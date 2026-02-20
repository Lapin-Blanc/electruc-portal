"""Forms for public pages and client requests."""
from datetime import date

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone

from .models import CustomerProfile, Domiciliation, Invitation, MeterReading, MeterPoint, SupportRequest
from .validators import validate_upload_extension, validate_upload_size


class BootstrapFormMixin:
    """Apply Bootstrap-friendly classes to all fields."""

    def apply_bootstrap(self):
        for field in self.fields.values():
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{existing} form-control".strip()


class ContactForm(BootstrapFormMixin, forms.Form):
    """Simple contact form without business logic."""

    nom = forms.CharField(label="Nom", max_length=100)
    email = forms.EmailField(label="Adresse e-mail")
    message = forms.CharField(label="Message", widget=forms.Textarea, max_length=2000)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()


class RegistrationForm(BootstrapFormMixin, forms.Form):
    """Self-registration form based on invitation details."""

    ean = forms.CharField(label="Code EAN", max_length=30)
    secret_code = forms.CharField(label="Code d'activation unique", max_length=20)
    email = forms.EmailField(label="Adresse e-mail")
    password1 = forms.CharField(label="Mot de passe", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirmation du mot de passe", widget=forms.PasswordInput)

    error_messages = {
        "invalid_invitation": "Invitation invalide, expiree ou deja utilisee.",
        "locked_invitation": "Trop de tentatives. Reessayez dans 15 minutes.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()

    def clean(self):
        cleaned_data = super().clean()
        ean = (cleaned_data.get("ean") or "").strip()
        secret_code = (cleaned_data.get("secret_code") or "").strip().upper()
        email = (cleaned_data.get("email") or "").strip().lower()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1 and password2 and password1 != password2:
            self.add_error("password2", "Les mots de passe ne correspondent pas.")

        if password1:
            try:
                validate_password(password1)
            except forms.ValidationError as exc:
                self.add_error("password1", exc)

        if not ean or not secret_code or not email:
            return cleaned_data

        meter_point = MeterPoint.objects.filter(ean=ean).first()
        if not meter_point:
            raise forms.ValidationError(self.error_messages["invalid_invitation"])

        invitation = (
            Invitation.objects.filter(meter_point=meter_point)
            .order_by("-created_at")
            .first()
        )
        if (
            not invitation
            or invitation.used_at is not None
            or invitation.expires_at <= timezone.now()
        ):
            raise forms.ValidationError(self.error_messages["invalid_invitation"])

        if invitation.is_locked:
            raise forms.ValidationError(self.error_messages["locked_invitation"])

        if not invitation.check_secret_code(secret_code):
            invitation.register_failed_attempt()
            raise forms.ValidationError(self.error_messages["invalid_invitation"])

        user_model = get_user_model()
        user_by_email = (
            user_model.objects.filter(username__iexact=email).first()
            or user_model.objects.filter(email__iexact=email).first()
        )
        profile_for_ean = CustomerProfile.objects.filter(ean=meter_point.ean).select_related("user").first()

        existing_user = None
        if profile_for_ean:
            if user_by_email and user_by_email.id != profile_for_ean.user_id:
                self.add_error("email", "Cette adresse e-mail ne correspond pas au dossier client.")
                return cleaned_data
            existing_user = profile_for_ean.user
        elif user_by_email:
            existing_user = user_by_email

        if existing_user:
            if existing_user.is_active:
                self.add_error("email", "Cette adresse e-mail est deja utilisee.")
                return cleaned_data
            # Allow retry only for the same invitation reservation.
            if invitation.used_by_id and invitation.used_by_id != existing_user.id:
                raise forms.ValidationError(self.error_messages["invalid_invitation"])
            if invitation.used_by_id is None and profile_for_ean is None:
                self.add_error(
                    "email",
                    "Cette adresse e-mail est deja utilisee pour une activation en attente.",
                )
                return cleaned_data
        elif invitation.used_by_id:
            # Invitation already reserved by another account.
            raise forms.ValidationError(self.error_messages["invalid_invitation"])

        invitation.reset_failed_attempts()
        cleaned_data["email"] = email
        cleaned_data["secret_code"] = secret_code
        cleaned_data["meter_point"] = meter_point
        cleaned_data["invitation"] = invitation
        cleaned_data["existing_user"] = existing_user
        return cleaned_data


class MultiFileInput(forms.ClearableFileInput):
    """Allow selecting multiple files with a standard file widget."""

    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """File field that accepts a list of uploaded files."""

    def clean(self, data, initial=None):
        if not data:
            return []

        if not isinstance(data, (list, tuple)):
            data = [data]

        cleaned = []
        for item in data:
            cleaned.append(super().clean(item, initial))
        return cleaned


class SupportRequestForm(BootstrapFormMixin, forms.ModelForm):
    """Support request form with optional attachments."""

    attachments = MultipleFileField(
        label="Pieces jointes (optionnel)",
        required=False,
        help_text="Formats acceptes : PDF, PNG, JPG/JPEG, DOC, DOCX (max 5 Mo).",
        validators=[validate_upload_extension, validate_upload_size],
        widget=MultiFileInput(attrs={"multiple": True, "accept": ".pdf,.png,.jpg,.jpeg,.doc,.docx"}),
    )

    class Meta:
        model = SupportRequest
        fields = ["subject", "message"]
        labels = {"subject": "Objet", "message": "Message"}
        widgets = {"message": forms.Textarea}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()
        self.fields["attachments"].widget.attrs["class"] = "form-control"


class DomiciliationForm(BootstrapFormMixin, forms.ModelForm):
    """Domiciliation request form (document upload)."""

    class Meta:
        model = Domiciliation
        fields = ["document"]
        labels = {"document": "Document (PDF/DOC/DOCX/PNG/JPG)"}
        help_texts = {"document": "Formats acceptes : PDF, PNG, JPG/JPEG, DOC, DOCX (max 5 Mo)."}
        widgets = {
            "document": forms.ClearableFileInput(attrs={"accept": ".pdf,.png,.jpg,.jpeg,.doc,.docx"})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()
        self.fields["document"].widget.attrs["class"] = "form-control"


class ElectrucAuthenticationForm(BootstrapFormMixin, AuthenticationForm):
    """Authentication form with Bootstrap-friendly widgets."""

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request, *args, **kwargs)
        self.fields["username"].label = "Nom d'utilisateur (adresse mail)"
        self.apply_bootstrap()


class ProfileForm(BootstrapFormMixin, forms.ModelForm):
    """Editable customer profile fields."""

    email = forms.EmailField(label="Adresse e-mail", required=False)

    class Meta:
        model = CustomerProfile
        fields = [
            "billing_address_street",
            "billing_address_number",
            "billing_address_postal_code",
            "billing_address_city",
            "phone",
            "preferred_contact",
            "language",
        ]
        labels = {
            "billing_address_street": "Rue (facturation)",
            "billing_address_number": "Numero (facturation)",
            "billing_address_postal_code": "Code postal (facturation)",
            "billing_address_city": "Ville (facturation)",
            "phone": "Telephone",
            "preferred_contact": "Contact prefere",
            "language": "Langue",
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()
        if user:
            self.fields["email"].initial = user.email


class MeterReadingForm(BootstrapFormMixin, forms.ModelForm):
    """Form to submit a new meter reading."""

    class Meta:
        model = MeterReading
        fields = ["reading_date", "value_kwh"]
        labels = {"reading_date": "Date du releve", "value_kwh": "Index (kWh)"}
        widgets = {"reading_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        self.last_validated = kwargs.pop("last_validated", None)
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()

    def clean_reading_date(self):
        reading_date = self.cleaned_data["reading_date"]
        if self.last_validated and reading_date < self.last_validated.reading_date:
            raise forms.ValidationError("La date doit etre posterieure au dernier releve valide.")
        if reading_date > date.today():
            raise forms.ValidationError("La date ne peut pas etre dans le futur.")
        return reading_date

    def clean_value_kwh(self):
        value = self.cleaned_data["value_kwh"]
        if self.last_validated and value < self.last_validated.value_kwh:
            raise forms.ValidationError("L'index doit etre superieur ou egal au dernier releve valide.")
        return value
