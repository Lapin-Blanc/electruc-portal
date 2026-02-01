from decimal import Decimal
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from portal.models import Invoice


class InvoiceDownloadTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="alice", password="pass1234")
        self.other = User.objects.create_user(username="bob", password="pass1234")

        self.invoice = Invoice.objects.create(
            user=self.user,
            reference="FAC-TEST-001",
            period_start=date(2025, 1, 1),
            period_end=date(2025, 1, 31),
            issue_date=date(2025, 2, 3),
            amount_eur=Decimal("85.50"),
            status=Invoice.STATUS_DUE,
        )

    def test_user_cannot_download_others_invoice(self):
        self.client.force_login(self.other)
        url = reverse("invoice_pdf_download", args=[self.invoice.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_pdf_generated_when_missing_file(self):
        self.client.force_login(self.user)
        url = reverse("invoice_pdf_download", args=[self.invoice.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(len(response.content) > 0)
