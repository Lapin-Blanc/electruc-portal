"""Views for the portal app (public pages + client area + self-registration)."""
import json
from io import BytesIO
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.contrib.staticfiles import finders
from django.core.mail import send_mail
from django.db import transaction
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from .forms import (
    ContactForm,
    DomiciliationForm,
    MeterReadingForm,
    ProfileForm,
    RegistrationForm,
    SupportRequestForm,
)
from .models import (
    Attachment,
    Contract,
    CustomerProfile,
    Domiciliation,
    Invitation,
    Invoice,
    MeterPointHistory,
    MeterReading,
    SupportRequest,
)


def _get_reportlab():
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas
    except ModuleNotFoundError:
        return None, None, None
    return A4, mm, canvas


def _build_fallback_pdf(document_title: str, lines=None) -> bytes:
    """Build a minimal valid PDF without external dependencies."""
    lines = lines or []

    def _escape_pdf_text(text):
        return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    content_rows = [
        "BT",
        "/F1 16 Tf",
        "50 800 Td",
        f"({_escape_pdf_text(document_title)}) Tj",
        "ET",
    ]
    y = 770
    for row in lines[:20]:
        content_rows.extend(
            [
                "BT",
                "/F1 11 Tf",
                f"50 {y} Td",
                f"({_escape_pdf_text(str(row))}) Tj",
                "ET",
            ]
        )
        y -= 18
    stream = "\n".join(content_rows).encode("latin-1", errors="replace")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(stream)} >>\nstream\n".encode("ascii") + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for idx, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{idx} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")

    xref_pos = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n".encode("ascii"))
    pdf.extend(f"startxref\n{xref_pos}\n%%EOF\n".encode("ascii"))
    return bytes(pdf)


def _draw_pdf_header(pdf, mm, title: str):
    logo_path = finders.find("branding/logo-transparent.png") or finders.find("branding/logo.png")
    if logo_path:
        pdf.drawImage(
            logo_path,
            20 * mm,
            268 * mm,
            width=57 * mm,
            height=18 * mm,
            preserveAspectRatio=True,
            mask="auto",
            anchor="sw",
        )
    else:
        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawString(20 * mm, 277 * mm, "Electruc")

    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawRightString(190 * mm, 285 * mm, "Electruc SA")
    pdf.setFont("Helvetica", 9)
    pdf.drawRightString(190 * mm, 280 * mm, "Avenue des Services 100")
    pdf.drawRightString(190 * mm, 275 * mm, "1000 Bruxelles - Belgique")
    pdf.drawRightString(190 * mm, 270 * mm, "TVA BE0123.456.789")

    pdf.setStrokeColorRGB(0.85, 0.88, 0.9)
    pdf.line(20 * mm, 266 * mm, 190 * mm, 266 * mm)

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(20 * mm, 258 * mm, title)


def home(request):
    """Public landing page."""
    return render(request, "portal/home.html")


def services(request):
    """Public services page."""
    return render(request, "portal/services.html")


def faq(request):
    """Public help/FAQ page."""
    return render(request, "portal/faq.html")


def contact(request):
    """Public contact page with a simple form (no email sending)."""
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            messages.success(request, "Votre message a bien ete recu.")
            form = ContactForm()
    else:
        form = ContactForm()

    return render(request, "portal/contact.html", {"form": form})


def _materialize_meter_history_for_user(user, meter_point):
    history_items = list(MeterPointHistory.objects.filter(meter_point=meter_point).order_by("period_start"))
    total_items = len(history_items)
    for index, item in enumerate(history_items, start=1):
        invoice_ref = f"FAC-SELF-{user.id:06d}-{item.period_start:%Y%m}"
        Invoice.objects.update_or_create(
            user=user,
            reference=invoice_ref,
            defaults={
                "period_start": item.period_start,
                "period_end": item.period_end,
                "issue_date": item.period_end + timezone.timedelta(days=3),
                "amount_eur": item.amount_eur,
                "status": Invoice.STATUS_PAID if index < total_items else Invoice.STATUS_DUE,
            },
        )
        MeterReading.objects.update_or_create(
            user=user,
            reading_date=item.reading_date,
            defaults={
                "value_kwh": item.consumption_kwh,
                "status": MeterReading.STATUS_VALIDATED,
                "note": "Historique importe",
            },
        )


