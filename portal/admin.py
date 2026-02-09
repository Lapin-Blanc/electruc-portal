"""Admin registrations for portal models."""
import csv
import calendar
import random
from datetime import date
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.http import HttpResponse
from django.contrib.auth import get_user_model
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils import timezone

from .models import (
    Attachment,
    Contract,
    CustomerProfile,
    Domiciliation,
    Invitation,
    Invoice,
    MeterPoint,
    MeterPointHistory,
    MeterReading,
    SupportRequest,
)


class MeterPointCSVImportForm(forms.Form):
    csv_file = forms.FileField(label="Fichier CSV")


def _read_csv_rows_from_text(text):
    return csv.DictReader(text.splitlines())


def _decode_csv_bytes(raw_bytes: bytes) -> str:
    """Decode CSV with common encodings while preserving accented characters."""
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw_bytes.decode("utf-8", errors="replace")


def _month_period(anchor: date, month_offset: int):
    target_month = anchor.month + month_offset
    target_year = anchor.year + (target_month - 1) // 12
    target_month = ((target_month - 1) % 12) + 1
    period_start = date(target_year, target_month, 1)
    last_day = calendar.monthrange(target_year, target_month)[1]
    period_end = date(target_year, target_month, last_day)
    return period_start, period_end


def ensure_meter_point_history(meter_point, months=5):
    today = timezone.localdate()
    # Build history for the 5 closed months preceding the import date.
    for offset in range(-months, 0):
        period_start, period_end = _month_period(today, offset)
        seed = f"{meter_point.ean}-{period_start.isoformat()}"
        rng = random.Random(seed)
        consumption = rng.randint(180, 520)
        amount = (Decimal(consumption) * Decimal("0.28")).quantize(Decimal("0.01"))
        MeterPointHistory.objects.update_or_create(
            meter_point=meter_point,
            period_start=period_start,
            defaults={
                "period_end": period_end,
                "reading_date": period_end,
                "consumption_kwh": consumption,
                "amount_eur": amount,
            },
        )


def import_meter_point_row(row):
    ean = (row.get("meter_ean") or row.get("ean") or "").strip()
    if not ean:
        raise ValueError("EAN manquant")

    supply_address = (row.get("supply_address") or "").strip()
    postal_code = (row.get("supply_postcode") or "").strip()
    city = (row.get("supply_city") or "").strip()

    defaults = {
        "address_line1": supply_address,
        "address_line2": "",
        "postal_code": postal_code,
        "city": city,
        "country": "BE",
        "holder_firstname": (row.get("firstname") or "").strip(),
        "holder_lastname": (row.get("lastname") or "").strip(),
    }

    meter_point, created = MeterPoint.objects.update_or_create(
        ean=ean,
        defaults=defaults,
    )
    ensure_meter_point_history(meter_point)
    return created, not created


def import_meter_points_from_reader(reader):
    created_count = 0
    updated_count = 0
    errors = 0

    for row in reader:
        if not any((value or "").strip() for value in row.values()):
            continue
        try:
            created, updated = import_meter_point_row(row)
            created_count += int(created)
            updated_count += int(updated)
        except Exception:
            errors += 1

    return created_count, updated_count, errors


def reset_online_accounts():
    now = timezone.now()
    User = get_user_model()

    invitation_user_ids = list(
        Invitation.objects.filter(used_by__isnull=False).values_list("used_by_id", flat=True).distinct()
    )
    contract_user_ids = list(
        Contract.objects.filter(meter_point__isnull=False).values_list("user_id", flat=True).distinct()
    )
    user_ids = sorted(set(invitation_user_ids + contract_user_ids))

    users_qs = User.objects.filter(id__in=user_ids, is_staff=False, is_superuser=False)
    deleted_users_count = users_qs.count()
    if deleted_users_count:
        users_qs.delete()

    reset_qs = Invitation.objects.filter(meter_point__isnull=False).exclude(
        used_at=None,
        used_by=None,
        failed_attempts=0,
        locked_until=None,
    )
    reset_invitations_count = reset_qs.count()
    if reset_invitations_count:
        reset_qs.update(
            used_at=None,
            used_by=None,
            failed_attempts=0,
            locked_until=None,
            expires_at=now + timedelta(days=30),
        )

    return deleted_users_count, reset_invitations_count


