import os
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
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
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    public_notes = models.TextField(blank=True)
    private_notes = models.TextField(blank=True)
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
    rating = models.DecimalField(
        max_digits=2,
        decimal_places=1,
        null=True,
        blank=True,
        validators=RATING_VALIDATORS,
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.location.name} – {self.name}"


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
            # Preserve format; fall back to JPEG
            fmt = img.format or "JPEG"
            if fmt == "JPEG":
                img.save(self.image.path, format=fmt, optimize=True, quality=85)
            else:
                img.save(self.image.path, format=fmt, optimize=True)


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
    # Human-readable summary of what changed / what was added or removed
    detail = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        user_str = self.user.username if self.user else "anonymous"
        return f"{self.timestamp:%Y-%m-%d %H:%M} | {user_str} | {self.action} {self.model_name} #{self.object_id}"