def registration_start(request):
    """Self-registration using EAN + invitation secret code."""
    if request.user.is_authenticated:
        return redirect("client_dashboard")

    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            invitation = form.cleaned_data["invitation"]
            meter_point = form.cleaned_data["meter_point"]
            email = form.cleaned_data["email"]
            password = form.cleaned_data["password1"]

            with transaction.atomic():
                user_model = get_user_model()
                user = user_model.objects.create_user(
                    username=email,
                    email=email,
                    password=password,
                    is_active=False,
                    first_name=meter_point.holder_firstname,
                    last_name=meter_point.holder_lastname,
                )

                invitation.used_by = user
                invitation.save(update_fields=["used_by"])

                Contract.objects.update_or_create(
                    user=user,
                    defaults={
                        "reference": f"CTR-SELF-{user.id:06d}",
                        "start_date": timezone.localdate(),
                        "plan_name": "Offre Standard",
                        "supply_address": meter_point.full_address,
                        "status": Contract.STATUS_ACTIVE,
                        "meter_point": meter_point,
                    },
                )

                CustomerProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        "customer_ref": f"CLI-SELF-{user.id:06d}",
                        "ean": meter_point.ean,
                        "supply_address_street": meter_point.address_line1,
                        "supply_address_number": meter_point.address_line2 or "",
                        "supply_address_postal_code": meter_point.postal_code,
                        "supply_address_city": meter_point.city,
                        "billing_address_street": meter_point.address_line1,
                        "billing_address_number": meter_point.address_line2 or "",
                        "billing_address_postal_code": meter_point.postal_code,
                        "billing_address_city": meter_point.city,
                    },
                )
                _materialize_meter_history_for_user(user=user, meter_point=meter_point)

            uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            activation_path = reverse("registration_activate", kwargs={"uidb64": uidb64, "token": token})
            activation_url = f"{settings.SITE_URL.rstrip('/')}{activation_path}"
            message = render_to_string(
                "portal/emails/activation_email.txt",
                {
                    "user": user,
                    "activation_url": activation_url,
                },
            )
            send_mail(
                subject="Activation de votre compte Electruc",
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
            )
            return redirect("registration_sent")
    else:
        form = RegistrationForm()

    return render(request, "portal/registration_start.html", {"form": form})


def registration_sent(request):
    """Confirmation page after registration email is sent."""
    return render(request, "portal/registration_sent.html")


def registration_activate(request, uidb64, token):
    """Activate account and mark invitation as used."""
    user = None
    user_model = get_user_model()

    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = user_model.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, user_model.DoesNotExist):
        user = None

    if user is None or not default_token_generator.check_token(user, token):
        messages.error(request, "Le lien d'activation est invalide ou a expire.")
        return render(request, "portal/activation_invalid.html", status=400)

    if not user.is_active:
        user.is_active = True
        user.save(update_fields=["is_active"])

    contract = Contract.objects.filter(user=user, meter_point__isnull=False).order_by("-start_date").first()
    if contract:
        invitation = (
            Invitation.objects.filter(
                meter_point=contract.meter_point,
                used_by=user,
                used_at__isnull=True,
            )
            .order_by("-created_at")
            .first()
        )
        if invitation:
            invitation.used_at = timezone.now()
            invitation.used_by = user
            invitation.save(update_fields=["used_at", "used_by"])

    messages.success(request, "Votre compte est active. Vous pouvez maintenant vous connecter.")
    return redirect("login")


