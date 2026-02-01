"""Create simple demonstration data for the portal app."""
from datetime import date, timedelta
from decimal import Decimal
import random

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from portal.models import Attachment, Contract, Domiciliation, Invoice, MeterReading, SupportRequest


class Command(BaseCommand):
    help = "Create demo users, contracts, invoices, readings, support requests and uploads."

    def handle(self, *args, **options):
        users_data = [
            {
                "username": "aline",
                "first_name": "Aline",
                "last_name": "Dupont",
                "email": "aline.dupont@example.com",
            },
            {
                "username": "marc",
                "first_name": "Marc",
                "last_name": "Van den Berg",
                "email": "marc.vandenberg@example.com",
            },
            {
                "username": "sophie",
                "first_name": "Sophie",
                "last_name": "Leroy",
                "email": "sophie.leroy@example.com",
            },
        ]

        addresses = [
            "Rue des Carmes 12, 5000 Namur",
            "Avenue Louise 220, 1050 Bruxelles",
            "Chaussée de Liège 45, 4000 Liège",
        ]

        plan_names = ["Électricité résidentielle", "Électricité & gaz", "Gaz résidentiel"]

        subject_samples = [
            "Question sur une facture",
            "Mise à jour des coordonnées",
            "Suivi d'une demande",
        ]

        pdf_bytes = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
        png_bytes = b"\x89PNG\r\n\x1a\n" + b"0" * 100

        User = get_user_model()

        for index, user_data in enumerate(users_data):
            user, created = User.objects.get_or_create(
                username=user_data["username"],
                defaults={
                    "first_name": user_data["first_name"],
                    "last_name": user_data["last_name"],
                    "email": user_data["email"],
                },
            )

            if created:
                user.set_password("demo1234")
                user.save()

            # Clear previous demo data for this user to keep the dataset clean.
            Attachment.objects.filter(support_request__user=user).delete()
            SupportRequest.objects.filter(user=user).delete()
            Domiciliation.objects.filter(user=user).delete()
            Contract.objects.filter(user=user).delete()
            Invoice.objects.filter(user=user).delete()
            MeterReading.objects.filter(user=user).delete()

            contract_reference = f"CTR-2025-{index + 1:03d}"
            Contract.objects.create(
                user=user,
                reference=contract_reference,
                start_date=date(2024, 1, 15) + timedelta(days=index * 30),
                plan_name=plan_names[index % len(plan_names)],
                supply_address=addresses[index % len(addresses)],
                status=Contract.STATUS_ACTIVE,
            )

            for month_offset in range(3):
                period_end = date(2025, 12, 31) - timedelta(days=30 * month_offset)
                period_start = period_end - timedelta(days=29)
                issue_date = period_end + timedelta(days=3)
                amount = Decimal(random.randint(45, 120)) + Decimal("0.00")
                invoice = Invoice.objects.create(
                    user=user,
                    reference=f"FAC-2025-{index + 1:03d}-{month_offset + 1:02d}",
                    period_start=period_start,
                    period_end=period_end,
                    issue_date=issue_date,
                    amount_eur=amount,
                    status=Invoice.STATUS_PAID if month_offset > 0 else Invoice.STATUS_DUE,
                )
                # Only attach a PDF for the very first invoice to test both paths.
                if index == 0 and month_offset == 0:
                    pdf_name = f"facture-{invoice.reference}.pdf"
                    invoice.pdf_file.save(pdf_name, ContentFile(pdf_bytes), save=True)

            for reading_offset in range(2):
                reading_date = date(2025, 12, 15) - timedelta(days=60 * reading_offset)
                MeterReading.objects.create(
                    user=user,
                    reading_date=reading_date,
                    value_kwh=1200 + (index * 250) + (reading_offset * 140),
                    status=MeterReading.STATUS_VALIDATED,
                )

            for request_offset in range(2):
                support_request = SupportRequest.objects.create(
                    user=user,
                    subject=subject_samples[request_offset % len(subject_samples)],
                    message="Demande enregistrée pour suivi par le service client.",
                    status=SupportRequest.STATUS_IN_PROGRESS if request_offset == 0 else SupportRequest.STATUS_OPEN,
                )
                attachment = Attachment(support_request=support_request)
                attachment.file.save(
                    f"piece-jointe-{support_request.id}.png",
                    ContentFile(png_bytes),
                    save=True,
                )

            if index < 2:
                domiciliation = Domiciliation(user=user, status=Domiciliation.STATUS_PENDING)
                domiciliation.document.save(
                    f"domiciliation-{user.username}.pdf",
                    ContentFile(pdf_bytes),
                    save=True,
                )

        self.stdout.write(self.style.SUCCESS("Données de démonstration créées."))
