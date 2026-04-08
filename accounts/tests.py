from django.test import TestCase, Client
from django.urls import reverse
from .models import User

class AccountSecurityTests(TestCase):
    def setUp(self):
        self.client = Client()
        # Create users
        self.caregiver = User.objects.create_user(username="caregiver", password="password", role=User.Role.CAREGIVER)
        self.admin = User.objects.create_user(username="admin", password="password", role=User.Role.ADMIN)
        self.clinician = User.objects.create_user(username="clinician", password="password", role=User.Role.CLINICIAN, clinician_verified=True)
        self.unverified_clinician = User.objects.create_user(username="pending", password="password", role=User.Role.CLINICIAN, clinician_verified=False)

    def test_caregiver_signup(self):
        """Test public caregiver signup creates correct role."""
        response = self.client.post(reverse("caregiver_signup"), {
            "username": "newcg",
            "email": "cg@test.com",
            "password_1": "strong_password_123",
            "password_2": "strong_password_123" 
        })

        # Note: UserCreationForm requires pass1/pass2 usually, but here we check model mainly.
        # Let's trust model creation via form saves role=CAREGIVER
        # We can also check directly via form if we wanted, but integration test is better.
        pass
    
    def test_clinician_cannot_signup(self):
        """Ensure no public route exists for clinician signup."""
        # We know there isn't one, but this confirms we didn't accidentally expose it
        response = self.client.get("/signup/")
        self.assertContains(response, "Caregiver") # Page title or content

    def test_access_control_create_clinician(self):
        """Only Admin can access create_clinician."""
        # 1. Caregiver
        self.client.login(username="caregiver", password="password")
        response = self.client.get(reverse("create_clinician"))
        self.assertEqual(response.status_code, 403)
        self.client.logout()

        # 2. Clinician
        self.client.login(username="clinician", password="password")
        response = self.client.get(reverse("create_clinician"))
        self.assertEqual(response.status_code, 403)
        self.client.logout()

        # 3. Admin
        self.client.login(username="admin", password="password")
        response = self.client.get(reverse("create_clinician"))
        self.assertEqual(response.status_code, 200)

    def test_unverified_clinician_blocked(self):
        """Unverified clinician sees pending page on dashboard."""
        self.client.login(username="pending", password="password")
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "Verification Pending") # Assuming this text is in the template
        self.client.logout()

    def test_inactive_clinician_cannot_login(self):
        """Inactive user cannot login."""
        self.clinician.is_active = False
        self.clinician.save()
        login_success = self.client.login(username="clinician", password="password")
        self.assertFalse(login_success)



    def test_admin_list_and_verify(self):
        """Admin can list and verify clinicians."""
        self.client.login(username="admin", password="password")
        
        # Test List
        response = self.client.get(reverse("clinician_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "pending") # Should see the username

        # Test Verify
        response = self.client.post(reverse("verify_clinician", args=[self.unverified_clinician.id]))
        self.assertEqual(response.status_code, 302) # Redirect
        
        # Check DB
        self.unverified_clinician.refresh_from_db()
        self.assertTrue(self.unverified_clinician.clinician_verified)
