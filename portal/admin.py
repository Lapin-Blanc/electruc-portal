"""Admin registrations for portal models."""
from django import forms
from django.contrib import admin, messages
from django.urls import path
from django.shortcuts import render, redirect
import csv
from datetime import date, timedelta
from decimal import Decimal
import random

from .models import (
    Attachment,
    Contract,
    CustomerProfile,
    Domiciliation,
    Invoice,
    MeterReading,
    SupportRequest,
)


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ("reference", "user", "plan_name", "status", "start_date")
    list_filter = ("status",)
    search_fields = ("reference", "user__username", "user__email")


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
        queryset.update(status=MeterReading.STATUS_REJECTED, note="Relevé à vérifier.")

    mark_validated.short_description = "Marquer comme validé"
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
    change_list_template = "admin/portal/customerprofile/change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path("import-csv/", self.admin_site.admin_view(self.import_csv), name="portal_customerprofile_import"),
        ]
        return custom + urls

    def import_csv(self, request):
        if request.method == "POST":
            form = CSVImportForm(request.POST, request.FILES)
            if form.is_valid():
                created_count = 0
                updated_count = 0
                errors = 0
                file_obj = form.cleaned_data["csv_file"]
                decoded = file_obj.read().decode("utf-8", errors="ignore").splitlines()
                reader = csv.DictReader(decoded)
                for row in reader:
                    try:
                        created, updated = import_customer_row(row)
                        created_count += int(created)
                        updated_count += int(updated)
                    except Exception:
                        errors += 1
                        continue
                messages.success(
                    request,
                    f"Import terminé. Créés: {created_count}, mis à jour: {updated_count}, erreurs: {errors}.",
                )
                return redirect("..")
        else:
            form = CSVImportForm()
        context = dict(
            self.admin_site.each_context(request),
            form=form,
        )
        return render(request, "admin/portal/customerprofile/import_csv.html", context)


class CSVImportForm(forms.Form):
    csv_file = forms.FileField(label="Fichier CSV")


def parse_bool(value):
    return str(value).strip().lower() in {"1", "true", "yes", "y", "oui"}


def import_customer_row(row):
    from django.contrib.auth import get_user_model
    from .models import Contract, CustomerProfile, Invoice, MeterReading

    User = get_user_model()

    username = row.get("username", "").strip()
    if not username:
        raise ValueError("Username manquant")

    user, created = User.objects.get_or_create(username=username)
    user.first_name = row.get("firstname", "").strip()
    user.last_name = row.get("lastname", "").strip()
    user.email = row.get("email", "").strip()
    password = row.get("password", "").strip()
    if password:
        user.set_password(password)
    user.save()

    supply_street = row.get("supply_address", "").strip()
    supply_number = ""
    if supply_street:
        parts = supply_street.rsplit(" ", 1)
        if len(parts) == 2:
            supply_street, supply_number = parts

    billing_same = parse_bool(row.get("billing_address_same_as_supply", ""))

    profile_defaults = {
        "customer_ref": row.get("customer_ref", "").strip() or f"CLI-{user.id:05d}",
        "ean": row.get("meter_ean", "").strip() or f"54{user.id:016d}",
        "meter_serial": row.get("meter_serial", "").strip(),
        "supply_address_street": supply_street,
        "supply_address_number": supply_number,
        "supply_address_postal_code": row.get("supply_postcode", "").strip(),
        "supply_address_city": row.get("supply_city", "").strip(),
        "billing_address_street": supply_street if billing_same else "",
        "billing_address_number": supply_number if billing_same else "",
        "billing_address_postal_code": row.get("supply_postcode", "").strip() if billing_same else "",
        "billing_address_city": row.get("supply_city", "").strip() if billing_same else "",
        "phone": row.get("phone_mobile", "").strip() or row.get("phone_landline", "").strip(),
        "preferred_contact": CustomerProfile.CONTACT_EMAIL,
        "language": (row.get("lang", "").strip() or CustomerProfile.LANG_FR),
        "notes_admin": row.get("notes_admin", "").strip(),
    }

    if profile_defaults["language"] not in {c[0] for c in CustomerProfile.LANGUAGE_CHOICES}:
        profile_defaults["language"] = CustomerProfile.LANG_FR

    profile, profile_created = CustomerProfile.objects.update_or_create(
        user=user,
        defaults=profile_defaults,
    )

    status_map = {
        "actif": Contract.STATUS_ACTIVE,
        "suspendu": Contract.STATUS_SUSPENDED,
        "cloture": Contract.STATUS_CLOSED,
        "clôturé": Contract.STATUS_CLOSED,
    }
    contract_status = status_map.get(row.get("status", "").strip().lower(), Contract.STATUS_ACTIVE)
    contract_start = row.get("contract_start_date", "").strip()
    try:
        start_date = date.fromisoformat(contract_start)
    except ValueError:
        start_date = date.today()

    contract_reference = f"CTR-{profile.customer_ref}"
    Contract.objects.update_or_create(
        user=user,
        reference=contract_reference,
        defaults={
            "start_date": start_date,
            "plan_name": row.get("contract_plan", "").strip() or "Offre Standard",
            "supply_address": f"{supply_street} {supply_number}, {profile.supply_address_postal_code} {profile.supply_address_city}".strip(),
            "status": contract_status,
        },
    )

    # Recreate demo invoices and readings for a clean dataset.
    Invoice.objects.filter(user=user).delete()
    MeterReading.objects.filter(user=user).delete()

    for month_offset in range(3):
        period_end = date.today().replace(day=1) - timedelta(days=1 + month_offset * 30)
        period_start = period_end - timedelta(days=29)
        issue_date = period_end + timedelta(days=3)
        amount = Decimal(random.randint(45, 120))
        Invoice.objects.create(
            user=user,
            reference=f"FAC-{profile.customer_ref}-{month_offset + 1:02d}",
            period_start=period_start,
            period_end=period_end,
            issue_date=issue_date,
            amount_eur=amount,
            status=Invoice.STATUS_PAID if month_offset > 0 else Invoice.STATUS_DUE,
        )

    for offset in range(2):
        MeterReading.objects.create(
            user=user,
            reading_date=date.today() - timedelta(days=60 * (offset + 1)),
            value_kwh=1200 + offset * 150,
            status=MeterReading.STATUS_VALIDATED,
        )

    MeterReading.objects.create(
        user=user,
        reading_date=date.today() - timedelta(days=10),
        value_kwh=1500,
        status=MeterReading.STATUS_SUBMITTED,
    )

    return profile_created, not profile_created