def _get_reportlab():
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas
    except ModuleNotFoundError:
        return None, None, None
    return A4, mm, canvas


def _build_invitations_multipage_pdf(request, items):
    A4, mm, canvas = _get_reportlab()
    if not canvas:
        content_lines = ["Invitations Electruc"]
        for item in items:
            content_lines.append(
                f"{item['holder_name']} | EAN: {item['ean']} | Code: {item['secret_code']} | URL: {item['registration_url']}"
            )
        response = HttpResponse("\n".join(content_lines), content_type="text/plain; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="invitations_electruc.txt"'
        return response

    from io import BytesIO

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    _, height = A4

    for item in items:
        y = height - 20 * mm
        pdf.setFont("Helvetica-Bold", 15)
        pdf.drawString(20 * mm, y, "Courrier d'invitation - Espace client Electruc")
        y -= 12 * mm

        pdf.setFont("Helvetica", 10)
        pdf.drawString(20 * mm, y, f"Destinataire: {item['holder_name']}")
        y -= 6 * mm
        pdf.drawString(20 * mm, y, f"Adresse: {item['address_line1']}")
        y -= 6 * mm
        if item["address_line2"]:
            pdf.drawString(20 * mm, y, item["address_line2"])
            y -= 6 * mm
        pdf.drawString(20 * mm, y, f"{item['postal_code']} {item['city']} - {item['country']}")

        y -= 12 * mm
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(20 * mm, y, f"Code EAN: {item['ean']}")
        y -= 10 * mm
        pdf.drawString(20 * mm, y, f"Code secret: {item['secret_code']}")
        y -= 10 * mm
        pdf.setFont("Helvetica", 10)
        pdf.drawString(20 * mm, y, f"URL inscription: {item['registration_url']}")
        y -= 8 * mm
        pdf.drawString(20 * mm, y, f"Valable jusqu'au: {item['expires_at']:%d/%m/%Y %H:%M}")

        y -= 14 * mm
        pdf.setFont("Helvetica", 9)
        pdf.drawString(
            20 * mm,
            y,
            "Le code EAN et le code secret sont necessaires pour creer le compte en ligne.",
        )
        pdf.drawString(20 * mm, 18 * mm, "Document de demonstration - diffusion interne atelier.")
        pdf.showPage()

    pdf.save()
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="invitations_electruc.pdf"'
    return response


def reset_workshop_data():
    """Reset workshop state while keeping imported meter points."""
    now = timezone.now()
    deleted_users_count, _ = reset_online_accounts()

    # Reset all invitations to a clean state for a new classroom session.
    reset_invitations_count = Invitation.objects.count()
    Invitation.objects.update(
        used_at=None,
        used_by=None,
        failed_attempts=0,
        locked_until=None,
        expires_at=now + timedelta(days=30),
    )

    return deleted_users_count, reset_invitations_count


@admin.register(MeterPoint)
class MeterPointAdmin(admin.ModelAdmin):
    list_display = ("ean", "holder_lastname", "holder_firstname", "postal_code", "city", "country")
    search_fields = ("ean", "holder_lastname", "holder_firstname", "address_line1", "city")
    actions = ["generate_invitation_action", "generate_invitations_pdf_action"]
    change_list_template = "admin/portal/meterpoint/change_list.html"

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ("ean",)
        return ()

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "<int:meter_point_id>/invitation-letter/",
                self.admin_site.admin_view(self.invitation_letter_view),
                name="portal_meterpoint_invitation_letter",
            ),
            path("import-csv/", self.admin_site.admin_view(self.import_csv_view), name="portal_meterpoint_import_csv"),
            path(
                "import-default-csv/",
                self.admin_site.admin_view(self.import_default_csv_view),
                name="portal_meterpoint_import_default_csv",
            ),
            path(
                "reset-online-accounts/",
                self.admin_site.admin_view(self.reset_online_accounts_view),
                name="portal_meterpoint_reset_online_accounts",
            ),
            path(
                "reset-workshop/",
                self.admin_site.admin_view(self.reset_workshop_view),
                name="portal_meterpoint_reset_workshop",
            ),
        ]
        return custom + urls

    def generate_invitation_action(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(
                request,
                "Selectionnez un seul point de fourniture pour generer un courrier d'invitation.",
                level=messages.WARNING,
            )
            return None

        meter_point = queryset.first()
        url = reverse("admin:portal_meterpoint_invitation_letter", args=[meter_point.id])
        return redirect(url)

    generate_invitation_action.short_description = "Générer invitation"

    def generate_invitations_pdf_action(self, request, queryset):
        if not queryset.exists():
            self.message_user(request, "Aucun point de fourniture selectionne.", level=messages.WARNING)
            return None

        now = timezone.now()
        registration_url = request.build_absolute_uri(reverse("registration_start"))
        items = []

        for meter_point in queryset.order_by("ean"):
            Invitation.objects.filter(
                meter_point=meter_point,
                used_at__isnull=True,
                expires_at__gt=now,
            ).update(expires_at=now)

            invitation, secret_code = Invitation.create_with_secret(
                meter_point=meter_point,
                expires_at=now + timedelta(days=30),
            )
            items.append(
                {
                    "holder_name": meter_point.holder_full_name,
                    "address_line1": meter_point.address_line1,
                    "address_line2": meter_point.address_line2,
                    "postal_code": meter_point.postal_code,
                    "city": meter_point.city,
                    "country": meter_point.country,
                    "ean": meter_point.ean,
                    "secret_code": secret_code,
                    "registration_url": registration_url,
                    "expires_at": invitation.expires_at,
                }
            )

        return _build_invitations_multipage_pdf(request, items)

    generate_invitations_pdf_action.short_description = "Générer invitations PDF (multi-sélection)"

    def invitation_letter_view(self, request, meter_point_id):
        meter_point = self.get_object(request, meter_point_id)
        if not meter_point:
            self.message_user(request, "Point de fourniture introuvable.", level=messages.ERROR)
            return redirect("admin:portal_meterpoint_changelist")

        now = timezone.now()
        Invitation.objects.filter(
            meter_point=meter_point,
            used_at__isnull=True,
            expires_at__gt=now,
        ).update(expires_at=now)

        invitation, secret_code = Invitation.create_with_secret(
            meter_point=meter_point,
            expires_at=now + timedelta(days=30),
        )

        registration_url = request.build_absolute_uri(reverse("registration_start"))
        context = {
            **self.admin_site.each_context(request),
            "meter_point": meter_point,
            "invitation": invitation,
            "secret_code": secret_code,
            "registration_url": registration_url,
        }
        return render(request, "admin/portal/meterpoint/invitation_letter.html", context)

    def import_csv_view(self, request):
        if request.method == "POST":
            form = MeterPointCSVImportForm(request.POST, request.FILES)
            if form.is_valid():
                file_obj = form.cleaned_data["csv_file"]
                decoded = _decode_csv_bytes(file_obj.read())
                created_count, updated_count, errors = import_meter_points_from_reader(_read_csv_rows_from_text(decoded))
                messages.success(
                    request,
                    f"Import terminé. Points créés: {created_count}, mis à jour: {updated_count}, erreurs: {errors}.",
                )
                return redirect("..")
        else:
            form = MeterPointCSVImportForm()

        context = {
            **self.admin_site.each_context(request),
            "form": form,
        }
        return render(request, "admin/portal/meterpoint/import_csv.html", context)

    def import_default_csv_view(self, request):
        csv_path = (getattr(settings, "TRAINING_CUSTOMERS_CSV_PATH", "") or "").strip()
        if not csv_path:
            messages.error(request, "TRAINING_CUSTOMERS_CSV_PATH n'est pas configuré dans l'environnement.")
            return redirect("..")

        file_path = Path(csv_path)
        if not file_path.exists():
            messages.error(request, f"Fichier CSV introuvable: {file_path}")
            return redirect("..")

        decoded = _decode_csv_bytes(file_path.read_bytes())
        created_count, updated_count, errors = import_meter_points_from_reader(_read_csv_rows_from_text(decoded))
        messages.success(
            request,
            f"Import automatique terminé. Points créés: {created_count}, mis à jour: {updated_count}, erreurs: {errors}.",
        )
        return redirect("..")

    def reset_online_accounts_view(self, request):
        if request.method == "POST":
            deleted_users_count, reset_invitations_count = reset_online_accounts()
            messages.success(
                request,
                "Réinitialisation terminée. "
                f"Comptes supprimés: {deleted_users_count}. "
                f"Invitations réinitialisées: {reset_invitations_count}.",
            )
            return redirect("..")

        context = {
            **self.admin_site.each_context(request),
        }
        return render(request, "admin/portal/meterpoint/reset_online_accounts.html", context)

    def reset_workshop_view(self, request):
        if request.method == "POST":
            deleted_users_count, reset_invitations_count = reset_workshop_data()
            messages.success(
                request,
                "Réinitialisation atelier terminée. "
                f"Comptes supprimés: {deleted_users_count}. "
                f"Invitations réinitialisées: {reset_invitations_count}.",
            )
            return redirect("..")

        context = {
            **self.admin_site.each_context(request),
        }
        return render(request, "admin/portal/meterpoint/reset_workshop.html", context)


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = (
        "meter_point",
        "created_at",
        "expires_at",
        "used_at",
        "used_by",
        "failed_attempts",
        "locked_until",
    )
    list_filter = ("used_at", "expires_at")
    search_fields = ("meter_point__ean", "used_by__username", "used_by__email")
    readonly_fields = (
        "secret_code_hash",
        "created_at",
        "failed_attempts",
        "locked_until",
    )


@admin.register(MeterPointHistory)
class MeterPointHistoryAdmin(admin.ModelAdmin):
    list_display = ("meter_point", "period_start", "period_end", "consumption_kwh", "amount_eur")
    list_filter = ("period_start",)
    search_fields = ("meter_point__ean",)


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ("reference", "user", "meter_point", "plan_name", "status", "start_date")
    list_filter = ("status",)
    search_fields = ("reference", "user__username", "user__email", "meter_point__ean")


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("reference", "user", "issue_date", "amount_eur", "status")
    list_filter = ("status",)
    search_fields = ("reference", "user__username", "user__email")


@admin.register(MeterReading)
class MeterReadingAdmin(admin.ModelAdmin):
    list_display = ("user", "reading_date", "value_kwh", "status", "note")
    list_filter = ("status",)
    search_fields = ("user__username", "user__email")
    actions = ["mark_validated", "mark_rejected"]

    def mark_validated(self, request, queryset):
        queryset.update(status=MeterReading.STATUS_VALIDATED, note="")

    def mark_rejected(self, request, queryset):
        queryset.update(status=MeterReading.STATUS_REJECTED, note="Releve a verifier.")

    mark_validated.short_description = "Marquer comme valide"
    mark_rejected.short_description = "Marquer comme refusé"


@admin.register(SupportRequest)
class SupportRequestAdmin(admin.ModelAdmin):
    list_display = ("subject", "user", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("subject", "user__username", "user__email")


@admin.register(Domiciliation)
class DomiciliationAdmin(admin.ModelAdmin):
    list_display = ("user", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("user__username", "user__email")


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ("support_request", "uploaded_at")


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ("customer_ref", "user", "ean", "meter_serial", "preferred_contact", "language")
    search_fields = ("customer_ref", "ean", "user__username", "user__email")
