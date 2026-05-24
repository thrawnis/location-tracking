from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tracker", "0003_itemreview"),
    ]

    operations = [
        migrations.AddField(
            model_name="location",
            name="phone",
            field=models.CharField(blank=True, help_text="Phone number", max_length=50),
        ),
        migrations.AddField(
            model_name="location",
            name="website",
            field=models.URLField(blank=True, help_text="Website URL", max_length=500),
        ),
        migrations.AddField(
            model_name="location",
            name="hours",
            field=models.TextField(blank=True, help_text="Opening hours (e.g. Mon-Fri 9am-5pm)"),
        ),
    ]
