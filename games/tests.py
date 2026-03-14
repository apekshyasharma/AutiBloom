from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User
from .models import TherapyGame

class GamesTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.caregiver = User.objects.create_user(
            username='caregiver1',
            password='password123',
            role='CAREGIVER'
        )
        self.practitioner = User.objects.create_user(
            username='practitioner1',
            password='password123',
            role='PRACTITIONER'
        )
        self.game = TherapyGame.objects.create(
            title="Test Game",
            slug="test-game",
            goal="Test Goal",
            age_range="5-10",
            description="Test playing the game"
        )
        self.list_url = reverse('game_list')
        self.detail_url = reverse('game_detail', args=[self.game.slug])

    def test_caregiver_access_list(self):
        self.client.login(username='caregiver1', password='password123')
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Game")
        self.assertContains(response, "Test Goal")

    def test_caregiver_access_detail(self):
        self.client.login(username='caregiver1', password='password123')
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Activity Setup Required")

    def test_practitioner_denied_list(self):
        self.client.login(username='practitioner1', password='password123')
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_redirect(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue('login' in response.url)