@login_required
def client_dashboard(request):
    """Client dashboard (protected)."""
    readings = list(
        MeterReading.objects.filter(user=request.user, status=MeterReading.STATUS_VALIDATED)
        .order_by("-reading_date")[:5]
    )
    readings.reverse()
    chart_labels = [item.reading_date.strftime("%b %Y") for item in readings]
    chart_values = [item.value_kwh for item in readings]
    latest_invoice = Invoice.objects.filter(user=request.user).order_by("-issue_date").first()
    context = {
        "chart_labels_json": json.dumps(chart_labels),
        "chart_values_json": json.dumps(chart_values),
        "validated_readings_count": len(readings),
        "invoices_count": Invoice.objects.filter(user=request.user).count(),
        "latest_invoice": latest_invoice,
    }
    return render(request, "client/dashboard.html", context)


@login_required
def client_profile(request):
    """Client profile page (protected)."""
    profile, _ = CustomerProfile.objects.get_or_create(
        user=request.user,
        defaults={
            "customer_ref": f"CLI-{request.user.id:05d}",
            "ean": f"54{request.user.id:016d}",
            "supply_address_street": "Rue de la Demo",
            "supply_address_number": "1",
            "supply_address_postal_code": "1000",
            "supply_address_city": "Bruxelles",
        },
    )

    if request.method == "POST":
        form = ProfileForm(request.POST, instance=profile, user=request.user)
        if form.is_valid():
            updated_profile = form.save(commit=False)
            updated_profile.save()
            if form.cleaned_data.get("email") is not None:
                request.user.email = form.cleaned_data["email"]
                request.user.save(update_fields=["email"])
            messages.success(request, "Vos coordonnees ont ete mises a jour.")
    else:
        form = ProfileForm(instance=profile, user=request.user)

    return render(
        request,
        "client/profile.html",
        {"profile": profile, "form": form},
    )


@login_required
def client_contract(request):
    """Client contract page (protected)."""
    contract = Contract.objects.filter(user=request.user).order_by("-start_date").first()
    profile = CustomerProfile.objects.filter(user=request.user).first()
    return render(
        request,
        "client/contract.html",
        {"contract": contract, "profile": profile},
    )


@login_required
def client_invoices(request):
    """Client invoices page (protected)."""
    invoices = Invoice.objects.filter(user=request.user).order_by("-issue_date")
    return render(request, "client/invoices.html", {"invoices": invoices})


@login_required
def client_readings(request):
    """Client meter readings page (protected)."""
    last_validated = (
        MeterReading.objects.filter(user=request.user, status=MeterReading.STATUS_VALIDATED)
        .order_by("-reading_date")
        .first()
    )

    if request.method == "POST":
        form = MeterReadingForm(request.POST, last_validated=last_validated)
        if form.is_valid():
            reading = form.save(commit=False)
            reading.user = request.user
            reading.status = MeterReading.STATUS_SUBMITTED
            reading.save()
            messages.success(request, "Votre releve a ete envoye pour validation.")
            form = MeterReadingForm(last_validated=last_validated)
    else:
        form = MeterReadingForm(last_validated=last_validated)

    readings = MeterReading.objects.filter(user=request.user).order_by("-reading_date")
    return render(
        request,
        "client/readings.html",
        {"readings": readings, "form": form, "last_validated": last_validated},
    )


@login_required
def client_requests(request):
    """Client requests page (protected)."""
    if request.method == "POST":
        form = SupportRequestForm(request.POST, request.FILES)
        if form.is_valid():
            support_request = form.save(commit=False)
            support_request.user = request.user
            support_request.save()

            for file_obj in form.cleaned_data.get("attachments", []):
                Attachment.objects.create(support_request=support_request, file=file_obj)

            messages.success(request, "Votre demande a bien ete enregistree.")
            form = SupportRequestForm()
    else:
        form = SupportRequestForm()

    support_requests = SupportRequest.objects.filter(user=request.user).order_by("-created_at")
    return render(
        request,
        "client/requests.html",
        {"support_requests": support_requests, "form": form},
    )


