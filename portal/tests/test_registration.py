from datetime import timedelta
import re

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from portal.admin import ensure_meter_point_history
from portal.models import Invitation, Invoice, MeterPoint, MeterReading


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", SITE_URL="http://testserver")
class RegistrationFlowTests(TestCase):
    def setUp(self):
        self.meter_point = MeterPoint.objects.create(
            ean="541234567890120001",
            address_line1="Rue de Test 1",
            address_line2="",
            postal_code="1000",
            city="Bruxelles",
            country="BE",
            holder_firstname="Jean",
            holder_lastname="Martin",
        )
        self.invitation, self.secret_code = Invitation.create_with_secret(
            meter_point=self.meter_point,
            expires_at=timezone.now() + timedelta(days=30),
        )
        ensure_meter_point_history(self.meter_point, months=5)

    def test_valid_invitation_creates_inactive_user_and_sends_email(self):
        response = self.client.post(
            reverse("registration_start"),
            {
                "ean": self.meter_point.ean,
                "secret_code": self.secret_code,
                "email": "jean.martin@example.com",
                "password1": "SecuritePass123!",
                "password2": "SecuritePass123!",
            },
        )

        self.assertRedirects(response, reverse("registration_sent"))
        user = get_user_model().objects.get(username="jean.martin@example.com")
        self.assertFalse(user.is_active)

        self.invitation.refresh_from_db()
        self.assertEqual(self.invitation.used_by, user)
        self.assertIsNone(self.invitation.used_at)

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/activation/", mail.outbox[0].body)
        self.assertEqual(Invoice.objects.filter(user=user).count(), 5)
        self.assertEqual(
            MeterReading.objects.filter(user=user, status=MeterReading.STATUS_VALIDATED).count(),
            5,
        )

    def test_activation_marks_user_active_and_invitation_used(self):
        self.client.post(
            reverse("registration_start"),
            {
                "ean": self.meter_point.ean,
                "secret_code": self.secret_code,
                "email": "activer@example.com",
                "password1": "SecuritePass123!",
                "password2": "SecuritePass123!",
            },
        )

        activation_email = mail.outbox[0].body
        match = re.search(r"http://testserver(/activation/[^\s]+)", activation_email)
        self.assertIsNotNone(match)
        activation_url = match.group(1)

        response = self.client.get(activation_url)
        self.assertRedirects(response, reverse("login"))

        user = get_user_model().objects.get(username="activer@example.com")
        user.refresh_from_db()
        self.assertTrue(user.is_active)

        self.invitation.refresh_from_db()
        self.assertEqual(self.invitation.used_by, user)
        self.assertIsNotNone(self.invitation.used_at)

    def test_expired_invitation_is_rejected(self):
        self.invitation.expires_at = timezone.now() - timedelta(days=1)
        self.invitation.save(update_fields=["expires_at"])

        response = self.client.post(
            reverse("registration_start"),
            {
                "ean": self.meter_point.ean,
                "secret_code": self.secret_code,
                "email": "refus@example.com",
                "password1": "SecuritePass123!",
                "password2": "SecuritePass123!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invitation invalide, expiree ou deja utilisee.")
        self.assertFalse(get_user_model().objects.filter(username="refus@example.com").exists())
