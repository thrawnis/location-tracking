"""
Migration: add ItemReview model, migrate existing Item.rating data, remove Item.rating.

Existing single-owner ratings (Item.rating / Item.notes) are migrated to
ItemReview records attributed to the location's created_by user.  If a location
has no created_by the old rating is silently dropped (there's no user to own it).
"""

import decimal

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def migrate_item_ratings(apps, schema_editor):
    """Copy Item.rating → ItemReview for each item that has a rating."""
    Item = apps.get_model("tracker", "Item")
    ItemReview = apps.get_model("tracker", "ItemReview")

    for item in Item.objects.select_related("location__created_by").filter(rating__isnull=False):
        owner = item.location.created_by
        if owner is None:
            continue
        ItemReview.objects.get_or_create(
            item=item,
            user=owner,
            defaults={
                "rating": item.rating,
                "notes": item.notes,  # carry over old notes as the owner's review
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("tracker", "0002_location_city_state"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. Create ItemReview table
        migrations.CreateModel(
            name="ItemReview",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                (
                    "item",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reviews",
                        to="tracker.item",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="item_reviews",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "rating",
                    models.DecimalField(
                        decimal_places=1,
                        max_digits=2,
                        validators=[
                            django.core.validators.MinValueValidator(decimal.Decimal("0.5")),
                            django.core.validators.MaxValueValidator(decimal.Decimal("5.0")),
                        ],
                    ),
                ),
                ("notes", models.TextField(blank=True, help_text="Your personal review or tasting notes")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-created_at"],
                "unique_together": {("item", "user")},
            },
        ),
        # 2. Migrate existing ratings to ItemReview rows
        migrations.RunPython(migrate_item_ratings, migrations.RunPython.noop),
        # 3. Drop Item.rating (reviews own ratings now)
        migrations.RemoveField(model_name="item", name="rating"),
    ]