@login_required
def client_direct_debit(request):
    """Client direct debit page (protected)."""
    if request.method == "POST":
        form = DomiciliationForm(request.POST, request.FILES)
        if form.is_valid():
            domiciliation = form.save(commit=False)
            domiciliation.user = request.user
            domiciliation.save()
            messages.success(request, "Votre demande de domiciliation a ete envoyee.")
            form = DomiciliationForm()
    else:
        form = DomiciliationForm()

    history = Domiciliation.objects.filter(user=request.user).order_by("-created_at")
    return render(
        request,
        "client/direct_debit.html",
        {"form": form, "history": history},
    )


@login_required
def invoice_pdf_download(request, invoice_id):
    """Download the invoice PDF if it belongs to the user."""
    invoice = get_object_or_404(Invoice, id=invoice_id, user=request.user)
    if not invoice.pdf_file:
        A4, mm, canvas = _get_reportlab()
        if not canvas:
            fallback_pdf = _build_fallback_pdf(
                document_title=f"Facture {invoice.reference}",
                lines=[
                    f"Date d'emission: {invoice.issue_date}",
                    f"Periode: {invoice.period_start} -> {invoice.period_end}",
                    f"Montant: {invoice.amount_eur} EUR",
                    f"Statut: {invoice.get_status_display()}",
                ],
            )
            response = HttpResponse(fallback_pdf, content_type="application/pdf")
            response["Content-Disposition"] = f'attachment; filename="facture-{invoice.reference}.pdf"'
            return response
        buffer = BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=A4)
        _draw_pdf_header(pdf, mm, "Facture")
        profile = CustomerProfile.objects.filter(user=request.user).first()
        client_name = request.user.get_full_name() or request.user.username
        client_lines = [client_name]
        if profile:
            client_lines.append(f"{profile.supply_address_street} {profile.supply_address_number}".strip())
            client_lines.append(f"{profile.supply_address_postal_code} {profile.supply_address_city}".strip())
        if request.user.email:
            client_lines.append(request.user.email)

        # Client block
        pdf.setStrokeColorRGB(0.87, 0.9, 0.92)
        pdf.rect(20 * mm, 215 * mm, 80 * mm, 35 * mm, stroke=1, fill=0)
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(23 * mm, 245 * mm, "Facturee a")
        pdf.setFont("Helvetica", 9)
        y_client = 240 * mm
        for line in client_lines[:4]:
            pdf.drawString(23 * mm, y_client, line)
            y_client -= 5 * mm

        # Document metadata block
        pdf.rect(110 * mm, 215 * mm, 80 * mm, 35 * mm, stroke=1, fill=0)
        pdf.setFont("Helvetica", 9)
        pdf.drawString(113 * mm, 245 * mm, f"Reference: {invoice.reference}")
        pdf.drawString(113 * mm, 240 * mm, f"Date d'emission: {invoice.issue_date:%d/%m/%Y}")
        pdf.drawString(113 * mm, 235 * mm, f"Periode: {invoice.period_start:%d/%m/%Y}")
        pdf.drawString(113 * mm, 230 * mm, f"au {invoice.period_end:%d/%m/%Y}")
        pdf.drawString(113 * mm, 225 * mm, f"Statut: {invoice.get_status_display()}")

        total = Decimal(invoice.amount_eur)
        abonnement = (total * Decimal("0.40")).quantize(Decimal("0.01"))
        consommation = (total * Decimal("0.50")).quantize(Decimal("0.01"))
        taxes = (total - abonnement - consommation).quantize(Decimal("0.01"))

        # Detail table
        table_left = 20 * mm
        table_width = 170 * mm
        table_top = 202 * mm
        row_height = 9 * mm
        rows = [
            ("Abonnement mensuel", abonnement),
            ("Consommation energie", consommation),
            ("Taxes et contributions", taxes),
        ]

        pdf.setFillColorRGB(0.95, 0.97, 0.98)
        pdf.rect(table_left, table_top, table_width, row_height, stroke=0, fill=1)
        pdf.setFillColorRGB(0, 0, 0)
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(table_left + 3 * mm, table_top + 3 * mm, "Description")
        pdf.drawRightString(table_left + table_width - 3 * mm, table_top + 3 * mm, "Montant")
        pdf.setStrokeColorRGB(0.87, 0.9, 0.92)
        pdf.rect(table_left, table_top - (len(rows) + 1) * row_height, table_width, (len(rows) + 1) * row_height, stroke=1, fill=0)

        y_row = table_top - row_height + 3 * mm
        pdf.setFont("Helvetica", 9)
        for description, amount in rows:
            pdf.drawString(table_left + 3 * mm, y_row, description)
            pdf.drawRightString(table_left + table_width - 3 * mm, y_row, f"{amount} EUR")
            pdf.line(table_left, y_row - 3 * mm, table_left + table_width, y_row - 3 * mm)
            y_row -= row_height

        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(132 * mm, 157 * mm, "Total TTC")
        pdf.drawRightString(187 * mm, 157 * mm, f"{total} EUR")

        pdf.setFont("Helvetica", 8)
        pdf.drawString(20 * mm, 20 * mm, "Paiement a 15 jours date de facture. Merci de votre confiance.")
        pdf.drawString(20 * mm, 15 * mm, "Document de demonstration - Electruc Portal.")

        pdf.showPage()
        pdf.save()

        response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="facture-{invoice.reference}.pdf"'
        return response

    return FileResponse(invoice.pdf_file.open("rb"), as_attachment=True, filename=invoice.pdf_file.name.split("/")[-1])


