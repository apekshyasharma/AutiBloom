"""
Comprehensive End-to-End Test Suite for AutiBloom Platform
Tests Auth, Wellbeing Tracking, and ML JSON Export.
"""
import datetime
import json
import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "autibloom.settings")
django.setup()

from django.test import TestCase, Client
from django.urls import reverse, resolve, NoReverseMatch
from django.utils import timezone
from accounts.models import User
from wellbeing.models import (
    ChildProfile, CaregiverChild, WellbeingQuestion,
    WeeklyWellbeingEntry, WeeklyWellbeingAnswer
)


# ============================================================
# FEATURE 1: Authentication & Authorization
# ============================================================

class TestCaregiverSignup(TestCase):
    def test_signup_page_loads(self):
        resp = self.client.get(reverse('caregiver_signup'))
        self.assertEqual(resp.status_code, 200)

    def test_signup_creates_caregiver(self):
        resp = self.client.post(reverse('caregiver_signup'), {
            'username': 'testcg',
            'email': 'cg@test.com',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
        })
        self.assertEqual(resp.status_code, 302)  # redirect to login
        user = User.objects.get(username='testcg')
        self.assertEqual(user.role, User.Role.CAREGIVER)
        self.assertTrue(user.is_caregiver())

    def test_signup_invalid_shows_form(self):
        resp = self.client.post(reverse('caregiver_signup'), {
            'username': 'testcg',
            'password1': 'a',
            'password2': 'b',
        })
        self.assertEqual(resp.status_code, 200)  # re-renders form


class TestLoginLogout(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='cg1', password='pass1234!', role=User.Role.CAREGIVER
        )

    def test_login_page_loads(self):
        resp = self.client.get(reverse('login'))
        self.assertEqual(resp.status_code, 200)

    def test_login_success(self):
        resp = self.client.post(reverse('login'), {
            'username': 'cg1', 'password': 'pass1234!'
        })
        self.assertEqual(resp.status_code, 302)  # redirect to dashboard

    def test_login_failure(self):
        resp = self.client.post(reverse('login'), {
            'username': 'cg1', 'password': 'wrong'
        })
        self.assertEqual(resp.status_code, 200)  # re-renders login form

    def test_logout(self):
        self.client.login(username='cg1', password='pass1234!')
        resp = self.client.post(reverse('logout'))
        # Django 6.x LogoutView requires POST and redirects
        self.assertIn(resp.status_code, [200, 302])


class TestDashboardRouting(TestCase):
    def test_caregiver_dashboard(self):
        user = User.objects.create_user(
            username='cg', password='pass1234!', role=User.Role.CAREGIVER
        )
        self.client.login(username='cg', password='pass1234!')
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 302)
        # Without a child, the caregiver is redirected to the child creation (onboarding) page
        self.assertEqual(resp.url, reverse('wellbeing_child_create'))

    def test_admin_dashboard(self):
        user = User.objects.create_user(
            username='admin1', password='pass1234!', role=User.Role.ADMIN
        )
        self.client.login(username='admin1', password='pass1234!')
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'accounts/dashboard_admin.html')

    def test_clinician_verified_dashboard(self):
        user = User.objects.create_user(
            username='clin1', password='pass1234!', role=User.Role.CLINICIAN
        )
        user.clinician_verified = True
        user.save()
        self.client.login(username='clin1', password='pass1234!')
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'accounts/dashboard_clinician.html')

    def test_clinician_unverified_pending(self):
        user = User.objects.create_user(
            username='clin2', password='pass1234!', role=User.Role.CLINICIAN
        )
        user.clinician_verified = False
        user.save()
        self.client.login(username='clin2', password='pass1234!')
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'accounts/clinician_pending.html')

    def test_unauthenticated_redirects_to_login(self):
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('login', resp.url)

    def test_home_resolves_to_dashboard(self):
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 302)  # redirect to login (not logged in)


