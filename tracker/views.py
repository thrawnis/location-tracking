import json
import math
import re
import urllib.request
import urllib.parse
from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta

from django.utils import timezone

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.cache import cache
from django.contrib.auth.forms import AuthenticationForm
from django.db.models import Avg, Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import (
    CollectionForm, ItemForm, ItemReviewForm, LocationForm, LocationReviewForm,
    PhotoForm, RegisterForm, TakeoutImportForm, VisitForm,
)
from .models import (
    AuditLog, Collection, Item, ItemReview, Location, LocationReview,
    OsmSearchCache, Photo, Visit,
)


# ── Audit helpers ─────────────────────────────────────────────────────────────

def _get_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    return xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR")


def _log(request, action, obj, detail=""):
    AuditLog.objects.create(
        user=request.user if request.user.is_authenticated else None,
        action=action,
        model_name=type(obj).__name__,
        object_id=obj.pk,
        object_repr=str(obj)[:255],
        detail=detail,
        ip_address=_get_ip(request),
    )


def _location_diff(old, new_data):
    field_labels = {
        "name": "Name",
        "category": "Category",
        "address": "Address",
        "city": "City",
        "state": "State",
        "latitude": "Latitude",
        "longitude": "Longitude",
        "overall_rating": "Rating",
        "phone": "Phone",
        "website": "Website",
        "hours": "Hours",
        "gluten_free": "Gluten-free",
        "dietary_notes": "Dietary notes",
        "public_notes": "Public notes",
        "private_notes": "Private notes",
    }
    parts = []
    for field, label in field_labels.items():
        old_val = str(getattr(old, field) or "")
        new_val = str(new_data.get(field) or "")
        if old_val != new_val:
            parts.append('{}: "{}" -> "{}"'.format(label, old_val, new_val))
    return "; ".join(parts) if parts else "No changes detected"


# ── Auth ──────────────────────────────────────────────────────────────────────

