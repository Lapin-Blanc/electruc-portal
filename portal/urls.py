"""URL configuration for the portal app."""
from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("services/", views.services, name="services"),
    path("aide/", views.faq, name="faq"),
    path("contact/", views.contact, name="contact"),
    path("inscription/", views.registration_start, name="registration_start"),
    path("inscription/envoye/", views.registration_sent, name="registration_sent"),
    path("activation/<uidb64>/<token>/", views.registration_activate, name="registration_activate"),
    path("espace-client/", views.client_dashboard, name="client_dashboard"),
    path("espace-client/profil/", views.client_profile, name="client_profile"),
    path("espace-client/contrat/", views.client_contract, name="client_contract"),
    path(
        "espace-client/contrat/pdf/",
        views.contract_pdf_download,
        name="contract_pdf_download",
    ),
    path(
        "espace-client/contrat/cgv/",
        views.cgv_download,
        name="cgv_download",
    ),
    path("espace-client/factures/", views.client_invoices, name="client_invoices"),
    path(
        "espace-client/factures/<int:invoice_id>/pdf/",
        views.invoice_pdf_download,
        name="invoice_pdf_download",
    ),
    path("espace-client/releves/", views.client_readings, name="client_readings"),
    path("espace-client/demandes/", views.client_requests, name="client_requests"),
    path(
        "espace-client/demandes/piece-jointe/<int:attachment_id>/",
        views.attachment_download,
        name="attachment_download",
    ),
    path(
        "espace-client/domiciliation/document/<int:domiciliation_id>/",
        views.domiciliation_document_download,
        name="domiciliation_document_download",
    ),
    path(
        "espace-client/domiciliation/formulaire/",
        views.direct_debit_template_download,
        name="direct_debit_template_download",
    ),
    path("espace-client/domiciliation/", views.client_direct_debit, name="client_direct_debit"),
]
