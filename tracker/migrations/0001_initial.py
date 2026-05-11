import django.core.validators
import django.db.models.deletion
import tracker.models
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Location",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                ("category", models.CharField(
                    choices=[
                        ("restaurant", "Restaurant"),
                        ("store", "Store"),
                        ("attraction", "Attraction"),
                        ("other", "Other"),
                    ],
                    default="other",
                    max_length=20,
                )),
                ("address", models.TextField(blank=True)),
                ("latitude", models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True)),
                ("longitude", models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True)),
                ("public_notes", models.TextField(blank=True)),
                ("private_notes", models.TextField(blank=True)),
                ("overall_rating", models.DecimalField(
                    blank=True,
                    decimal_places=1,
                    max_digits=2,
                    null=True,
                    validators=[
                        django.core.validators.MinValueValidator(Decimal("0.5")),
                        django.core.validators.MaxValueValidator(Decimal("5.0")),
                    ],
                )),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="locations",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="Visit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField()),
                ("location", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="visits",
                    to="tracker.location",
                )),
                ("user", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="visits",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"ordering": ["-date"]},
        ),
        migrations.CreateModel(
            name="Item",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                ("rating", models.DecimalField(
                    blank=True,
                    decimal_places=1,
                    max_digits=2,
                    null=True,
                    validators=[
                        django.core.validators.MinValueValidator(Decimal("0.5")),
                        django.core.validators.MaxValueValidator(Decimal("5.0")),
                    ],
                )),
                ("notes", models.TextField(blank=True)),
                ("location", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="items",
                    to="tracker.location",
                )),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="Photo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("image", models.ImageField(upload_to=tracker.models._photo_upload_path)),
                ("caption", models.CharField(blank=True, max_length=255)),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                ("location", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="photos",
                    to="tracker.location",
                )),
                ("uploaded_by", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="photos",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"ordering": ["-uploaded_at"]},
        ),
        migrations.CreateModel(
            name="AuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("timestamp", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("action", models.CharField(
                    choices=[("create", "Create"), ("update", "Update"), ("delete", "Delete")],
                    max_length=10,
                )),
                ("model_name", models.CharField(max_length=50)),
                ("object_id", models.PositiveIntegerField(blank=True, null=True)),
                ("object_repr", models.CharField(max_length=255)),
                ("detail", models.TextField(blank=True)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"ordering": ["-timestamp"]},
        ),
    ]