def login_view(request):
    if request.user.is_authenticated:
        return redirect("location_list")
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        login(request, user)
        return redirect(request.GET.get("next", "location_list"))
    return render(request, "registration/login.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect("location_list")


def register_view(request):
    if request.user.is_authenticated:
        return redirect("location_list")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Welcome, {}!".format(user.username))
        return redirect("location_list")
    return render(request, "registration/register.html", {"form": form})


# ── Locations ─────────────────────────────────────────────────────────────────

@login_required
def location_list(request):
    locations = (
        Location.objects
        .prefetch_related("photos", "visits", "items", "collections")
        .annotate(
            user_avg_rating=Avg("reviews__rating"),
            user_review_count=Count("reviews", distinct=True),
        )
        .all()
    )
    return render(request, "tracker/location_list.html", {
        "locations": locations,
        "category_choices": Location.CATEGORY_CHOICES,
        "status_choices": Location.STATUS_CHOICES,
        "gf_choices": Location.GF_CHOICES,
        "all_collections": Collection.objects.all(),
    })


@login_required
def location_detail(request, pk):
    location = get_object_or_404(
        Location.objects.prefetch_related(
            "photos", "visits__user", "items__reviews__user",
            "reviews__user", "collections",
        ),
        pk=pk,
    )
    my_review = location.reviews.filter(user=request.user).first()
    return render(request, "tracker/location_detail.html", {
        "location": location,
        "visit_form": VisitForm(),
        "item_form": ItemForm(),
        "photo_form": PhotoForm(),
        "my_review": my_review,
        "all_collections": Collection.objects.all(),
    })


@login_required
def location_create(request):
    prefill = {f: request.GET[f] for f in [
        'name','address','latitude','longitude','city','state',
        'phone','website','hours','gluten_free','dietary_notes',
        'status','google_place_id',
    ] if request.GET.get(f)}
    form = LocationForm(request.POST or None, initial=prefill or None)
    if request.method == "POST" and form.is_valid():
        location = form.save(commit=False)
        location.created_by = request.user
        location.save()
        _log(
            request,
            AuditLog.ACTION_CREATE,
            location,
            'Created location "{}" (category: {})'.format(
                location.name, location.get_category_display()
            ),
        )
        messages.success(request, "Waypoint added.")
        return redirect("location_detail", pk=location.pk)
    return render(request, "tracker/location_form.html", {"form": form, "action": "Add"})


@login_required
def location_edit(request, pk):
    location = get_object_or_404(Location, pk=pk)
    if request.method == "POST":
        form = LocationForm(request.POST, instance=location)
        if form.is_valid():
            diff = _location_diff(location, form.cleaned_data)
            form.save()
            _log(request, AuditLog.ACTION_UPDATE, location, diff)
            messages.success(request, "Waypoint updated.")
            return redirect("location_detail", pk=location.pk)
    else:
        form = LocationForm(instance=location)
    return render(request, "tracker/location_form.html", {
        "form": form,
        "action": "Edit",
        "location": location,
    })


@login_required
def location_delete(request, pk):
    location = get_object_or_404(Location, pk=pk)
    if request.method == "POST":
        _log(
            request,
            AuditLog.ACTION_DELETE,
            location,
            'Deleted location "{}"'.format(location.name),
        )
        location.delete()
        messages.success(request, "Waypoint deleted.")
        return redirect("location_list")
    return render(request, "tracker/location_confirm_delete.html", {"location": location})


@login_required
@require_POST
def gf_verify(request, pk):
    """Mark/update the gluten-free verification for a location."""
    location = get_object_or_404(Location, pk=pk)
    action = request.POST.get("action", "verify")   # "verify" | "unverify"

    if action == "unverify":
        location.gluten_free_verified_by = None
        location.gluten_free_verified_at = None
        detail = "GF verification removed"
    else:
        location.gluten_free_verified_by = request.user
        location.gluten_free_verified_at = timezone.now()
        detail = f"GF status verified as '{location.get_gluten_free_display()}'"

    location.save(update_fields=["gluten_free_verified_by", "gluten_free_verified_at", "updated_at"])
    _log(request, AuditLog.ACTION_UPDATE, location, detail)

    from django.http import HttpResponse
    # Re-render just the GF card partial via HTMX
    return render(request, "tracker/partials/gf_card.html", {"location": location})


@login_required
def locations_geojson(request):
    qs = (
        Location.objects
        .exclude(latitude=None).exclude(longitude=None)
        .annotate(user_avg_rating=Avg("reviews__rating"))
        .prefetch_related("photos")
    )
    features = []
    for loc in qs:
        rating = loc.user_avg_rating if loc.user_avg_rating is not None else loc.overall_rating
        first_photo = next(iter(loc.photos.all()), None)
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [float(loc.longitude), float(loc.latitude)],
            },
            "properties": {
                "id": loc.pk,
                "name": loc.name,
                "category": loc.category,
                "category_display": loc.get_category_display(),
                "rating": str(round(rating, 1)) if rating else None,
                "status": loc.status,
                "gluten_free": loc.gluten_free,
                "photo": first_photo.image.url if first_photo else None,
                "address": loc.address,
                "city": loc.city,
                "state": loc.state,
                "city_state": ", ".join(filter(None, [loc.city, loc.state])),
                "url": "/locations/{}/".format(loc.pk),
            },
        })
    return JsonResponse({"type": "FeatureCollection", "features": features})


# ── Items (HTMX) ──────────────────────────────────────────────────────────────

def _annotated_items(location):
    """Items with avg_rating and review_count annotations, reviews prefetched."""
    return (
        location.items
        .annotate(
            avg_rating=Avg("reviews__rating"),
            review_count=Count("reviews", distinct=True),
        )
        .prefetch_related("reviews__user")
        .order_by("name")
    )


def _render_items_section(
    request, location,
    item_form=None, show_form=False,
    review_item_pk=None, review_form=None,
):
    # Determine the logged-in user's existing reviews (item_pk → review)
    my_reviews = {}
    if request.user.is_authenticated:
        for rev in ItemReview.objects.filter(
            item__location=location, user=request.user
        ).select_related("item"):
            my_reviews[rev.item_id] = rev

    return render(request, "tracker/partials/items_section.html", {
        "location": location,
        "items": _annotated_items(location),
        "item_form": item_form or ItemForm(),
        "show_form": show_form,
        "review_item_pk": review_item_pk,
        "review_form": review_form or ItemReviewForm(),
        "my_reviews": my_reviews,
    })


