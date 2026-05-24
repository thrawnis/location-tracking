from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Item, ItemReview, Location, Photo, Visit


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
            "address",
            "city",
            "state",
            "latitude",
            "longitude",
            "overall_rating",
            "public_notes",
            "private_notes",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Location name"}),
            "address": forms.TextInput(attrs={"placeholder": "Address (optional — use map to set)"}),
            "city": forms.HiddenInput(),
            "state": forms.HiddenInput(),
            "latitude": forms.HiddenInput(),
            "longitude": forms.HiddenInput(),
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
