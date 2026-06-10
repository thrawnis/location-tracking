from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Collection, Item, ItemReview, Location, LocationReview, Photo, Visit


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=False)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")


class LocationForm(forms.ModelForm):
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
            "phone",
            "website",
            "hours",
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
            "phone": forms.TextInput(attrs={"placeholder": "+1 (555) 000-0000"}),
            "website": forms.URLInput(attrs={"placeholder": "https://example.com"}),
            "hours": forms.Textarea(attrs={"rows": 2, "placeholder": "Mon–Fri 9am–9pm\nSat–Sun 10am–6pm"}),
            "dietary_notes": forms.Textarea(
                attrs={"rows": 3, "placeholder": "e.g. Dedicated GF fryer, staff trained on cross-contamination, ask for GF menu"}
            ),
            "public_notes": forms.Textarea(attrs={"rows": 4, "placeholder": "Visible to everyone"}),
            "private_notes": forms.Textarea(
                attrs={"rows": 4, "placeholder": "Only visible when logged in"}
            ),
            "overall_rating": forms.HiddenInput(),
        }


class ItemForm(forms.ModelForm):
    """Create/edit an item (dish/product). Rating lives in ItemReview."""

    class Meta:
        model = Item
        fields = ["name", "notes"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Item or dish name"}),
            "notes": forms.Textarea(attrs={"rows": 2, "placeholder": "Description (optional)"}),
        }


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