@login_required
def item_add(request, pk):
    location = get_object_or_404(Location, pk=pk)
    if request.method == "POST":
        form = ItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.location = location
            item.save()
            _log(request, AuditLog.ACTION_CREATE, item,
                 'Added item "{}" to "{}"'.format(item.name, location.name))
            # Optionally create the submitter's initial review
            initial_rating = request.POST.get("initial_rating", "").strip()
            initial_notes  = request.POST.get("initial_notes", "").strip()
            if initial_rating:
                try:
                    from decimal import Decimal
                    rev = ItemReview.objects.create(
                        item=item,
                        user=request.user,
                        rating=Decimal(initial_rating),
                        notes=initial_notes,
                    )
                    _log(request, AuditLog.ACTION_CREATE, rev,
                         'Rated "{}" {}/5 in "{}"'.format(item.name, initial_rating, location.name))
                except Exception:
                    pass
            return _render_items_section(request, location)
        return _render_items_section(request, location, item_form=form, show_form=True)
    show = request.GET.get("show", "1") != "0"
    return _render_items_section(request, location, show_form=show)


@login_required
def item_edit(request, pk, item_pk):
    location = get_object_or_404(Location, pk=pk)
    item = get_object_or_404(Item, pk=item_pk, location=location)
    if request.method == "POST":
        old_name, old_notes = item.name, item.notes
        form = ItemForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            parts = []
            if old_name != item.name:
                parts.append('name: "{}" -> "{}"'.format(old_name, item.name))
            if old_notes != item.notes:
                parts.append("description changed")
            _log(
                request, AuditLog.ACTION_UPDATE, item,
                'Updated item in "{}": {}'.format(
                    location.name, "; ".join(parts) or "no changes"
                ),
            )
            return _render_items_section(request, location)
        return render(request, "tracker/partials/item_edit_form.html", {
            "location": location, "item": item, "form": form,
        })
    return render(request, "tracker/partials/item_edit_form.html", {
        "location": location, "item": item, "form": ItemForm(instance=item),
    })


@login_required
def item_review_upsert(request, pk, item_pk):
    """Create or update the logged-in user's review for one item."""
    location = get_object_or_404(Location, pk=pk)
    item = get_object_or_404(Item, pk=item_pk, location=location)
    existing = ItemReview.objects.filter(item=item, user=request.user).first()

    if request.method == "POST":
        form = ItemReviewForm(request.POST, instance=existing)
        if form.is_valid():
            review = form.save(commit=False)
            review.item = item
            review.user = request.user
            review.save()
            action = AuditLog.ACTION_UPDATE if existing else AuditLog.ACTION_CREATE
            _log(request, action, review,
                 '{} review for "{}" in "{}": {}/5'.format(
                     "Updated" if existing else "Added",
                     item.name, location.name, review.rating))
            return _render_items_section(request, location)
        return _render_items_section(
            request, location,
            review_item_pk=item_pk, review_form=form,
        )

    # GET — show the review form (or cancel: just render the section without form)
    if request.GET.get("cancel"):
        return _render_items_section(request, location)
    form = ItemReviewForm(instance=existing)
    return _render_items_section(
        request, location,
        review_item_pk=item_pk, review_form=form,
    )


@login_required
@require_POST
def item_review_delete(request, pk, item_pk):
    """Delete the logged-in user's own review."""
    location = get_object_or_404(Location, pk=pk)
    item = get_object_or_404(Item, pk=item_pk, location=location)
    review = get_object_or_404(ItemReview, item=item, user=request.user)
    _log(request, AuditLog.ACTION_DELETE, review,
         'Deleted review for "{}" in "{}"'.format(item.name, location.name))
    review.delete()
    return _render_items_section(request, location)


@login_required
@require_POST
def item_delete(request, pk, item_pk):
    location = get_object_or_404(Location, pk=pk)
    item = get_object_or_404(Item, pk=item_pk, location=location)
    _log(
        request,
        AuditLog.ACTION_DELETE,
        item,
        'Deleted item "{}" from "{}"'.format(item.name, location.name),
    )
    item.delete()
    return _render_items_section(request, location)


