# Generated manually for customer profiles and meter reading updates.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def migrate_reading_status(apps, schema_editor):
    MeterReading = apps.get_model("portal", "MeterReading")
    MeterReading.objects.filter(status="recorded").update(status="submitted")


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0002_uploads_and_domiciliation"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="meterreading",
            name="note",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AlterField(
            model_name="meterreading",
            name="status",
            field=models.CharField(
                choices=[
                    ("submitted", "En cours de validation"),
                    ("validated", "Validé"),
                    ("rejected", "Refusé"),
                ],
                default="submitted",
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="CustomerProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("customer_ref", models.CharField(max_length=30, unique=True)),
                ("ean", models.CharField(max_length=30, unique=True)),
                ("supply_address_street", models.CharField(max_length=120)),
                ("supply_address_number", models.CharField(max_length=20)),
                ("supply_address_postal_code", models.CharField(max_length=10)),
                ("supply_address_city", models.CharField(max_length=80)),
                ("billing_address_street", models.CharField(blank=True, max_length=120)),
                ("billing_address_number", models.CharField(blank=True, max_length=20)),
                ("billing_address_postal_code", models.CharField(blank=True, max_length=10)),
                ("billing_address_city", models.CharField(blank=True, max_length=80)),
                ("phone", models.CharField(blank=True, max_length=30)),
                (
                    "preferred_contact",
                    models.CharField(
                        choices=[("email", "E-mail"), ("phone", "Téléphone")],
                        default="email",
                        max_length=10,
                    ),
                ),
                (
                    "language",
                    models.CharField(
                        choices=[("fr", "Français"), ("nl", "Nederlands"), ("en", "English")],
                        default="fr",
                        max_length=5,
                    ),
                ),
                (
                    "user",
                    models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
                ),
            ],
        ),
        migrations.RunPython(migrate_reading_status, migrations.RunPython.noop),
    ]
