from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import AuthenticationForm
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import ItemForm, LocationForm, PhotoForm, RegisterForm, VisitForm
from .models import AuditLog, Item, Location, Photo, Visit


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
        "latitude": "Latitude",
        "longitude": "Longitude",
        "overall_rating": "Rating",
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

def location_list(request):
    q = request.GET.get("q", "").strip()
    category = request.GET.get("category", "")
    locations = Location.objects.all()
    if q:
        locations = locations.filter(Q(name__icontains=q) | Q(address__icontains=q))
    if category:
        locations = locations.filter(category=category)
    return render(request, "tracker/location_list.html", {
        "locations": locations,
        "q": q,
        "category": category,
        "category_choices": Location.CATEGORY_CHOICES,
    })


def location_detail(request, pk):
    location = get_object_or_404(Location, pk=pk)
    return render(request, "tracker/location_detail.html", {
        "location": location,
        "visit_form": VisitForm(),
        "item_form": ItemForm(),
        "photo_form": PhotoForm(),
    })


@login_required
def location_create(request):
    form = LocationForm(request.POST or None)
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
        messages.success(request, "Location added.")
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
            messages.success(request, "Location updated.")
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
        messages.success(request, "Location deleted.")
        return redirect("location_list")
    return render(request, "tracker/location_confirm_delete.html", {"location": location})


def locations_geojson(request):
    qs = Location.objects.exclude(latitude=None).exclude(longitude=None)
    q = request.GET.get("q", "").strip()
    category = request.GET.get("category", "")
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(address__icontains=q))
    if category:
        qs = qs.filter(category=category)
    features = []
    for loc in qs:
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
                "rating": str(loc.overall_rating) if loc.overall_rating else None,
                "address": loc.address,
                "url": "/locations/{}/".format(loc.pk),
            },
        })
    return JsonResponse({"type": "FeatureCollection", "features": features})


# ── Items (HTMX) ──────────────────────────────────────────────────────────────

def _render_items_section(request, location, item_form=None, show_form=False):
    return render(request, "tracker/partials/items_section.html", {
        "location": location,
        "item_form": item_form or ItemForm(),
        "show_form": show_form,
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
            detail = 'Added item "{}" to "{}"'.format(item.name, location.name)
            if item.rating:
                detail += " with rating {}".format(item.rating)
            _log(request, AuditLog.ACTION_CREATE, item, detail)
            return _render_items_section(request, location)
        return _render_items_section(request, location, item_form=form, show_form=True)
    return _render_items_section(request, location, show_form=True)


@login_required
def item_edit(request, pk, item_pk):
    location = get_object_or_404(Location, pk=pk)
    item = get_object_or_404(Item, pk=item_pk, location=location)
    if request.method == "POST":
        old_name, old_rating, old_notes = item.name, item.rating, item.notes
        form = ItemForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            parts = []
            if old_name != item.name:
                parts.append('name: "{}" -> "{}"'.format(old_name, item.name))
            if old_rating != item.rating:
                parts.append("rating: {} -> {}".format(old_rating, item.rating))
            if old_notes != item.notes:
                parts.append("notes changed")
            _log(
                request,
                AuditLog.ACTION_UPDATE,
                item,
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
    return _render_visits_section(request, location, show_form=True)


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
    return _render_photos_section(request, location, show_form=True)


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