# ── Visits (HTMX) ─────────────────────────────────────────────────────────────

def _render_visits_section(request, location, visit_form=None, show_form=False):
    return render(request, "tracker/partials/visits_section.html", {
        "location": location,
        "visit_form": visit_form or VisitForm(),
        "show_form": show_form,
    })


@login_required
def visit_add(request, pk):
    location = get_object_or_404(Location, pk=pk)
    if request.method == "POST":
        form = VisitForm(request.POST)
        if form.is_valid():
            visit = form.save(commit=False)
            visit.location = location
            visit.user = request.user
            visit.save()
            _log(
                request,
                AuditLog.ACTION_CREATE,
                visit,
                'Logged visit to "{}" on {}'.format(location.name, visit.date),
            )
            return _render_visits_section(request, location)
        return _render_visits_section(request, location, visit_form=form, show_form=True)
    show = request.GET.get("show", "1") != "0"
    return _render_visits_section(request, location, show_form=show)


@login_required
@require_POST
def visit_delete(request, pk, visit_pk):
    location = get_object_or_404(Location, pk=pk)
    visit = get_object_or_404(Visit, pk=visit_pk, location=location)
    _log(
        request,
        AuditLog.ACTION_DELETE,
        visit,
        'Deleted visit to "{}" dated {}'.format(location.name, visit.date),
    )
    visit.delete()
    return _render_visits_section(request, location)


# ── Photos (HTMX) ─────────────────────────────────────────────────────────────

def _render_photos_section(request, location, photo_form=None, show_form=False):
    return render(request, "tracker/partials/photos_section.html", {
        "location": location,
        "photo_form": photo_form or PhotoForm(),
        "show_form": show_form,
    })


@login_required
def photo_add(request, pk):
    location = get_object_or_404(Location, pk=pk)
    if request.method == "POST":
        form = PhotoForm(request.POST, request.FILES)
        if form.is_valid():
            photo = form.save(commit=False)
            photo.location = location
            photo.uploaded_by = request.user
            photo.save()
            detail = 'Uploaded photo to "{}"'.format(location.name)
            if photo.caption:
                detail += ' with caption "{}"'.format(photo.caption)
            _log(request, AuditLog.ACTION_CREATE, photo, detail)
            return _render_photos_section(request, location)
        return _render_photos_section(request, location, photo_form=form, show_form=True)
    show = request.GET.get("show", "1") != "0"
    return _render_photos_section(request, location, show_form=show)


@login_required
@require_POST
def photo_delete(request, pk, photo_pk):
    location = get_object_or_404(Location, pk=pk)
    photo = get_object_or_404(Photo, pk=photo_pk, location=location)
    detail = 'Deleted photo from "{}"'.format(location.name)
    if photo.caption:
        detail += ' (caption: "{}")'.format(photo.caption)
    _log(request, AuditLog.ACTION_DELETE, photo, detail)
    if photo.image and photo.image.storage.exists(photo.image.name):
        photo.image.delete(save=False)
    photo.delete()
    return _render_photos_section(request, location)


@login_required
@require_POST
def photo_rotate(request, pk, photo_pk):
    """Rotate a photo 90° clockwise or counter-clockwise in place."""
    from PIL import Image, UnidentifiedImageError
    location = get_object_or_404(Location, pk=pk)
    photo = get_object_or_404(Photo, pk=photo_pk, location=location)
    direction = request.POST.get("direction", "cw")
    angle = -90 if direction == "cw" else 90  # PIL rotates CCW by default
    try:
        img = Image.open(photo.image.path)
        # expand=True ensures the canvas grows for portrait/landscape swaps
        rotated = img.rotate(angle, expand=True)
        fmt = img.format or "JPEG"
        if fmt == "JPEG":
            rotated.save(photo.image.path, format=fmt, quality=90)
        else:
            rotated.save(photo.image.path, format=fmt)
        _log(request, AuditLog.ACTION_UPDATE, photo,
             'Rotated photo {} {}° in "{}"'.format(photo.pk, abs(angle), location.name))
    except (FileNotFoundError, UnidentifiedImageError, Exception):
        pass
    return _render_photos_section(request, location)


