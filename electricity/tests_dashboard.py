import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import ConsultationRequest, PublicFormSubmissionBucket


class DashboardRegressionTests(TestCase):
    def test_staff_dashboard_loads_without_exposing_internal_spam_counters(self):
        user = get_user_model().objects.create_user(username="dashboard-staff", is_staff=True)
        self.client.force_login(user)
        request = ConsultationRequest.objects.create(full_name="Existing Customer", phone="0701234567")
        counter = PublicFormSubmissionBucket.objects.create(
            key="private-spam-counter", count=3,
            expires_at=timezone.now() + datetime.timedelta(hours=1),
        )

        response = self.client.get(reverse("electricity:dashboard"), secure=True)

        self.assertEqual(response.status_code, 200)
        cards = {card["object_name"]: card for card in response.context["model_cards"]}
        self.assertNotIn("PublicFormSubmissionBucket", cards)
        self.assertEqual(cards["ConsultationRequest"]["count"], 1)
        self.assertIn(request, list(cards["ConsultationRequest"]["rows"]))
        self.assertNotContains(response, "private-spam-counter")
        counter.refresh_from_db()
        self.assertEqual(counter.count, 3)
