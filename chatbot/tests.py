import json
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User
from chatbot.models import ChatSession, ChatMessage


class ChatbotAccessTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(username="admin", password="pw", role=User.Role.ADMIN)
        self.caregiver = User.objects.create_user(username="caregiver", password="pw", role=User.Role.CAREGIVER)
        self.verified_clin = User.objects.create_user(username="vclin", password="pw", role=User.Role.CLINICIAN, clinician_verified=True)
        self.unverified_clin = User.objects.create_user(username="uclin", password="pw", role=User.Role.CLINICIAN, clinician_verified=False)

    def test_requires_login(self):
        response = self.client.get(reverse("chatbot:chat_page"))
        self.assertNotEqual(response.status_code, 200)
        self.assertEqual(response.status_code, 302) # Redirects to login

    def test_caregiver_allowed(self):
        self.client.force_login(self.caregiver)
        response = self.client.get(reverse("chatbot:chat_page"))
        self.assertEqual(response.status_code, 200)

    def test_clinician_verified_allowed(self):
        self.client.force_login(self.verified_clin)
        response = self.client.get(reverse("chatbot:chat_page"))
        self.assertEqual(response.status_code, 200)

    def test_clinician_unverified_denied(self):
        self.client.force_login(self.unverified_clin)
        response = self.client.get(reverse("chatbot:chat_page"))
        self.assertEqual(response.status_code, 403)

    def test_admin_denied(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("chatbot:chat_page"))
        self.assertEqual(response.status_code, 403)


class ChatbotApiTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.caregiver = User.objects.create_user(username="caregiver", password="pw", role=User.Role.CAREGIVER)

    def test_csrf_required_for_ask(self):
        self.client.force_login(self.caregiver)
        # Without CSRF token in the request headers
        response = self.client.post(
            reverse("chatbot:chat_ask"),
            data=json.dumps({"message": "Hello"}),
            content_type="application/json"
        )
        # 403 Forbidden due to CSRF missing
        self.assertEqual(response.status_code, 403)

    @patch("chatbot.views.requests.get")
    @patch("chatbot.views.requests.post")
    def test_chat_ask_success(self, mock_post, mock_get):
        self.client.force_login(self.caregiver)
        
        # Mock POST to Fastapi
        mock_post_resp = MagicMock()
        mock_post_resp.json.return_value = {"request_id": "req-123", "session_id": "sess-456"}
        mock_post.return_value = mock_post_resp
        
        # Mock GET SSE Stream
        mock_get_resp = MagicMock()
        # Create an iterator that yields line strings (decoded content)
        mock_get_resp.iter_lines.return_value = [
            'event: token',
            'data: {"text": "Hello "}',
            '',
            'event: token',
            'data: {"text": "World"}',
            '',
            'event: done',
            'data: {"ok": true, "sources": [{"id": 1, "title": "Test Source"}]}',
            ''
        ]
        mock_get.return_value = mock_get_resp

        # Create a client that doesn't enforce CSRF just to test the logic
        client_no_csrf = Client()
        client_no_csrf.force_login(self.caregiver)

        response = client_no_csrf.post(
            reverse("chatbot:chat_ask"),
            data=json.dumps({"message": "Test question"}),
            content_type="application/json"
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["answer"], "Hello World")
        self.assertEqual(data["sources"], [{"id": 1, "title": "Test Source"}])
        self.assertTrue("session_id" in data)
        
        # Verify db models created
        self.assertEqual(ChatSession.objects.count(), 1)
        self.assertEqual(ChatMessage.objects.count(), 2)
        messages = ChatMessage.objects.order_by("created_at")
        self.assertEqual(messages[0].role, "user")
        self.assertEqual(messages[0].content, "Test question")
        self.assertEqual(messages[1].role, "assistant")
        self.assertEqual(messages[1].content, "Hello World")

    @patch("chatbot.views.requests.get")
    @patch("chatbot.views.requests.post")
    def test_chat_ask_rag_error(self, mock_post, mock_get):
        self.client.force_login(self.caregiver)
        
        mock_post_resp = MagicMock()
        mock_post_resp.json.return_value = {"request_id": "req-123"}
        mock_post.return_value = mock_post_resp
        
        mock_get_resp = MagicMock()
        mock_get_resp.iter_lines.return_value = [
            'event: error',
            'data: {"message": "Service unavailable"}',
            ''
        ]
        mock_get.return_value = mock_get_resp

        client_no_csrf = Client()
        client_no_csrf.force_login(self.caregiver)

        response = client_no_csrf.post(
            reverse("chatbot:chat_ask"),
            data=json.dumps({"message": "Test error"}),
            content_type="application/json"
        )
        
        self.assertEqual(response.status_code, 502)
        data = response.json()
        self.assertEqual(data["error"], "Service unavailable")