# ── Server-side IP geolocation (fallback when browser denies location) ────────

_PRIVATE_PREFIXES = ("10.", "172.16.", "172.17.", "172.18.", "172.19.",
                     "172.20.", "172.21.", "172.22.", "172.23.", "172.24.",
                     "172.25.", "172.26.", "172.27.", "172.28.", "172.29.",
                     "172.30.", "172.31.", "192.168.")

@login_required
def geoip_view(request):
    # Rate-limit: one successful lookup per user per 60 seconds
    rate_key = f"geoip_rl_{request.user.pk}"
    if cache.get(rate_key):
        return JsonResponse({"status": "rate_limited"}, status=429)

    ip = _get_ip(request)
    is_private = ip in ("127.0.0.1", "::1") or any(ip.startswith(p) for p in _PRIVATE_PREFIXES)
    if is_private:
        return JsonResponse({"status": "private"})
    try:
        url = f"http://ip-api.com/json/{ip}?fields=status,lat,lon,city,regionName"
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read())
        if data.get("status") == "success":
            cache.set(rate_key, True, 60)
            return JsonResponse({
                "status": "ok",
                "lat": data["lat"],
                "lng": data["lon"],
                "city": data.get("city", ""),
                "region": data.get("regionName", ""),
            })
    except Exception:
        pass
    return JsonResponse({"status": "error"})


# ── OSM POI search (server-side proxy + 24-hour cache) ────────────────────────

_OSM_CACHE_TTL = timedelta(hours=24)
_OVERPASS_URL  = "https://overpass-api.de/api/interpreter"


