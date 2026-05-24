from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tracker", "0005_osmsearchcache"),
    ]

    operations = [
        migrations.AddField(
            model_name="location",
            name="gluten_free",
            field=models.CharField(
                blank=True,
                choices=[
                    ("",          "Unknown"),
                    ("dedicated", "Dedicated GF kitchen (celiac-safe)"),
                    ("options",   "GF options available (shared kitchen)"),
                    ("limited",   "Limited GF (e.g. remove the bun)"),
                    ("none",      "No gluten-free options"),
                ],
                default="",
                help_text="Gluten-free accommodation level",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="location",
            name="dietary_notes",
            field=models.TextField(
                blank=True,
                help_text="Dietary notes: allergies, cross-contamination info, etc.",
            ),
        ),
    ]
