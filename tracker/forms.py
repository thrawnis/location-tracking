import re

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Collection, Item, ItemReview, Location, LocationReview, Photo, Visit


def normalize_case(text):
    """Title-case a value only if the user typed it in ALL CAPS or all lowercase
    (i.e. not intentional casing). Mixed-case values are returned untouched."""
    if not text:
        return text
    s = text.strip()
    if not any(c.isalpha() for c in s):
        return s
    if s == s.upper() or s == s.lower():
        return re.sub(r"[A-Za-z']+", lambda m: m.group(0).capitalize(), s)
    return s


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=False)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")


class LocationForm(forms.ModelForm):
    # Fields sourced from Google when a waypoint is saved from a map POI.
    # For such entries they are locked so only manually added waypoints are editable.
    GOOGLE_SOURCED_FIELDS = ["name", "address", "latitude", "longitude", "city", "state"]

    class Meta:
        model = Location
        fields = [
            "name",
            "category",
            "status",
            "address",
            "city",
            "state",
            "latitude",
            "longitude",
            "google_place_id",
            "overall_rating",
            "gluten_free",
            "dietary_notes",
            "public_notes",
            "private_notes",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Location name"}),
            "status": forms.RadioSelect(),
            "address": forms.TextInput(attrs={"placeholder": "Address (optional — use map to set)"}),
            "city": forms.HiddenInput(),
            "state": forms.HiddenInput(),
            "latitude": forms.HiddenInput(),
            "longitude": forms.HiddenInput(),
            "google_place_id": forms.HiddenInput(),
            "dietary_notes": forms.Textarea(
                attrs={"rows": 3, "placeholder": "e.g. Dedicated GF fryer, staff trained on cross-contamination, ask for GF menu"}
            ),
            "public_notes": forms.Textarea(attrs={"rows": 4, "placeholder": "Visible to everyone"}),
            "private_notes": forms.Textarea(
                attrs={"rows": 4, "placeholder": "Only visible when logged in"}
            ),
            "overall_rating": forms.HiddenInput(),
        }

    def __init__(self, *args, unlock_google_fields=False, **kwargs):
        super().__init__(*args, **kwargs)
        # A Google Place ID (from a saved POI) marks the identity fields as
        # authoritative; lock them so they can't be edited after the fact.
        # Admins can pass unlock_google_fields=True to override the lock.
        pid = self.initial.get("google_place_id") or getattr(self.instance, "google_place_id", "")
        self.google_locked = bool(pid) and not unlock_google_fields
        if self.google_locked:
            for name in self.GOOGLE_SOURCED_FIELDS:
                field = self.fields.get(name)
                if field:
                    field.widget.attrs["readonly"] = True

    # Fix up shouting / all-lowercase entry on the identifying fields.
    def clean_name(self):
        return normalize_case(self.cleaned_data.get("name", ""))

    def clean_address(self):
        return normalize_case(self.cleaned_data.get("address", ""))

    def clean_city(self):
        return normalize_case(self.cleaned_data.get("city", ""))

    def clean_state(self):
        return normalize_case(self.cleaned_data.get("state", ""))

    def clean(self):
        """Ignore any tampered edits to locked, Google-sourced fields."""
        cleaned = super().clean()
        if getattr(self, "google_locked", False) and self.instance.pk:
            for name in self.GOOGLE_SOURCED_FIELDS:
                if name in cleaned:
                    cleaned[name] = getattr(self.instance, name)
        return cleaned


class ItemForm(forms.ModelForm):
    """Create/edit an item (dish/product). Rating lives in ItemReview."""

    class Meta:
        model = Item
        fields = ["name", "notes"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Item or dish name"}),
            "notes": forms.Textarea(attrs={"rows": 2, "placeholder": "Description (optional)"}),
        }

    def clean_name(self):
        return normalize_case(self.cleaned_data.get("name", ""))


class ItemReviewForm(forms.ModelForm):
    """A single user's rating + review text for one item."""

    class Meta:
        model = ItemReview
        fields = ["rating", "notes"]
        widgets = {
            "rating": forms.HiddenInput(),
            "notes": forms.Textarea(
                attrs={"rows": 2, "placeholder": "Your review (optional)"}
            ),
        }

    def clean_rating(self):
        rating = self.cleaned_data.get("rating")
        if not rating:
            raise forms.ValidationError("Please select a star rating.")
        return rating


class LocationReviewForm(forms.ModelForm):
    """A single user's overall rating + review for one location."""

    class Meta:
        model = LocationReview
        fields = ["rating", "notes"]
        widgets = {
            "rating": forms.HiddenInput(),
            "notes": forms.Textarea(
                attrs={"rows": 2, "placeholder": "Your review of this place (optional)"}
            ),
        }

    def clean_rating(self):
        rating = self.cleaned_data.get("rating")
        if not rating:
            raise forms.ValidationError("Please select a star rating.")
        return rating


class CollectionForm(forms.ModelForm):
    class Meta:
        model = Collection
        fields = ["name", "description"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g. Austin 2026, GF-safe spots"}),
            "description": forms.Textarea(attrs={"rows": 2, "placeholder": "Description (optional)"}),
        }


class TakeoutImportForm(forms.Form):
    """Upload a Google Takeout 'Saved Places' JSON or a generic GeoJSON file."""

    file = forms.FileField(
        help_text="Saved Places.json from Google Takeout, or any GeoJSON FeatureCollection",
    )
    default_status = forms.ChoiceField(
        choices=Location.STATUS_CHOICES,
        initial=Location.STATUS_WANT,
        label="Import as",
        help_text="Status to assign to imported places",
    )


class VisitForm(forms.ModelForm):
    class Meta:
        model = Visit
        fields = ["date"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
        }


class PhotoForm(forms.ModelForm):
    class Meta:
        model = Photo
        fields = ["image", "caption"]
        widgets = {
            "caption": forms.TextInput(attrs={"placeholder": "Caption (optional)"}),
        }
