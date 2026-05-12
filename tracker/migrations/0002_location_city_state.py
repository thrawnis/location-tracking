from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tracker", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="location",
            name="city",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="location",
            name="state",
            field=models.CharField(blank=True, max_length=100),
        ),
    ]
