import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Change OsmSearchCache.fetched_at from auto_now_add (immutable) to a plain
    DateTimeField with a default so update_or_create can refresh the timestamp
    when stale results are replaced.
    """

    dependencies = [
        ("tracker", "0007_location_gf_verification"),
    ]

    operations = [
        migrations.AlterField(
            model_name="osmsearchcache",
            name="fetched_at",
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
    ]