@login_required
def attachment_download(request, attachment_id):
    """Download a support attachment if it belongs to the user."""
    attachment = get_object_or_404(Attachment, id=attachment_id)
    if attachment.support_request.user_id != request.user.id:
        raise Http404("Acces refuse.")
    return FileResponse(attachment.file.open("rb"), as_attachment=True, filename=attachment.file.name.split("/")[-1])


@login_required
def domiciliation_document_download(request, domiciliation_id):
    """Download a domiciliation document if it belongs to the user."""
    domiciliation = get_object_or_404(Domiciliation, id=domiciliation_id, user=request.user)
    return FileResponse(
        domiciliation.document.open("rb"),
        as_attachment=True,
        filename=domiciliation.document.name.split("/")[-1],
    )


@login_required
def direct_debit_template_download(request):
    """Download a fillable direct debit form (PDF AcroForm)."""
    A4, mm, canvas = _get_reportlab()
    if not canvas:
        fallback_pdf = _build_fallback_pdf(
            document_title="Formulaire de domiciliation SEPA",
            lines=[
                "Nom et prenom: __________________________",
                "Adresse: __________________________",
                "Code postal / Ville: __________________________",
                "IBAN: __________________________",
                "BIC: __________________________",
                "Date et signature: __________________________",
            ],
        )
        response = HttpResponse(fallback_pdf, content_type="application/pdf")
        response["Content-Disposition"] = 'attachment; filename="domiciliation_electruc_editable.pdf"'
        return response

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    _draw_pdf_header(pdf, mm, "Formulaire de domiciliation SEPA")

    pdf.setFont("Helvetica", 10)
    pdf.drawString(20 * mm, 248 * mm, "Completez les champs, puis enregistrez et transmettez le document signe.")

    pdf.setStrokeColorRGB(0.87, 0.9, 0.92)
    pdf.rect(20 * mm, 206 * mm, 170 * mm, 36 * mm, stroke=1, fill=0)
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(23 * mm, 236 * mm, "Informations du titulaire")
    pdf.setFont("Helvetica", 9)
    pdf.drawString(23 * mm, 229 * mm, "Nom et prenom")
    pdf.drawString(23 * mm, 222 * mm, "Adresse")
    pdf.drawString(23 * mm, 215 * mm, "Code postal / Ville")

    pdf.rect(20 * mm, 170 * mm, 170 * mm, 30 * mm, stroke=1, fill=0)
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(23 * mm, 194 * mm, "Coordonnees bancaires")
    pdf.setFont("Helvetica", 9)
    pdf.drawString(23 * mm, 187 * mm, "IBAN")
    pdf.drawString(23 * mm, 180 * mm, "BIC")

    pdf.rect(20 * mm, 136 * mm, 170 * mm, 28 * mm, stroke=1, fill=0)
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(23 * mm, 158 * mm, "Mandat")
    pdf.setFont("Helvetica", 9)
    pdf.drawString(23 * mm, 151 * mm, "J'autorise Electruc SA a prelever les montants dus sur le compte indique.")
    pdf.drawString(23 * mm, 145 * mm, "Ce mandat reste valable jusqu'a revocation explicite du titulaire.")

    pdf.rect(20 * mm, 108 * mm, 170 * mm, 22 * mm, stroke=1, fill=0)
    pdf.setFont("Helvetica", 9)
    pdf.drawString(23 * mm, 121 * mm, "Date")
    pdf.drawString(88 * mm, 121 * mm, "Lieu")
    pdf.drawString(23 * mm, 113 * mm, "Signature")

    form = pdf.acroForm
    from reportlab.lib import colors

    field_border = colors.Color(0.7, 0.75, 0.8)
    field_text = colors.black
    form.textfield(
        name="holder_name",
        x=62 * mm,
        y=226.5 * mm,
        width=122 * mm,
        height=6 * mm,
        borderStyle="inset",
        borderColor=field_border,
        fillColor=None,
        textColor=field_text,
        forceBorder=True,
    )
    form.textfield(
        name="holder_address",
        x=62 * mm,
        y=219.5 * mm,
        width=122 * mm,
        height=6 * mm,
        borderStyle="inset",
        borderColor=field_border,
        fillColor=None,
        textColor=field_text,
        forceBorder=True,
    )
    form.textfield(
        name="holder_city",
        x=62 * mm,
        y=212.5 * mm,
        width=122 * mm,
        height=6 * mm,
        borderStyle="inset",
        borderColor=field_border,
        fillColor=None,
        textColor=field_text,
        forceBorder=True,
    )
    form.textfield(
        name="iban",
        x=62 * mm,
        y=184.5 * mm,
        width=122 * mm,
        height=6 * mm,
        borderStyle="inset",
        borderColor=field_border,
        fillColor=None,
        textColor=field_text,
        forceBorder=True,
    )
    form.textfield(
        name="bic",
        x=62 * mm,
        y=177.5 * mm,
        width=122 * mm,
        height=6 * mm,
        borderStyle="inset",
        borderColor=field_border,
        fillColor=None,
        textColor=field_text,
        forceBorder=True,
    )
    form.textfield(
        name="mandate_date",
        x=34 * mm,
        y=118 * mm,
        width=44 * mm,
        height=6 * mm,
        borderStyle="inset",
        borderColor=field_border,
        fillColor=None,
        textColor=field_text,
        forceBorder=True,
    )
    form.textfield(
        name="mandate_place",
        x=96 * mm,
        y=118 * mm,
        width=40 * mm,
        height=6 * mm,
        borderStyle="inset",
        borderColor=field_border,
        fillColor=None,
        textColor=field_text,
        forceBorder=True,
    )
    form.textfield(
        name="holder_signature",
        x=48 * mm,
        y=110 * mm,
        width=136 * mm,
        height=6 * mm,
        borderStyle="inset",
        borderColor=field_border,
        fillColor=None,
        textColor=field_text,
        forceBorder=True,
    )

    pdf.setFont("Helvetica", 8)
    pdf.drawString(20 * mm, 20 * mm, "Document de demonstration - Electruc Portal.")
    pdf.showPage()
    pdf.save()

    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="domiciliation_electruc_editable.pdf"'
    return response