def _round2(value):
    """Round a float to 2 dp as a Decimal (cache key)."""
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def osm_search(request):
    """
    Proxy for Overpass API with a 24-hour server-side cache.

    GET params: q, lat, lng, radius (metres, default 8047)
    Returns JSON: { cached: bool, fetched_at: iso, results: [...] }
    Each result mirrors the Overpass element with an extra 'dist_km' field
    computed server-side.
    """
    query    = request.GET.get("q", "").strip()
    try:
        lat    = float(request.GET.get("lat", 0))
        lng    = float(request.GET.get("lng", 0))
        radius = int(request.GET.get("radius", 8047))
    except (ValueError, TypeError):
        return JsonResponse({"error": "invalid params"}, status=400)

    if not query:
        return JsonResponse({"error": "q required"}, status=400)

    # ── Cache lookup ─────────────────────────────────────────────────────────
    clat = _round2(lat)
    clng = _round2(lng)

    cached = OsmSearchCache.objects.filter(
        query=query.lower(),
        center_lat=clat,
        center_lng=clng,
        radius_m=radius,
        fetched_at__gte=timezone.now() - _OSM_CACHE_TTL,
    ).first()

    if cached:
        return JsonResponse({
            "cached": True,
            "fetched_at": cached.fetched_at.isoformat(),
            "results": cached.results,
        })

    # ── Fetch from Overpass ───────────────────────────────────────────────────
    # Strip chars that break Overpass regex syntax
    q = re.sub(r'[\\"\[\](){}*+?.^$|]', '', query)
    overpass_q = (
        f'[out:json][timeout:25];('
        f'node["name"~"{q}",i](around:{radius},{lat},{lng});'
        f'way["name"~"{q}",i](around:{radius},{lat},{lng});'
        f'relation["name"~"{q}",i](around:{radius},{lat},{lng});'
        f');out center 200;'
    )

    try:
        # Overpass expects a form-encoded body: data=<query>
        form_body = urllib.parse.urlencode({'data': overpass_q}).encode()
        req = urllib.request.Request(
            _OVERPASS_URL,
            data=form_body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = json.loads(resp.read())
    except Exception as exc:
        return JsonResponse({"error": f"overpass unavailable: {exc}"}, status=502)

    # ── Compute distance + filter out no-coord elements ──────────────────────
    def _haversine(lat1, lon1, lat2, lon2):
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    results = []
    for el in raw.get("elements", []):
        elat = el.get("lat") or (el.get("center") or {}).get("lat")
        elng = el.get("lon") or (el.get("center") or {}).get("lon")
        if elat is None or elng is None:
            continue
        el["dist_km"] = round(_haversine(lat, lng, elat, elng), 4)
        results.append(el)

    results.sort(key=lambda e: e["dist_km"])

    # ── Store / update cache ──────────────────────────────────────────────────
    OsmSearchCache.objects.update_or_create(
        query=query.lower(),
        center_lat=clat,
        center_lng=clng,
        radius_m=radius,
        defaults={"results": results, "fetched_at": timezone.now()},
    )

    return JsonResponse({
        "cached": False,
        "fetched_at": timezone.now().isoformat(),
        "results": results,
    })


# ── Location reviews (HTMX) ───────────────────────────────────────────────────

def _render_location_reviews(request, location, review_form=None, show_form=False):
    my_review = location.reviews.filter(user=request.user).first() \
        if request.user.is_authenticated else None
    return render(request, "tracker/partials/location_reviews.html", {
        "location": location,
        "my_review": my_review,
        "review_form": review_form or LocationReviewForm(instance=my_review),
        "show_form": show_form,
    })


@login_required
def location_review_upsert(request, pk):
    """Create or update the logged-in user's overall review for a location."""
    location = get_object_or_404(Location, pk=pk)
    existing = LocationReview.objects.filter(location=location, user=request.user).first()

    if request.method == "POST":
        form = LocationReviewForm(request.POST, instance=existing)
        if form.is_valid():
            review = form.save(commit=False)
            review.location = location
            review.user = request.user
            review.save()
            action = AuditLog.ACTION_UPDATE if existing else AuditLog.ACTION_CREATE
            _log(request, action, review,
                 '{} review for "{}": {}/5'.format(
                     "Updated" if existing else "Added", location.name, review.rating))
            return _render_location_reviews(request, location)
        return _render_location_reviews(request, location, review_form=form, show_form=True)

    if request.GET.get("cancel"):
        return _render_location_reviews(request, location)
    return _render_location_reviews(request, location, show_form=True)


@login_required
@require_POST
def location_review_delete(request, pk):
    location = get_object_or_404(Location, pk=pk)
    review = get_object_or_404(LocationReview, location=location, user=request.user)
    _log(request, AuditLog.ACTION_DELETE, review,
         'Deleted review for "{}"'.format(location.name))
    review.delete()
    return _render_location_reviews(request, location)


# ── Collections ───────────────────────────────────────────────────────────────

@login_required
def collection_list(request):
    collections = (
        Collection.objects
        .prefetch_related("locations")
        .select_related("created_by")
        .annotate(loc_count=Count("locations"))
    )
    form = CollectionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        coll = form.save(commit=False)
        coll.created_by = request.user
        coll.save()
        _log(request, AuditLog.ACTION_CREATE, coll,
             'Created collection "{}"'.format(coll.name))
        messages.success(request, 'Collection "{}" created.'.format(coll.name))
        return redirect("collection_list")
    return render(request, "tracker/collection_list.html", {
        "collections": collections,
        "form": form,
    })


@login_required
@require_POST
def collection_delete(request, pk):
    coll = get_object_or_404(Collection, pk=pk)
    _log(request, AuditLog.ACTION_DELETE, coll,
         'Deleted collection "{}"'.format(coll.name))
    coll.delete()
    messages.success(request, "Collection deleted.")
    return redirect("collection_list")


@login_required
@require_POST
def collection_toggle(request, pk, loc_pk):
    """Add/remove a location to/from a collection (HTMX, from detail page)."""
    coll = get_object_or_404(Collection, pk=pk)
    location = get_object_or_404(Location, pk=loc_pk)
    if coll.locations.filter(pk=location.pk).exists():
        coll.locations.remove(location)
        detail = 'Removed "{}" from collection "{}"'.format(location.name, coll.name)
    else:
        coll.locations.add(location)
        detail = 'Added "{}" to collection "{}"'.format(location.name, coll.name)
    _log(request, AuditLog.ACTION_UPDATE, coll, detail)
    return render(request, "tracker/partials/collections_widget.html", {
        "location": location,
        "all_collections": Collection.objects.all(),
    })


# ── Export ────────────────────────────────────────────────────────────────────

@login_required
def export_locations(request):
    """Download all waypoints as CSV, GeoJSON, or KML."""
    from django.http import HttpResponse
    import csv
    from xml.sax.saxutils import escape as xml_escape

    fmt = request.GET.get("format", "csv").lower()
    qs = Location.objects.annotate(user_avg_rating=Avg("reviews__rating")).order_by("name")

    if fmt == "geojson":
        features = []
        for loc in qs:
            if not loc.has_coords():
                continue
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point",
                             "coordinates": [float(loc.longitude), float(loc.latitude)]},
                "properties": {
                    "name": loc.name, "category": loc.category, "status": loc.status,
                    "address": loc.address, "city": loc.city, "state": loc.state,
                    "phone": loc.phone, "website": loc.website, "hours": loc.hours,
                    "gluten_free": loc.gluten_free, "dietary_notes": loc.dietary_notes,
                    "rating": float(loc.user_avg_rating or loc.overall_rating or 0) or None,
                    "public_notes": loc.public_notes,
                },
            })
        resp = JsonResponse({"type": "FeatureCollection", "features": features},
                            json_dumps_params={"indent": 2})
        resp["Content-Disposition"] = 'attachment; filename="waypoints.geojson"'
        return resp

    if fmt == "kml":
        placemarks = []
        for loc in qs:
            if not loc.has_coords():
                continue
            desc_parts = [p for p in [
                loc.get_category_display(),
                loc.address,
                f"Phone: {loc.phone}" if loc.phone else "",
                f"GF: {loc.get_gluten_free_display()}" if loc.gluten_free else "",
                loc.public_notes,
            ] if p]
            placemarks.append(
                "<Placemark><name>{}</name><description>{}</description>"
                "<Point><coordinates>{},{},0</coordinates></Point></Placemark>".format(
                    xml_escape(loc.name),
                    xml_escape("\n".join(desc_parts)),
                    loc.longitude, loc.latitude,
                )
            )
        kml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
            '<name>Waypoints</name>{}</Document></kml>'.format("".join(placemarks))
        )
        resp = HttpResponse(kml, content_type="application/vnd.google-earth.kml+xml")
        resp["Content-Disposition"] = 'attachment; filename="waypoints.kml"'
        return resp

    # Default: CSV
    resp = HttpResponse(content_type="text/csv")
    resp["Content-Disposition"] = 'attachment; filename="waypoints.csv"'
    writer = csv.writer(resp)
    writer.writerow([
        "name", "category", "status", "address", "city", "state",
        "latitude", "longitude", "phone", "website", "hours",
        "gluten_free", "dietary_notes", "rating", "public_notes",
    ])
    for loc in qs:
        writer.writerow([
            loc.name, loc.category, loc.status, loc.address, loc.city, loc.state,
            loc.latitude or "", loc.longitude or "", loc.phone, loc.website, loc.hours,
            loc.gluten_free, loc.dietary_notes,
            loc.user_avg_rating or loc.overall_rating or "", loc.public_notes,
        ])
    return resp


