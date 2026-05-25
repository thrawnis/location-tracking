import os
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.utils import timezone
from django.db import models


RATING_VALIDATORS = [
    MinValueValidator(Decimal("0.5")),
    MaxValueValidator(Decimal("5.0")),
]

MAX_PHOTO_PIXELS = 2_000_000  # 2 megapixels


class Location(models.Model):
    CATEGORY_CHOICES = [
        ("restaurant", "Restaurant"),
        ("store", "Store"),
        ("attraction", "Attraction"),
        ("other", "Other"),
    ]

    name = models.CharField(max_length=255)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="other")
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    public_notes = models.TextField(blank=True)
    private_notes = models.TextField(blank=True)
    phone = models.CharField(max_length=50, blank=True, help_text="Phone number")
    website = models.URLField(max_length=500, blank=True, help_text="Website URL")
    hours = models.TextField(blank=True, help_text="Opening hours (e.g. Mon-Fri 9am-5pm)")

    GF_UNKNOWN   = ""
    GF_DEDICATED = "dedicated"
    GF_OPTIONS   = "options"
    GF_LIMITED   = "limited"
    GF_NONE      = "none"
    GF_CHOICES = [
        (GF_UNKNOWN,   "Unknown"),
        (GF_DEDICATED, "Dedicated GF kitchen (celiac-safe)"),
        (GF_OPTIONS,   "GF options available (shared kitchen)"),
        (GF_LIMITED,   "Limited GF (e.g. remove the bun)"),
        (GF_NONE,      "No gluten-free options"),
    ]
    gluten_free = models.CharField(
        max_length=20,
        choices=GF_CHOICES,
        blank=True,
        default="",
        help_text="Gluten-free accommodation level",
    )
    dietary_notes = models.TextField(
        blank=True,
        help_text="Dietary notes: allergies, cross-contamination info, etc.",
    )
    gluten_free_verified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="gf_verifications",
        help_text="User who verified the GF status first-hand",
    )
    gluten_free_verified_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When the GF status was last verified",
    )
    overall_rating = models.DecimalField(
        max_digits=2,
        decimal_places=1,
        null=True,
        blank=True,
        validators=RATING_VALIDATORS,
    )
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="locations"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def has_coords(self):
        return self.latitude is not None and self.longitude is not None


class Visit(models.Model):
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="visits")
    date = models.DateField()
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="visits"
    )

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.location.name} – {self.date}"


class Item(models.Model):
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="items")
    name = models.CharField(max_length=255)
    # General description/notes about the item — not a per-user rating
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.location.name} – {self.name}"


class ItemReview(models.Model):
    """One rating + review per registered user per item/dish."""

    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="item_reviews")
    rating = models.DecimalField(
        max_digits=2,
        decimal_places=1,
        validators=RATING_VALIDATORS,
    )
    notes = models.TextField(blank=True, help_text="Your personal review or tasting notes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("item", "user")]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} → {self.item.name}: {self.rating}"


def _photo_upload_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    return f"photos/location_{instance.location_id}/{instance.location_id}_{filename}"


class Photo(models.Model):
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to=_photo_upload_path)
    caption = models.CharField(max_length=255, blank=True)
    uploaded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="photos"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"Photo for {self.location.name} ({self.pk})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self._resize_to_2mp()

    def _resize_to_2mp(self):
        from PIL import Image, UnidentifiedImageError
        try:
            img = Image.open(self.image.path)
        except (FileNotFoundError, UnidentifiedImageError):
            return
        w, h = img.size
        if w * h > MAX_PHOTO_PIXELS:
            ratio = (MAX_PHOTO_PIXELS / (w * h)) ** 0.5
            new_size = (max(1, int(w * ratio)), max(1, int(h * ratio)))
            img = img.resize(new_size, Image.LANCZOS)
            fmt = img.format or "JPEG"
            if fmt == "JPEG":
                img.save(self.image.path, format=fmt, optimize=True, quality=85)
            else:
                img.save(self.image.path, format=fmt, optimize=True)


class OsmSearchCache(models.Model):
    """
    Caches Overpass API search results for up to 24 hours.
    Key: (query, lat/lng rounded to 2 dp ≈ 1 km grid, radius_m).
    """
    query      = models.CharField(max_length=255, db_index=True)
    center_lat = models.DecimalField(max_digits=7, decimal_places=2)   # ~1 km grid
    center_lng = models.DecimalField(max_digits=8, decimal_places=2)
    radius_m   = models.IntegerField()
    results    = models.JSONField(default=list)   # list of serialised Overpass element dicts
    fetched_at = models.DateTimeField(default=timezone.now)  # updatable so cache can refresh

    class Meta:
        unique_together = [("query", "center_lat", "center_lng", "radius_m")]
        ordering = ["-fetched_at"]

    def __str__(self):
        return f'OSM "{self.query}" @({self.center_lat},{self.center_lng}) r={self.radius_m}m'


class AuditLog(models.Model):
    ACTION_CREATE = "create"
    ACTION_UPDATE = "update"
    ACTION_DELETE = "delete"
    ACTION_CHOICES = [
        (ACTION_CREATE, "Create"),
        (ACTION_UPDATE, "Update"),
        (ACTION_DELETE, "Delete"),
    ]

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=50)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    object_repr = models.CharField(max_length=255)
    detail = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        user_str = self.user.username if self.user else "anonymous"
        return f"{self.timestamp:%Y-%m-%d %H:%M} | {user_str} | {self.action} {self.model_name} #{self.object_id}"
