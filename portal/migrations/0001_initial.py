# Generated manually for initial portal models (T4).
from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Contract",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reference", models.CharField(max_length=50, unique=True)),
                ("start_date", models.DateField()),
                ("plan_name", models.CharField(max_length=100)),
                ("supply_address", models.CharField(max_length=200)),
                (
                    "status",
                    models.CharField(
                        choices=[("active", "Actif"), ("suspended", "Suspendu"), ("closed", "Clôturé")],
                        default="active",
                        max_length=20,
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Invoice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reference", models.CharField(max_length=50)),
                ("period_start", models.DateField()),
                ("period_end", models.DateField()),
                ("issue_date", models.DateField()),
                ("amount_eur", models.DecimalField(decimal_places=2, max_digits=8)),
                (
                    "status",
                    models.CharField(
                        choices=[("due", "À payer"), ("paid", "Payée"), ("cancelled", "Annulée")],
                        default="due",
                        max_length=20,
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={
                "ordering": ["-issue_date"],
            },
        ),
        migrations.CreateModel(
            name="MeterReading",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reading_date", models.DateField()),
                ("value_kwh", models.PositiveIntegerField()),
                (
                    "status",
                    models.CharField(
                        choices=[("recorded", "Enregistré"), ("validated", "Validé")],
                        default="recorded",
                        max_length=20,
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={
                "ordering": ["-reading_date"],
            },
        ),
        migrations.CreateModel(
            name="SupportRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("subject", models.CharField(max_length=120)),
                ("message", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "status",
                    models.CharField(
                        choices=[("open", "Ouverte"), ("in_progress", "En cours"), ("closed", "Clôturée")],
                        default="open",
                        max_length=20,
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
