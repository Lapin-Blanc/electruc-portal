# Generated manually for additional profile fields.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0003_customer_profile_and_readings"),
    ]

    operations = [
        migrations.AddField(
            model_name="customerprofile",
            name="meter_serial",
            field=models.CharField(blank=True, max_length=30),
        ),
        migrations.AddField(
            model_name="customerprofile",
            name="notes_admin",
            field=models.TextField(blank=True),
        ),
    ]
