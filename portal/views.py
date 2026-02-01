"""Views for the portal app (public pages + minimal contact form)."""
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.contrib import messages
from django.contrib.staticfiles import finders

from .forms import ContactForm, SupportRequestForm, DomiciliationForm
from .models import Attachment, Domiciliation, Invoice, MeterReading, SupportRequest

from io import BytesIO
from decimal import Decimal

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


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
            # No email or storage is performed; we only confirm reception.
            messages.success(request, "Votre message a bien été reçu.")
            form = ContactForm()
    else:
        form = ContactForm()

    return render(request, "portal/contact.html", {"form": form})


@login_required
def client_dashboard(request):
    """Client dashboard (protected)."""
    return render(request, "client/dashboard.html")


@login_required
def client_profile(request):
    """Client profile page (protected)."""
    return render(request, "client/profile.html")


@login_required
def client_contract(request):
    """Client contract page (protected)."""
    return render(request, "client/contract.html")


@login_required
def client_invoices(request):
    """Client invoices page (protected)."""
    invoices = Invoice.objects.filter(user=request.user).order_by("-issue_date")
    return render(request, "client/invoices.html", {"invoices": invoices})


@login_required
def client_readings(request):
    """Client meter readings page (protected)."""
    readings = MeterReading.objects.filter(user=request.user).order_by("-reading_date")
    return render(request, "client/readings.html", {"readings": readings})


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

            messages.success(request, "Votre demande a bien été enregistrée.")
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
            messages.success(request, "Votre demande de domiciliation a été envoyée.")
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
        # Generate a simple PDF on the fly using ReportLab.
        buffer = BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4

        y = height - 20 * mm

        logo_path = finders.find("branding/electruc-logo.png")
        if logo_path:
            pdf.drawImage(logo_path, 20 * mm, y - 12 * mm, width=40 * mm, height=12 * mm, preserveAspectRatio=True)
        else:
            pdf.setFont("Helvetica-Bold", 16)
            pdf.drawString(20 * mm, y, "Electruc")

        y -= 20 * mm
        pdf.setFont("Helvetica", 10)
        client_name = request.user.get_full_name() or request.user.username
        pdf.drawString(20 * mm, y, f"Client: {client_name}")
        y -= 6 * mm
        if request.user.email:
            pdf.drawString(20 * mm, y, f"E-mail: {request.user.email}")

        y -= 12 * mm
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(20 * mm, y, "Facture")
        y -= 6 * mm
        pdf.setFont("Helvetica", 10)
        pdf.drawString(20 * mm, y, f"Référence: {invoice.reference}")
        y -= 6 * mm
        pdf.drawString(20 * mm, y, f"Date d'émission: {invoice.issue_date}")
        y -= 6 * mm
        pdf.drawString(20 * mm, y, f"Période: {invoice.period_start} → {invoice.period_end}")
        y -= 6 * mm
        pdf.drawString(20 * mm, y, f"Statut: {invoice.get_status_display()}")

        y -= 12 * mm
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(20 * mm, y, "Détail")
        y -= 6 * mm

        total = Decimal(invoice.amount_eur)
        abonnement = (total * Decimal("0.40")).quantize(Decimal("0.01"))
        consommation = (total * Decimal("0.50")).quantize(Decimal("0.01"))
        taxes = (total - abonnement - consommation).quantize(Decimal("0.01"))

        pdf.setFont("Helvetica", 10)
        pdf.drawString(20 * mm, y, f"Abonnement")
        pdf.drawRightString(180 * mm, y, f"{abonnement} €")
        y -= 6 * mm
        pdf.drawString(20 * mm, y, f"Consommation")
        pdf.drawRightString(180 * mm, y, f"{consommation} €")
        y -= 6 * mm
        pdf.drawString(20 * mm, y, f"Taxes")
        pdf.drawRightString(180 * mm, y, f"{taxes} €")
        y -= 8 * mm
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(20 * mm, y, "Total")
        pdf.drawRightString(180 * mm, y, f"{total} €")

        pdf.setFont("Helvetica", 9)
        pdf.drawString(20 * mm, 15 * mm, "Document de démonstration — Electruc Portal.")

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
        raise Http404("Accès refusé.")
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
    """Download a blank direct debit form (static file)."""
    template_path = finders.find("forms/domiciliation_electruc.docx")
    if not template_path:
        raise Http404("Formulaire non disponible.")
    return FileResponse(
        open(template_path, "rb"),
        as_attachment=True,
        filename="domiciliation_electruc.docx",
    )