@login_required
def cgv_download(request):
    """Download branded CGV PDF."""
    A4, mm, canvas = _get_reportlab()
    if not canvas:
        fallback_pdf = _build_fallback_pdf(
            document_title="Conditions generales de vente - Electruc",
            lines=[
                "1. Objet: fourniture d'energie selon contrat en vigueur.",
                "2. Facturation: mensuelle, payable dans les delais indiques.",
                "3. Releves: le client transmet ses index selon les modalites du portail.",
                "4. Donnees: traitement conforme au RGPD.",
            ],
        )
        response = HttpResponse(fallback_pdf, content_type="application/pdf")
        response["Content-Disposition"] = 'attachment; filename="cgv_electruc.pdf"'
        return response

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    _draw_pdf_header(pdf, mm, "Conditions generales de vente")

    sections = [
        ("1. Objet", "Les presentes CGV definissent les conditions de fourniture d'energie pour les clients particuliers."),
        ("2. Contrat", "Le contrat prend effet a la date indiquee sur le document contractuel et reste en vigueur selon les modalites prevues."),
        ("3. Prix et facturation", "La facturation est mensuelle. Le detail des montants est accessible depuis l'espace client."),
        ("4. Paiement", "Le paiement est exigible a l'echeance indiquee sur la facture. Des frais peuvent s'appliquer en cas de retard."),
        ("5. Releves et consommation", "Le client transmet ses releves via le portail; Electruc peut estimer la consommation en l'absence de releve."),
        ("6. Service client", "Les demandes sont traitees via l'espace client, par e-mail ou formulaire de contact."),
        ("7. Donnees personnelles", "Les donnees sont traitees conformement a la reglementation en vigueur et a la politique de confidentialite."),
        ("8. Droit applicable", "Le contrat est soumis au droit belge. Les tribunaux competents sont ceux du ressort du siege social."),
    ]

    y = 248 * mm
    for title, text in sections:
        if y < 40 * mm:
            pdf.showPage()
            _draw_pdf_header(pdf, mm, "Conditions generales de vente")
            y = 248 * mm
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(20 * mm, y, title)
        y -= 6 * mm
        pdf.setFont("Helvetica", 9)
        pdf.drawString(20 * mm, y, text)
        y -= 10 * mm

    pdf.setFont("Helvetica", 8)
    pdf.drawString(20 * mm, 20 * mm, "Version pedagogique - Electruc Portal.")
    pdf.showPage()
    pdf.save()

    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="cgv_electruc.pdf"'
    return response


