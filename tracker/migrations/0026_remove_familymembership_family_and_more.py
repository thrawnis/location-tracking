import django.db.models.deletion
import tracker.models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tracker", "0025_itemreview_subject_seen_itemreview_submitted_by_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Replace the group-style Family models with one-to-one connections.
        migrations.DeleteModel(name="FamilyMembership"),
        migrations.DeleteModel(name="Family"),
        migrations.CreateModel(
            name="ConnectToken",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token", models.CharField(default=tracker.models._invite_token, max_length=64, unique=True)),
                ("user", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="connect_token", to=settings.AUTH_USER_MODEL,
                )),
            ],
        ),
        migrations.CreateModel(
            name="Connection",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user_high", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="+", to=settings.AUTH_USER_MODEL,
                )),
                ("user_low", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="+", to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"unique_together": {("user_low", "user_high")}},
        ),
    ]