# ── Import (Google Takeout / GeoJSON) ─────────────────────────────────────────

def _parse_takeout_features(data):
    """
    Yield dicts of location fields from either a Google Takeout Saved Places
    JSON or a generic GeoJSON FeatureCollection.
    """
    for feat in data.get("features", []):
        geom = feat.get("geometry") or {}
        props = feat.get("properties") or {}
        coords = geom.get("coordinates") or [None, None]
        lng, lat = (coords + [None, None])[:2]

        # Google Takeout nests details under properties.location
        g_loc = props.get("location") or {}
        name = (
            g_loc.get("name")
            or props.get("name")
            or props.get("Title")
            or props.get("title")
            or ""
        ).strip()
        if not name:
            continue

        address = g_loc.get("address") or props.get("address") or ""
        yield {
            "name": name[:255],
            "address": address,
            "latitude": lat,
            "longitude": lng,
            "website": (props.get("google_maps_url") or props.get("website") or "")[:500],
        }


@login_required
def import_locations(request):
    """Upload Google Takeout Saved Places JSON (or GeoJSON) to bulk-create waypoints."""
    form = TakeoutImportForm(request.POST or None, request.FILES or None)
    result = None
    if request.method == "POST" and form.is_valid():
        try:
            data = json.loads(form.cleaned_data["file"].read().decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            form.add_error("file", "Not a valid JSON file.")
            data = None

        if data is not None:
            status = form.cleaned_data["default_status"]
            created, skipped = 0, 0
            for fields in _parse_takeout_features(data):
                # Skip exact name duplicates (case-insensitive)
                if Location.objects.filter(name__iexact=fields["name"]).exists():
                    skipped += 1
                    continue
                loc = Location.objects.create(
                    created_by=request.user, status=status, **fields,
                )
                _log(request, AuditLog.ACTION_CREATE, loc,
                     'Imported "{}" from file upload'.format(loc.name))
                created += 1
            result = {"created": created, "skipped": skipped}
            if created:
                messages.success(
                    request,
                    "Imported {} waypoint{} ({} duplicate{} skipped).".format(
                        created, "s" if created != 1 else "",
                        skipped, "s" if skipped != 1 else ""),
                )
            else:
                messages.info(request, "No new waypoints found in that file.")
    return render(request, "tracker/import_export.html", {
        "form": form,
        "result": result,
    })


# ── Activity feed ─────────────────────────────────────────────────────────────

@login_required
def activity_feed(request):
    """Recent community activity: reviews, new waypoints, GF verifications, photos."""
    logs = (
        AuditLog.objects
        .select_related("user")
        .filter(model_name__in=[
            "Location", "LocationReview", "ItemReview", "Item", "Photo", "Visit",
        ])
        .order_by("-timestamp")[:100]
    )
    return render(request, "tracker/activity_feed.html", {"logs": logs})


# ── Duplicate detection API ───────────────────────────────────────────────────

@login_required
def check_duplicate(request):
    """
    GET lat, lng[, exclude] → nearby existing waypoints within ~100 m,
    so the add form can warn before creating a duplicate.
    """
    try:
        lat = float(request.GET.get("lat"))
        lng = float(request.GET.get("lng"))
    except (TypeError, ValueError):
        return JsonResponse({"matches": []})
    exclude_pk = request.GET.get("exclude")

    # ~0.001° ≈ 111 m latitude; cheap bounding box first, then precise haversine
    box = 0.0015
    qs = Location.objects.filter(
        latitude__gte=lat - box, latitude__lte=lat + box,
        longitude__gte=lng - box, longitude__lte=lng + box,
    )
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)

    def _haversine_m(lat1, lon1, lat2, lon2):
        R = 6371000.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat / 2) ** 2
             + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
             * math.sin(dlon / 2) ** 2)
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    matches = []
    for loc in qs:
        dist = _haversine_m(lat, lng, float(loc.latitude), float(loc.longitude))
        if dist <= 100:
            matches.append({
                "id": loc.pk,
                "name": loc.name,
                "distance_m": round(dist),
                "url": "/locations/{}/".format(loc.pk),
            })
    matches.sort(key=lambda m: m["distance_m"])
    return JsonResponse({"matches": matches[:5]})


# ── Admin audit log ───────────────────────────────────────────────────────────

@user_passes_test(lambda u: u.is_staff)
def audit_log_view(request):
    logs = AuditLog.objects.select_related("user").all()
    q = request.GET.get("q", "").strip()
    action = request.GET.get("action", "")
    model = request.GET.get("model", "")
    if q:
        logs = logs.filter(
            Q(object_repr__icontains=q) | Q(detail__icontains=q) | Q(user__username__icontains=q)
        )
    if action:
        logs = logs.filter(action=action)
    if model:
        logs = logs.filter(model_name=model)
    model_names = (
        AuditLog.objects.values_list("model_name", flat=True).distinct().order_by("model_name")
    )
    return render(request, "tracker/audit_log.html", {
        "logs": logs[:500],
        "q": q,
        "action": action,
        "model": model,
        "action_choices": AuditLog.ACTION_CHOICES,
        "model_names": model_names,
    })