class TestAdminClinicianManagement(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin', password='adm1234!', role=User.Role.ADMIN
        )
        self.caregiver = User.objects.create_user(
            username='cg', password='cg1234!', role=User.Role.CAREGIVER
        )
        self.client.login(username='admin', password='adm1234!')

    def test_create_clinician_page_loads(self):
        resp = self.client.get(reverse('create_clinician'))
        self.assertEqual(resp.status_code, 200)

    def test_create_clinician_success(self):
        resp = self.client.post(reverse('create_clinician'), {
            'username': 'newclin',
            'email': 'clin@test.com',
            'password': 'ClinPass123!',
        })
        self.assertEqual(resp.status_code, 302)  # redirect to dashboard
        clin = User.objects.get(username='newclin')
        self.assertEqual(clin.role, User.Role.CLINICIAN)
        self.assertTrue(clin.clinician_verified)

    def test_create_duplicate_clinician(self):
        User.objects.create_user(username='dup', password='x', role=User.Role.CLINICIAN)
        resp = self.client.post(reverse('create_clinician'), {
            'username': 'dup', 'email': '', 'password': 'x',
        })
        self.assertEqual(resp.status_code, 200)  # re-renders with error

    def test_clinician_list(self):
        User.objects.create_user(
            username='clin_a', password='x', role=User.Role.CLINICIAN
        )
        resp = self.client.get(reverse('clinician_list'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'clin_a')

    def test_verify_clinician(self):
        clin = User.objects.create_user(
            username='clin_v', password='x', role=User.Role.CLINICIAN
        )
        resp = self.client.post(reverse('verify_clinician', args=[clin.id]))
        self.assertEqual(resp.status_code, 302)
        clin.refresh_from_db()
        self.assertTrue(clin.clinician_verified)

    def test_unverify_clinician(self):
        clin = User.objects.create_user(
            username='clin_u', password='x', role=User.Role.CLINICIAN
        )
        clin.clinician_verified = True
        clin.save()
        resp = self.client.post(reverse('unverify_clinician', args=[clin.id]))
        self.assertEqual(resp.status_code, 302)
        clin.refresh_from_db()
        self.assertFalse(clin.clinician_verified)

    def test_deactivate_clinician(self):
        clin = User.objects.create_user(
            username='clin_d', password='x', role=User.Role.CLINICIAN
        )
        resp = self.client.post(reverse('deactivate_clinician', args=[clin.id]))
        self.assertEqual(resp.status_code, 302)
        clin.refresh_from_db()
        self.assertFalse(clin.is_active)

    def test_activate_clinician(self):
        clin = User.objects.create_user(
            username='clin_act', password='x', role=User.Role.CLINICIAN
        )
        clin.is_active = False
        clin.save()
        resp = self.client.post(reverse('activate_clinician', args=[clin.id]))
        self.assertEqual(resp.status_code, 302)
        clin.refresh_from_db()
        self.assertTrue(clin.is_active)


class TestPermissionRestrictions(TestCase):
    def setUp(self):
        self.caregiver = User.objects.create_user(
            username='cg', password='cg1234!', role=User.Role.CAREGIVER
        )
        self.clinician = User.objects.create_user(
            username='clin', password='clin1234!', role=User.Role.CLINICIAN
        )

    def test_caregiver_cannot_access_clinician_list(self):
        self.client.login(username='cg', password='cg1234!')
        resp = self.client.get(reverse('clinician_list'))
        self.assertIn(resp.status_code, [302, 403])

    def test_caregiver_cannot_create_clinician(self):
        self.client.login(username='cg', password='cg1234!')
        resp = self.client.get(reverse('create_clinician'))
        self.assertIn(resp.status_code, [302, 403])

    def test_clinician_cannot_access_admin_pages(self):
        self.client.login(username='clin', password='clin1234!')
        resp = self.client.get(reverse('clinician_list'))
        self.assertIn(resp.status_code, [302, 403])

    def test_clinician_cannot_access_wellbeing_child_list(self):
        self.client.login(username='clin', password='clin1234!')
        resp = self.client.get(reverse('wellbeing_child_list'))
        self.assertIn(resp.status_code, [302, 403])


class TestPasswordReset(TestCase):
    def test_password_reset_form_loads(self):
        resp = self.client.get(reverse('password_reset'))
        self.assertEqual(resp.status_code, 200)


# ============================================================
# FEATURE 2: Wellbeing Tracking
# ============================================================

class TestChildCRUD(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='cg', password='cg1234!', role=User.Role.CAREGIVER
        )
        self.client.login(username='cg', password='cg1234!')

    def test_child_list_empty(self):
        resp = self.client.get(reverse('wellbeing_child_list'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'No children profiles found')

    def test_child_create(self):
        resp = self.client.post(reverse('wellbeing_child_create'), {
            'name': 'Alice',
            'date_of_birth': '2020-05-15',
            'sex': 'f',
            'jaundice': 'no',
            'family_asd': 'no',
            'notes': 'Test child',
        })
        self.assertEqual(resp.status_code, 302)  # redirect to list
        child = ChildProfile.objects.get(name='Alice')
        self.assertEqual(child.sex, 'f')
        # Check relationship created
        rel = CaregiverChild.objects.get(caregiver=self.user, child=child)
        self.assertIsNotNone(rel)

    def test_child_detail(self):
        child = ChildProfile.objects.create(name='Bob', date_of_birth='2019-01-01')
        CaregiverChild.objects.create(caregiver=self.user, child=child)
        resp = self.client.get(reverse('wellbeing_child_detail', args=[child.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Bob')

    def test_child_edit(self):
        child = ChildProfile.objects.create(name='Charlie', date_of_birth='2019-01-01')
        CaregiverChild.objects.create(caregiver=self.user, child=child)
        resp = self.client.post(reverse('wellbeing_child_edit', args=[child.id]), {
            'name': 'Charlie Updated',
            'date_of_birth': '2019-01-01',
            'sex': 'm',
            'jaundice': 'yes',
            'family_asd': 'no',
        })
        self.assertEqual(resp.status_code, 302)
        child.refresh_from_db()
        self.assertEqual(child.name, 'Charlie Updated')
        self.assertEqual(child.sex, 'm')

    def test_child_detail_other_caregiver_404(self):
        """A caregiver cannot access another caregiver's child."""
        other = User.objects.create_user(
            username='other', password='x', role=User.Role.CAREGIVER
        )
        child = ChildProfile.objects.create(name='OtherChild')
        CaregiverChild.objects.create(caregiver=other, child=child)
        resp = self.client.get(reverse('wellbeing_child_detail', args=[child.id]))
        self.assertEqual(resp.status_code, 404)


def _seed_questions():
    """Seed the 10 wellbeing questions for tests."""
    questions_data = [
        ("A1", "communication", "Q1 text", 1),
        ("A2", "communication", "Q2 text", 2),
        ("A3", "emotional_responses", "Q3 text", 3),
        ("A4", "routines", "Q4 text", 4),
        ("A5", "routines", "Q5 text", 5),
        ("A6", "sensory_behaviors", "Q6 text", 6),
        ("A7", "communication", "Q7 text", 7),
        ("A8", "emotional_responses", "Q8 text", 8),
        ("A9", "sensory_behaviors", "Q9 text", 9),
        ("A10", "routines", "Q10 text", 10),
    ]
    for code, domain, text, order in questions_data:
        WellbeingQuestion.objects.get_or_create(
            code=code, defaults={'domain': domain, 'text': text, 'order': order}
        )


class TestEntryWorkflow(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='cg', password='cg1234!', role=User.Role.CAREGIVER
        )
        self.client.login(username='cg', password='cg1234!')
        self.child = ChildProfile.objects.create(
            name='Test Child', date_of_birth=datetime.date(2020, 1, 1),
            sex='m', jaundice='no', family_asd='no'
        )
        CaregiverChild.objects.create(caregiver=self.user, child=self.child)
        _seed_questions()

    def test_entry_start_creates_draft(self):
        resp = self.client.get(reverse('wellbeing_entry_start', args=[self.child.id]))
        self.assertEqual(resp.status_code, 302)  # redirects to edit
        entry = WeeklyWellbeingEntry.objects.get(child=self.child)
        self.assertEqual(entry.status, 'DRAFT')
        # 10 answer shells created
        self.assertEqual(entry.answers.count(), 10)

    def test_entry_start_idempotent(self):
        """Starting entry for same week again retrieves existing draft."""
        self.client.get(reverse('wellbeing_entry_start', args=[self.child.id]))
        self.client.get(reverse('wellbeing_entry_start', args=[self.child.id]))
        self.assertEqual(WeeklyWellbeingEntry.objects.filter(child=self.child).count(), 1)

    def test_entry_start_with_explicit_date(self):
        resp = self.client.get(
            reverse('wellbeing_entry_start', args=[self.child.id]) + '?week_start=2025-06-04'
        )
        self.assertEqual(resp.status_code, 302)
        entry = WeeklyWellbeingEntry.objects.get(child=self.child)
        self.assertEqual(entry.week_start, datetime.date(2025, 6, 2))  # Monday of that week

    def test_entry_edit_page_loads(self):
        self.client.get(reverse('wellbeing_entry_start', args=[self.child.id]))
        entry = WeeklyWellbeingEntry.objects.get(child=self.child)
        resp = self.client.get(reverse('wellbeing_entry_edit', args=[entry.id]))
        self.assertEqual(resp.status_code, 200)

    def test_entry_submit_requires_all_answers(self):
        """Submit should fail if any answer is missing."""
        self.client.get(reverse('wellbeing_entry_start', args=[self.child.id]))
        entry = WeeklyWellbeingEntry.objects.get(child=self.child)
        resp = self.client.post(reverse('wellbeing_entry_submit', args=[entry.id]))
        self.assertEqual(resp.status_code, 302)  # redirect back to edit
        entry.refresh_from_db()
        self.assertEqual(entry.status, 'DRAFT')  # still draft

    def test_entry_submit_success(self):
        """Full flow: start → fill all answers → submit."""
        self.client.get(reverse('wellbeing_entry_start', args=[self.child.id]))
        entry = WeeklyWellbeingEntry.objects.get(child=self.child)

        # Fill all 10 answers directly in the DB (simulating form save)
        for answer in entry.answers.all():
            answer.slider_score = 3
            answer.save()  # triggers binary_flag computation

        resp = self.client.post(reverse('wellbeing_entry_submit', args=[entry.id]))
        self.assertEqual(resp.status_code, 302)
        entry.refresh_from_db()
        self.assertEqual(entry.status, 'SUBMITTED')
        self.assertIsNotNone(entry.submitted_at)

    def test_entry_submit_only_post(self):
        """GET to submit should redirect, not submit."""
        self.client.get(reverse('wellbeing_entry_start', args=[self.child.id]))
        entry = WeeklyWellbeingEntry.objects.get(child=self.child)
        resp = self.client.get(reverse('wellbeing_entry_submit', args=[entry.id]))
        self.assertEqual(resp.status_code, 302)
        entry.refresh_from_db()
        self.assertEqual(entry.status, 'DRAFT')


class TestModelValidation(TestCase):
    def test_weekly_entry_week_end_mismatch(self):
        user = User.objects.create_user(
            username='cg', password='x', role=User.Role.CAREGIVER
        )
        child = ChildProfile.objects.create(name='X')
        from django.core.exceptions import ValidationError
        entry = WeeklyWellbeingEntry(
            caregiver=user, child=child,
            week_start=datetime.date(2025, 2, 10),
            week_end=datetime.date(2025, 2, 20),  # wrong! should be +6
        )
        with self.assertRaises(ValidationError):
            entry.full_clean()

    def test_binary_flag_computation(self):
        user = User.objects.create_user(
            username='cg', password='x', role=User.Role.CAREGIVER
        )
        child = ChildProfile.objects.create(name='Y')
        _seed_questions()
        entry = WeeklyWellbeingEntry.objects.create(
            caregiver=user, child=child,
            week_start=datetime.date(2025, 2, 10),
            week_end=datetime.date(2025, 2, 16),
        )
        q = WellbeingQuestion.objects.first()

        # Score 0 → binary should be 1 (risk)
        ans = WeeklyWellbeingAnswer.objects.create(entry=entry, question=q, slider_score=0)
        self.assertEqual(ans.binary_flag, 1)

        # Score 1 → binary should be 1 (risk)
        ans.slider_score = 1
        ans.save()
        self.assertEqual(ans.binary_flag, 1)

        # Score 2 → binary should be 0 (no risk)
        ans.slider_score = 2
        ans.save()
        self.assertEqual(ans.binary_flag, 0)

        # Score 4 → binary should be 0
        ans.slider_score = 4
        ans.save()
        self.assertEqual(ans.binary_flag, 0)

    def test_metrics_recomputation(self):
        user = User.objects.create_user(
            username='cg2', password='x', role=User.Role.CAREGIVER
        )
        child = ChildProfile.objects.create(name='Z')
        _seed_questions()
        entry = WeeklyWellbeingEntry.objects.create(
            caregiver=user, child=child,
            week_start=datetime.date(2025, 2, 10),
            week_end=datetime.date(2025, 2, 16),
        )
        # Fill answers
        for q in WellbeingQuestion.objects.all():
            WeeklyWellbeingAnswer.objects.create(entry=entry, question=q, slider_score=2)

        entry.refresh_from_db()
        self.assertIsNotNone(entry.overall_score)
        self.assertAlmostEqual(entry.overall_score, 2.0)


# ============================================================
# FEATURE 3: ML JSON Export
# ============================================================

class TestMLJSONExport(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='cg', password='cg1234!', role=User.Role.CAREGIVER
        )
        self.client.login(username='cg', password='cg1234!')
        _seed_questions()

    def _create_submitted_entry(self, child):
        entry = WeeklyWellbeingEntry.objects.create(
            caregiver=self.user, child=child,
            week_start=datetime.date(2025, 2, 10),
            week_end=datetime.date(2025, 2, 16),
        )
        for q in WellbeingQuestion.objects.all():
            WeeklyWellbeingAnswer.objects.create(entry=entry, question=q, slider_score=3)
        entry.status = 'SUBMITTED'
        entry.submitted_at = timezone.now()
        entry.save()
        return entry

    def test_export_success(self):
        child = ChildProfile.objects.create(
            name='E1', date_of_birth=datetime.date(2020, 6, 15),
            sex='f', jaundice='no', family_asd='yes'
        )
        CaregiverChild.objects.create(caregiver=self.user, child=child)
        entry = self._create_submitted_entry(child)

        resp = self.client.get(reverse('wellbeing_entry_export_json', args=[entry.id]))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # Check demographics
        self.assertIn('age_years', data)
        self.assertEqual(data['sex'], 'f')
        self.assertEqual(data['jaundice'], 'no')
        self.assertEqual(data['family_asd'], 'yes')
        # Check all 10 answer keys
        for i in range(1, 11):
            key = f'a{i}'
            self.assertIn(key, data, f"Missing key {key}")
            self.assertIn(data[key], [0, 1], f"Invalid binary value for {key}")

    def test_export_rejects_draft(self):
        child = ChildProfile.objects.create(
            name='E2', date_of_birth=datetime.date(2020, 1, 1),
            sex='m', jaundice='no', family_asd='no'
        )
        CaregiverChild.objects.create(caregiver=self.user, child=child)
        entry = WeeklyWellbeingEntry.objects.create(
            caregiver=self.user, child=child,
            week_start=datetime.date(2025, 2, 10),
            week_end=datetime.date(2025, 2, 16),
        )
        resp = self.client.get(reverse('wellbeing_entry_export_json', args=[entry.id]))
        self.assertEqual(resp.status_code, 400)

    def test_export_rejects_missing_demographics(self):
        child = ChildProfile.objects.create(
            name='E3', date_of_birth=datetime.date(2020, 1, 1),
            sex='m',  # jaundice and family_asd missing
        )
        CaregiverChild.objects.create(caregiver=self.user, child=child)
        entry = self._create_submitted_entry(child)

        resp = self.client.get(reverse('wellbeing_entry_export_json', args=[entry.id]))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('export_blocked', resp.url)

    def test_export_rejects_missing_dob(self):
        child = ChildProfile.objects.create(
            name='E4', sex='m', jaundice='no', family_asd='no',
            # no date_of_birth
        )
        CaregiverChild.objects.create(caregiver=self.user, child=child)
        entry = self._create_submitted_entry(child)

        resp = self.client.get(reverse('wellbeing_entry_export_json', args=[entry.id]))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('export_blocked', resp.url)

    def test_export_other_caregiver_blocked(self):
        """One caregiver cannot export another's entry."""
        other = User.objects.create_user(
            username='other', password='x', role=User.Role.CAREGIVER
        )
        child = ChildProfile.objects.create(
            name='E5', date_of_birth=datetime.date(2020, 1, 1),
            sex='m', jaundice='no', family_asd='no'
        )
        CaregiverChild.objects.create(caregiver=other, child=child)
        entry = WeeklyWellbeingEntry.objects.create(
            caregiver=other, child=child,
            week_start=datetime.date(2025, 2, 10),
            week_end=datetime.date(2025, 2, 16),
            status='SUBMITTED', submitted_at=timezone.now()
        )
        for q in WellbeingQuestion.objects.all():
            WeeklyWellbeingAnswer.objects.create(entry=entry, question=q, slider_score=3)

        resp = self.client.get(reverse('wellbeing_entry_export_json', args=[entry.id]))
        self.assertEqual(resp.status_code, 404)


# ============================================================
# URL Resolution Tests
# ============================================================

class TestURLResolution(TestCase):
    """Verify all expected URL names resolve without errors."""

    def test_all_url_names_resolve(self):
        simple_names = [
            'login', 'logout', 'caregiver_signup', 'dashboard', 'home',
            'create_clinician', 'clinician_list',
            'wellbeing_child_list', 'wellbeing_child_create',
            'password_reset',
        ]
        for name in simple_names:
            try:
                url = reverse(name)
                self.assertTrue(len(url) > 0, f"URL for '{name}' is empty")
            except NoReverseMatch:
                self.fail(f"URL name '{name}' does not resolve")

    def test_parameterized_urls_resolve(self):
        parameterized = [
            ('verify_clinician', [1]),
            ('unverify_clinician', [1]),
            ('activate_clinician', [1]),
            ('deactivate_clinician', [1]),
            ('wellbeing_child_detail', [1]),
            ('wellbeing_child_edit', [1]),
            ('wellbeing_entry_start', [1]),
            ('wellbeing_entry_edit', [1]),
            ('wellbeing_entry_submit', [1]),
            ('wellbeing_entry_export_json', [1]),
        ]
        for name, args in parameterized:
            try:
                url = reverse(name, args=args)
                self.assertTrue(len(url) > 0, f"URL for '{name}' is empty")
            except NoReverseMatch:
                self.fail(f"URL name '{name}' with args {args} does not resolve")
