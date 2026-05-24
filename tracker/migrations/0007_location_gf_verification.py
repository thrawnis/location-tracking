import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("tracker", "0006_location_dietary"),
    ]

    operations = [
        migrations.AddField(
            model_name="location",
            name="gluten_free_verified_by",
            field=models.ForeignKey(
                blank=True,
                help_text="User who verified the GF status first-hand",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="gf_verifications",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="location",
            name="gluten_free_verified_at",
            field=models.DateTimeField(
                blank=True,
                help_text="When the GF status was last verified",
                null=True,
            ),
        ),
    ]
