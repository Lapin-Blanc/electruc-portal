"""Admin registrations for portal models."""
from django.contrib import admin

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
    list_display = ("customer_ref", "user", "ean", "preferred_contact", "language")
    search_fields = ("customer_ref", "ean", "user__username", "user__email")
