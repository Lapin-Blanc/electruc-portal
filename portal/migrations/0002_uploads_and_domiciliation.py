# Generated manually for T5 uploads and additional models.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import portal.validators


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="invoice",
            name="pdf_file",
            field=models.FileField(
                blank=True,
                null=True,
                upload_to="invoices/",
                validators=[
                    portal.validators.validate_upload_extension,
                    portal.validators.validate_upload_size,
                ],
            ),
        ),
        migrations.CreateModel(
            name="Domiciliation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "En attente"), ("active", "Active"), ("rejected", "Refusée")],
                        default="pending",
                        max_length=20,
                    ),
                ),
                (
                    "document",
                    models.FileField(
                        upload_to="domiciliation/",
                        validators=[
                            portal.validators.validate_upload_extension,
                            portal.validators.validate_upload_size,
                        ],
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
        migrations.CreateModel(
            name="Attachment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "file",
                    models.FileField(
                        upload_to="support_attachments/",
                        validators=[
                            portal.validators.validate_upload_extension,
                            portal.validators.validate_upload_size,
                        ],
                    ),
                ),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                (
                    "support_request",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="attachments", to="portal.supportrequest"),
                ),
            ],
            options={
                "ordering": ["-uploaded_at"],
            },
        ),
    ]
