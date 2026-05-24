from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tracker", "0004_location_contact_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="OsmSearchCache",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("query",      models.CharField(db_index=True, max_length=255)),
                ("center_lat", models.DecimalField(decimal_places=2, max_digits=7)),
                ("center_lng", models.DecimalField(decimal_places=2, max_digits=8)),
                ("radius_m",   models.IntegerField()),
                ("results",    models.JSONField(default=list)),
                ("fetched_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-fetched_at"],
                "unique_together": {("query", "center_lat", "center_lng", "radius_m")},
            },
        ),
    ]
