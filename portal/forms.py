"""Forms for public pages and client requests."""
from django import forms

from datetime import date

from django.contrib.auth.forms import AuthenticationForm

from .models import CustomerProfile, Domiciliation, MeterReading, SupportRequest
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
        label="Pièces jointes (optionnel)",
        required=False,
        help_text="Formats acceptés : PDF, PNG, JPG/JPEG, DOC, DOCX (max 5 Mo).",
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
        help_texts = {"document": "Formats acceptés : PDF, PNG, JPG/JPEG, DOC, DOCX (max 5 Mo)."}
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
            "billing_address_number": "Numéro (facturation)",
            "billing_address_postal_code": "Code postal (facturation)",
            "billing_address_city": "Ville (facturation)",
            "phone": "Téléphone",
            "preferred_contact": "Contact préféré",
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
        labels = {"reading_date": "Date du relevé", "value_kwh": "Index (kWh)"}
        widgets = {"reading_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        self.last_validated = kwargs.pop("last_validated", None)
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()

    def clean_reading_date(self):
        reading_date = self.cleaned_data["reading_date"]
        if self.last_validated and reading_date < self.last_validated.reading_date:
            raise forms.ValidationError("La date doit être postérieure au dernier relevé validé.")
        if reading_date > date.today():
            raise forms.ValidationError("La date ne peut pas être dans le futur.")
        return reading_date

    def clean_value_kwh(self):
        value = self.cleaned_data["value_kwh"]
        if self.last_validated and value < self.last_validated.value_kwh:
            raise forms.ValidationError("L'index doit être supérieur ou égal au dernier relevé validé.")
        return value
