"""Business models (simple and pedagogical)."""
from django.conf import settings
from django.db import models

from .validators import validate_upload_size, validate_upload_extension


class Contract(models.Model):
    """Energy supply contract linked to a user."""
    STATUS_ACTIVE = "active"
    STATUS_SUSPENDED = "suspended"
    STATUS_CLOSED = "closed"

    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Actif"),
        (STATUS_SUSPENDED, "Suspendu"),
        (STATUS_CLOSED, "Clôturé"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    reference = models.CharField(max_length=50, unique=True)
    start_date = models.DateField()
    plan_name = models.CharField(max_length=100)
    supply_address = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)

    def __str__(self) -> str:
        return f"{self.reference}"


class Invoice(models.Model):
    """Customer invoice linked to a user (no PDF file)."""
    STATUS_DUE = "due"
    STATUS_PAID = "paid"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_DUE, "À payer"),
        (STATUS_PAID, "Payée"),
        (STATUS_CANCELLED, "Annulée"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    reference = models.CharField(max_length=50)
    period_start = models.DateField()
    period_end = models.DateField()
    issue_date = models.DateField()
    amount_eur = models.DecimalField(max_digits=8, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DUE)
    pdf_file = models.FileField(
        upload_to="invoices/",
        blank=True,
        null=True,
        validators=[validate_upload_extension, validate_upload_size],
    )

    class Meta:
        ordering = ["-issue_date"]

    def __str__(self) -> str:
        return f"{self.reference}"


class MeterReading(models.Model):
    """Meter reading linked to a user."""
    STATUS_SUBMITTED = "submitted"
    STATUS_VALIDATED = "validated"
    STATUS_REJECTED = "rejected"

    STATUS_CHOICES = [
        (STATUS_SUBMITTED, "En cours de validation"),
        (STATUS_VALIDATED, "Validé"),
        (STATUS_REJECTED, "Refusé"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    reading_date = models.DateField()
    value_kwh = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_SUBMITTED)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-reading_date"]

    def __str__(self) -> str:
        return f"{self.reading_date}"


class SupportRequest(models.Model):
    """Support request linked to a user."""
    STATUS_OPEN = "open"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_CLOSED = "closed"

    STATUS_CHOICES = [
        (STATUS_OPEN, "Ouverte"),
        (STATUS_IN_PROGRESS, "En cours"),
        (STATUS_CLOSED, "Clôturée"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    subject = models.CharField(max_length=120)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.subject


class Domiciliation(models.Model):
    """Direct debit activation request linked to a user."""
    STATUS_PENDING = "pending"
    STATUS_ACTIVE = "active"
    STATUS_REJECTED = "rejected"

    STATUS_CHOICES = [
        (STATUS_PENDING, "En attente"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_REJECTED, "Refusée"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    document = models.FileField(
        upload_to="domiciliation/",
        validators=[validate_upload_extension, validate_upload_size],
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Domiciliation {self.user}"


class Attachment(models.Model):
    """Attachment linked to a support request (1-n)."""
    support_request = models.ForeignKey(SupportRequest, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(
        upload_to="support_attachments/",
        validators=[validate_upload_extension, validate_upload_size],
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self) -> str:
        return f"Pièce jointe {self.id}"


class CustomerProfile(models.Model):
    """Customer profile linked to a user (administrative data)."""
    CONTACT_EMAIL = "email"
    CONTACT_PHONE = "phone"

    CONTACT_CHOICES = [
        (CONTACT_EMAIL, "E-mail"),
        (CONTACT_PHONE, "Téléphone"),
    ]

    LANG_FR = "fr"
    LANG_NL = "nl"
    LANG_EN = "en"

    LANGUAGE_CHOICES = [
        (LANG_FR, "Français"),
        (LANG_NL, "Nederlands"),
        (LANG_EN, "English"),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    customer_ref = models.CharField(max_length=30, unique=True)
    ean = models.CharField(max_length=30, unique=True)
    supply_address_street = models.CharField(max_length=120)
    supply_address_number = models.CharField(max_length=20)
    supply_address_postal_code = models.CharField(max_length=10)
    supply_address_city = models.CharField(max_length=80)

    billing_address_street = models.CharField(max_length=120, blank=True)
    billing_address_number = models.CharField(max_length=20, blank=True)
    billing_address_postal_code = models.CharField(max_length=10, blank=True)
    billing_address_city = models.CharField(max_length=80, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    preferred_contact = models.CharField(max_length=10, choices=CONTACT_CHOICES, default=CONTACT_EMAIL)
    language = models.CharField(max_length=5, choices=LANGUAGE_CHOICES, default=LANG_FR)

    def __str__(self) -> str:
        return f"{self.customer_ref}"