@login_required
def contract_pdf_download(request):
    """Generate a contract PDF on the fly for the logged-in user."""
    contract = Contract.objects.filter(user=request.user).order_by("-start_date").first()
    if not contract:
        raise Http404("Contrat non disponible.")
    profile = CustomerProfile.objects.filter(user=request.user).first()
    A4, mm, canvas = _get_reportlab()
    if not canvas:
        fallback_pdf = _build_fallback_pdf(
            document_title=f"Contrat {contract.reference}",
            lines=[
                f"Offre: {contract.plan_name}",
                f"Date de debut: {contract.start_date}",
                f"Statut: {contract.get_status_display()}",
                f"Adresse: {contract.supply_address}",
                f"EAN: {profile.ean if profile else '-'}",
            ],
        )
        response = HttpResponse(fallback_pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="contrat-{contract.reference}.pdf"'
        return response

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    _draw_pdf_header(pdf, mm, "Contrat d'energie")

    client_name = request.user.get_full_name() or request.user.username
    client_lines = [client_name]
    if request.user.email:
        client_lines.append(request.user.email)
    if profile:
        client_lines.append(f"{profile.supply_address_street} {profile.supply_address_number}".strip())
        client_lines.append(f"{profile.supply_address_postal_code} {profile.supply_address_city}".strip())

    pdf.setStrokeColorRGB(0.87, 0.9, 0.92)
    pdf.rect(20 * mm, 218 * mm, 80 * mm, 32 * mm, stroke=1, fill=0)
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(23 * mm, 245 * mm, "Titulaire du contrat")
    pdf.setFont("Helvetica", 9)
    y_client = 240 * mm
    for line in client_lines[:4]:
        pdf.drawString(23 * mm, y_client, line)
        y_client -= 5 * mm

    pdf.rect(110 * mm, 218 * mm, 80 * mm, 32 * mm, stroke=1, fill=0)
    pdf.setFont("Helvetica", 9)
    pdf.drawString(113 * mm, 245 * mm, f"Reference: {contract.reference}")
    pdf.drawString(113 * mm, 240 * mm, f"Date de debut: {contract.start_date:%d/%m/%Y}")
    pdf.drawString(113 * mm, 235 * mm, f"Offre: {contract.plan_name}")
    pdf.drawString(113 * mm, 230 * mm, f"Statut: {contract.get_status_display()}")
    pdf.drawString(113 * mm, 225 * mm, f"EAN: {profile.ean if profile else '-'}")

    # Contract summary section
    section_top = 206 * mm
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(20 * mm, section_top, "Resume des conditions")
    pdf.setFont("Helvetica", 9)
    summary_lines = [
        f"Adresse de fourniture: {contract.supply_address}",
        "Facturation: mensuelle, paiement a 15 jours.",
        "Duree: contrat a duree indeterminee, resiliation possible selon CGV.",
        "Support client: disponible via l'espace client et formulaire de contact.",
    ]
    y_text = section_top - 8 * mm
    for line in summary_lines:
        pdf.drawString(20 * mm, y_text, line)
        y_text -= 6 * mm

    # Small clauses table
    table_left = 20 * mm
    table_width = 170 * mm
    table_top = 165 * mm
    row_height = 9 * mm
    clauses = [
        ("Type d'offre", contract.plan_name),
        ("Frequence de releve", "Mensuelle"),
        ("Canal de facturation", "Portail client"),
        ("Reference point de fourniture", profile.ean if profile else "-"),
    ]
    pdf.setFillColorRGB(0.95, 0.97, 0.98)
    pdf.rect(table_left, table_top, table_width, row_height, stroke=0, fill=1)
    pdf.setFillColorRGB(0, 0, 0)
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(table_left + 3 * mm, table_top + 3 * mm, "Element")
    pdf.drawRightString(table_left + table_width - 3 * mm, table_top + 3 * mm, "Valeur")
    pdf.setStrokeColorRGB(0.87, 0.9, 0.92)
    pdf.rect(table_left, table_top - (len(clauses) + 1) * row_height, table_width, (len(clauses) + 1) * row_height, stroke=1, fill=0)

    y_row = table_top - row_height + 3 * mm
    pdf.setFont("Helvetica", 9)
    for label, value in clauses:
        pdf.drawString(table_left + 3 * mm, y_row, str(label))
        pdf.drawRightString(table_left + table_width - 3 * mm, y_row, str(value))
        pdf.line(table_left, y_row - 3 * mm, table_left + table_width, y_row - 3 * mm)
        y_row -= row_height

    pdf.setFont("Helvetica", 8)
    pdf.drawString(20 * mm, 20 * mm, "Conditions generales disponibles dans l'espace client.")
    pdf.drawString(20 * mm, 15 * mm, "Document de demonstration - Electruc Portal.")
    pdf.showPage()
    pdf.save()

    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="contrat-{contract.reference}.pdf"'
    return response

