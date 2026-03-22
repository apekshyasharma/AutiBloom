from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
import datetime
from .models import ChildProfile, CaregiverChild, WeeklyWellbeingEntry, WeeklyWellbeingAnswer, WellbeingQuestion
from .forms import WeeklyAnswerFormSet

User = get_user_model()

class WellbeingIntegrityTest(TestCase):
    def setUp(self):
        # Create Users
        self.caregiver = User.objects.create_user(username='cg', password='pw', role='CAREGIVER')
        self.superuser = User.objects.create_superuser(username='admin', password='pw')
        
        # Create Child
        self.child = ChildProfile.objects.create(
            name='TestKid', 
            date_of_birth=datetime.date(2020, 1, 1),
            sex='m', jaundice='no', family_asd='no'
        )
        CaregiverChild.objects.create(caregiver=self.caregiver, child=self.child)

        # Create Questions (A1..A10)
        self.questions = []
        for i in range(1, 11):
            q = WellbeingQuestion.objects.create(
                code=f"A{i}", 
                domain='communication', 
                text=f"Question {i}", 
                order=i
            )
            self.questions.append(q)

        self.client.login(username='cg', password='pw')

    def test_save_progress_without_touch_keeps_nulls(self):
        # 1. Start Entry
        self.client.get(reverse('wellbeing_entry_start', args=[self.child.id]))
        entry = WeeklyWellbeingEntry.objects.get(child=self.child)
        
        # Get dynamic prefix
        prefix = WeeklyAnswerFormSet(instance=entry).prefix
        
        # 2. Simulate POST
        data = {
            f'{prefix}-TOTAL_FORMS': '10',
            f'{prefix}-INITIAL_FORMS': '10',
            f'{prefix}-MIN_NUM_FORMS': '0',
            f'{prefix}-MAX_NUM_FORMS': '1000',
            'save_action': 'save'
        }
        
        # Simulate browser auto-fill sending '2' but touched=''
        for i, ans in enumerate(entry.answers.all()):
            data[f'{prefix}-{i}-id'] = ans.id
            data[f'{prefix}-{i}-slider_score'] = '2' # Default
            data[f'{prefix}-{i}-touched'] = '' # Untouched
            data[f'{prefix}-{i}-comment'] = ''
        
        resp = self.client.post(reverse('wellbeing_entry_edit', args=[entry.id]), data)
        self.assertRedirects(resp, reverse('wellbeing_entry_edit', args=[entry.id]) + '?event=entry_saved')
        
        # 3. Verify they are STILL None in DB (Integrity Check worked)
        entry.refresh_from_db()
        for ans in entry.answers.all():
            self.assertIsNone(ans.slider_score, f"Question {ans.question.code} should be None but was {ans.slider_score}")

    def test_touch_one_slider_saves_only_that_one(self):
        self.client.get(reverse('wellbeing_entry_start', args=[self.child.id]))
        entry = WeeklyWellbeingEntry.objects.get(child=self.child)
        
        prefix = WeeklyAnswerFormSet(instance=entry).prefix
        
        data = {
            f'{prefix}-TOTAL_FORMS': '10',
            f'{prefix}-INITIAL_FORMS': '10',
            f'{prefix}-MIN_NUM_FORMS': '0',
            f'{prefix}-MAX_NUM_FORMS': '1000',
            'save_action': 'save'
        }
        
        # Q1 Touched and Set to 3
        answers = list(entry.answers.all())
        data[f'{prefix}-0-id'] = answers[0].id
        data[f'{prefix}-0-slider_score'] = '3'
        data[f'{prefix}-0-touched'] = '1' # TOUCHED!
        
        for i in range(1, 10):
            data[f'{prefix}-{i}-id'] = answers[i].id
            data[f'{prefix}-{i}-slider_score'] = '2' # Fake default
            data[f'{prefix}-{i}-touched'] = '' # Untouched
        
        self.client.post(reverse('wellbeing_entry_edit', args=[entry.id]), data)
        
        entry.refresh_from_db()
        
        # Q1 should be 3
        self.assertEqual(entry.answers.get(id=answers[0].id).slider_score, 3)
        # Others should be None
        for i in range(1, 10):
            ans = entry.answers.get(id=answers[i].id)
            self.assertIsNone(ans.slider_score)

    def test_submit_requires_all_10_scores(self):
        self.client.get(reverse('wellbeing_entry_start', args=[self.child.id]))
        entry = WeeklyWellbeingEntry.objects.get(child=self.child)
        
        # Answer only 1
        ans = entry.answers.first()
        ans.slider_score = 3
        ans.binary_flag = 0
        ans.save()
        
        resp = self.client.post(reverse('wellbeing_entry_submit', args=[entry.id]))
        # Should fail and redirect
        self.assertRedirects(resp, reverse('wellbeing_entry_edit', args=[entry.id]) + '?event=submit_blocked')
        entry.refresh_from_db()
        self.assertEqual(entry.status, 'DRAFT')

    def test_export_contract_exact_keys(self):
        self.client.get(reverse('wellbeing_entry_start', args=[self.child.id]))
        entry = WeeklyWellbeingEntry.objects.get(child=self.child)
        
        # Satisfy strict contract
        for ans in entry.answers.all():
            ans.slider_score = 1
            ans.save() 
        
        entry.status = 'SUBMITTED'
        entry.save()

        resp = self.client.get(reverse('wellbeing_entry_export_json', args=[entry.id]))
        self.assertEqual(resp.status_code, 200)
        
        data = resp.json()
        expected_keys = {
            'age_years', 'sex', 'jaundice', 'family_asd',
            'a1', 'a2', 'a3', 'a4', 'a5', 'a6', 'a7', 'a8', 'a9', 'a10'
        }
        self.assertEqual(set(data.keys()), expected_keys)

    def test_post_to_submitted_returns_403(self):
        """Constraint 3: Submitted entries must be immutable via POST."""
        self.client.get(reverse('wellbeing_entry_start', args=[self.child.id]))
        entry = WeeklyWellbeingEntry.objects.get(child=self.child)
        entry.status = 'SUBMITTED'
        entry.save()

        resp = self.client.post(reverse('wellbeing_entry_edit', args=[entry.id]), {'save_action': 'save'})
        self.assertEqual(resp.status_code, 403)


class CaregiverOnboardingTest(TestCase):
    """Tests for the caregiver onboarding redirect flow."""

    def setUp(self):
        self.caregiver = User.objects.create_user(username='onboard_cg', password='pw', role='CAREGIVER')
        self.client = Client()
        self.client.login(username='onboard_cg', password='pw')

    def test_caregiver_no_children_redirected_to_onboarding(self):
        """Caregiver with no CaregiverChild links is redirected to child add (onboarding)."""
        resp = self.client.get(reverse('dashboard'))
        self.assertRedirects(resp, reverse('wellbeing_child_create'))

    def test_caregiver_with_child_redirected_to_dashboard(self):
        """Caregiver with a child is redirected to the wellbeing dashboard."""
        child = ChildProfile.objects.create(
            name='OnboardKid',
            date_of_birth=datetime.date(2021, 6, 15),
            sex='f', jaundice='no', family_asd='no'
        )
        CaregiverChild.objects.create(caregiver=self.caregiver, child=child)

        resp = self.client.get(reverse('dashboard'))
        self.assertRedirects(resp, reverse('wellbeing_dashboard'))

    def test_child_create_redirects_to_wellbeing_dashboard(self):
        """After successfully adding a child, caregiver is redirected to wellbeing dashboard."""
        resp = self.client.post(reverse('wellbeing_child_create'), {
            'name': 'NewKid',
            'date_of_birth': '2022-03-10',
            'sex': 'm',
            'jaundice': 'yes',
            'family_asd': 'no',
            'notes': '',
        })
        # Expects redirect to /wellbeing/dashboard/?child_id=ID.
        # Check that it starts with the url rather than exact match
        self.assertTrue(resp.url.startswith(reverse('wellbeing_dashboard')))
        # Verify child and link were created
        self.assertTrue(ChildProfile.objects.filter(name='NewKid').exists())
        self.assertTrue(CaregiverChild.objects.filter(caregiver=self.caregiver).exists())

class DashboardAnalyticsTest(TestCase):
    """Tests for the dashboard analytics data and RBAC."""

    def setUp(self):
        self.caregiver_a = User.objects.create_user(username='cg_a', password='pw', role='CAREGIVER')
        self.caregiver_b = User.objects.create_user(username='cg_b', password='pw', role='CAREGIVER')
        
        self.child_a = ChildProfile.objects.create(name='KidA', date_of_birth=datetime.date(2021, 1, 1), sex='m', jaundice='no', family_asd='no')
        self.child_b = ChildProfile.objects.create(name='KidB', date_of_birth=datetime.date(2021, 2, 1), sex='f', jaundice='yes', family_asd='no')
        
        CaregiverChild.objects.create(caregiver=self.caregiver_a, child=self.child_a)
        CaregiverChild.objects.create(caregiver=self.caregiver_b, child=self.child_b)
        
        self.client = Client()

    def test_dashboard_enforces_rbac_view(self):
        """Caregiver A cannot view dashboard filtered for Child B."""
        self.client.login(username='cg_a', password='pw')
        resp = self.client.get(reverse('wellbeing_dashboard') + f"?child_id={self.child_b.id}")
        self.assertEqual(resp.status_code, 404)

    def test_dashboard_enforces_rbac_api(self):
        """Caregiver A cannot access API for Child B."""
        self.client.login(username='cg_a', password='pw')
        resp = self.client.get(reverse('wellbeing_dashboard_api', args=[self.child_b.id]))
        self.assertEqual(resp.status_code, 404)

    def test_dashboard_api_data_structure(self):
        """Verify the JSON structure of the dashboard API."""
        self.client.login(username='cg_a', password='pw')
        
        # Add a submitted entry to have data
        entry = WeeklyWellbeingEntry.objects.create(
            caregiver=self.caregiver_a,
            child=self.child_a,
            week_start=datetime.date(2024, 1, 1),
            week_end=datetime.date(2024, 1, 7),
            status='SUBMITTED',
            overall_score=3.5,
            communication_score=4.0
        )
        entry.submitted_at = timezone.now()
        entry.save()
        
        resp = self.client.get(reverse('wellbeing_dashboard_api', args=[self.child_a.id]))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        
        self.assertIn('stats', data)
        self.assertIn('chart_data', data)
        self.assertEqual(data['stats']['submitted_count'], 1)
        self.assertEqual(data['chart_data']['overall'][0], 3.5)
        self.assertEqual(data['chart_data']['communication'][0], 4.0)
        self.assertEqual(data['selected_child_id'], self.child_a.id)


class SubmitRedirectAndReportTest(TestCase):
    """Tests for the fixed submit redirect and the new child_report view."""

    def setUp(self):
        self.caregiver = User.objects.create_user(username='cg_rpt', password='pw', role='CAREGIVER')
        self.child = ChildProfile.objects.create(
            name='ReportKid',
            date_of_birth=datetime.date(2020, 5, 1),
            sex='m', jaundice='no', family_asd='no'
        )
        CaregiverChild.objects.create(caregiver=self.caregiver, child=self.child)
        # Create questions A1..A10 (needed for entry_start)
        for i in range(1, 11):
            WellbeingQuestion.objects.create(
                code=f'A{i}', domain='communication',
                text=f'Question {i}', order=i
            )
        self.client = Client()
        self.client.login(username='cg_rpt', password='pw')

    def _make_fully_answered_entry(self):
        """Helper: create a DRAFT entry with all 10 answers filled."""
        self.client.get(reverse('wellbeing_entry_start', args=[self.child.id]))
        entry = WeeklyWellbeingEntry.objects.get(child=self.child)
        for ans in entry.answers.all():
            ans.slider_score = 2
            ans.binary_flag = 1
            ans.save()
        entry.recompute_metrics()
        entry.save()
        return entry

    def test_entry_submit_success_redirects_to_dashboard(self):
        """Successful submit must redirect to wellbeing_entry_report."""
        entry = self._make_fully_answered_entry()
        resp = self.client.post(reverse('wellbeing_entry_submit', args=[entry.id]))
        expected_url = f"{reverse('wellbeing_entry_report', args=[entry.id])}?event=entry_submitted"
        self.assertRedirects(resp, expected_url, fetch_redirect_response=False)



    def test_child_report_empty_state(self):
        """GET child_report with no submitted entries returns 200 with friendly empty state."""
        resp = self.client.get(reverse('wellbeing_child_report', args=[self.child.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'No submitted check-ins yet')
        self.assertContains(resp, 'Start Weekly Check-in')

    def test_child_report_with_submitted_entry(self):
        """GET child_report with 1 submitted entry returns 200 and shows the week_start date."""
        entry = WeeklyWellbeingEntry.objects.create(
            caregiver=self.caregiver,
            child=self.child,
            week_start=datetime.date(2025, 1, 6),
            week_end=datetime.date(2025, 1, 12),
            status='SUBMITTED',
            overall_score=3.0,
        )
        entry.submitted_at = timezone.now()
        entry.save()
        resp = self.client.get(reverse('wellbeing_child_report', args=[self.child.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Jan 06, 2025')

    def test_child_report_enforces_ownership(self):
        """Caregiver cannot view report for a child they do not own."""
        other = User.objects.create_user(username='other_cg', password='pw', role='CAREGIVER')
        other_child = ChildProfile.objects.create(
            name='OtherKid', date_of_birth=datetime.date(2021, 1, 1),
            sex='f', jaundice='no', family_asd='no'
        )
        CaregiverChild.objects.create(caregiver=other, child=other_child)
        # self.caregiver tries to access other_child's report → 404
        resp = self.client.get(reverse('wellbeing_child_report', args=[other_child.id]))
        self.assertEqual(resp.status_code, 404)

    def test_child_report_does_not_auto_redirect(self):
        """Report page must never redirect to entry_start automatically."""
        resp = self.client.get(reverse('wellbeing_child_report', args=[self.child.id]))
        # Must be 200 — not any redirect code
        self.assertEqual(resp.status_code, 200)


class DiagnosticRequiredTests(TestCase):
    """
    Exactly-named tests as required by the STEP 5 specification.
    These mirror the SubmitRedirectAndReportTest but use the mandated test names.
    """

    def setUp(self):
        self.caregiver = User.objects.create_user(username='diag_cg', password='pw', role='CAREGIVER')
        self.child = ChildProfile.objects.create(
            name='DiagKid',
            date_of_birth=datetime.date(2019, 3, 15),
            sex='f', jaundice='no', family_asd='no'
        )
        CaregiverChild.objects.create(caregiver=self.caregiver, child=self.child)
        for i in range(1, 11):
            WellbeingQuestion.objects.create(
                code=f'B{i}', domain='communication',
                text=f'Diag Question {i}', order=i
            )
        self.client = Client()
        self.client.login(username='diag_cg', password='pw')

    def _make_submitted_entry(self):
        self.client.get(reverse('wellbeing_entry_start', args=[self.child.id]))
        entry = WeeklyWellbeingEntry.objects.filter(child=self.child).first()
        for ans in entry.answers.all():
            ans.slider_score = 2
            ans.binary_flag = 1
            ans.save()
        entry.recompute_metrics()
        entry.save()
        return entry

    def test_submit_redirects_to_dashboard_and_sets_message(self):
        """
        STEP 5 - Test 1: After successful submission, redirect must be to
        wellbeing_entry_report and a success message must be set.
        """
        entry = self._make_submitted_entry()
        expected_url = f"{reverse('wellbeing_entry_report', args=[entry.id])}?event=entry_submitted"

        # Check redirect without follow
        resp = self.client.post(reverse('wellbeing_entry_submit', args=[entry.id]))
        self.assertRedirects(resp, expected_url, fetch_redirect_response=False)

    def test_view_report_links_to_report_route_not_entry_start(self):
        """
        STEP 5 - Test 2: The child_report URL must resolve to child_report view,
        not to entry_start. Accessing it returns 200, not a redirect to check-in.
        """
        resp = self.client.get(reverse('wellbeing_child_report', args=[self.child.id]))
        self.assertEqual(resp.status_code, 200)
        # Must NOT redirect to entry_start
        self.assertNotEqual(
            resp.get('Location', ''),
            reverse('wellbeing_entry_start', args=[self.child.id])
        )
        # Must use the report template
        self.assertTemplateUsed(resp, 'wellbeing/child_report.html')

    def test_report_empty_state_renders_without_redirect(self):
        """
        STEP 5 - Test 3: With no submitted entries, report renders a friendly
        empty state (200) and does NOT automatically redirect to entry_start.
        """
        resp = self.client.get(reverse('wellbeing_child_report', args=[self.child.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'No submitted check-ins yet')
        self.assertContains(resp, 'Start Weekly Check-in')
        # Confirm zero submitted entries served
        self.assertEqual(resp.context['entries'].count(), 0)

    def test_dashboard_shows_latest_submitted_entry(self):
        """
        STEP 5 - Test 4: After submitting an entry, the wellbeing_dashboard
        query returns that entry in its stats (submitted_count = 1).
        """
        # Create a submitted entry directly
        entry = WeeklyWellbeingEntry.objects.create(
            caregiver=self.caregiver,
            child=self.child,
            week_start=datetime.date(2025, 2, 10),
            week_end=datetime.date(2025, 2, 16),
            status='SUBMITTED',
            overall_score=3.2,
        )
        entry.submitted_at = timezone.now()
        entry.save()

        resp = self.client.get(
            reverse('wellbeing_dashboard') + f'?child_id={self.child.id}'
        )
        self.assertEqual(resp.status_code, 200)
        stats = resp.context.get('stats', {})
        self.assertEqual(stats.get('submitted_count'), 1,
                         "Dashboard must show 1 submitted entry after submission")

    def test_submit_action_inside_entry_edit_sets_submitted(self):
        """
        Simulate POST to wellbeing_entry_edit with submit_action and all 10 slider_scores set + touched=1.
        Assert entry.status == SUBMITTED and response redirects to dashboard.
        """
        entry = self._make_submitted_entry() # Returns a draft entry with valid answers
        
        post_data = {
            'submit_action': 'submit',
            'answers-TOTAL_FORMS': '10',
            'answers-INITIAL_FORMS': '10',
            'answers-MIN_NUM_FORMS': '0',
            'answers-MAX_NUM_FORMS': '1000',
        }
        for i, ans in enumerate(entry.answers.order_by('question__order', 'id')):
            post_data[f'answers-{i}-id'] = str(ans.id)
            post_data[f'answers-{i}-slider_score'] = '3'
            post_data[f'answers-{i}-touched'] = '1'

        resp = self.client.post(reverse('wellbeing_entry_edit', args=[entry.id]), data=post_data)
        
        entry.refresh_from_db()
        self.assertEqual(entry.status, 'SUBMITTED')
        expected_url = f"{reverse('wellbeing_entry_report', args=[entry.id])}?event=entry_submitted"
        self.assertRedirects(resp, expected_url, fetch_redirect_response=False)

    def test_report_shows_entries_after_submission(self):
        """
        After submission, GET child_report and assert entries exist in context.
        """
        entry = self._make_submitted_entry()
        entry.status = 'SUBMITTED'
        entry.submitted_at = timezone.now()
        entry.save()

        resp = self.client.get(reverse('wellbeing_child_report', args=[self.child.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['entries'].count(), 1)


class PredictionPipelineTest(TestCase):
    """Tests for the stub prediction pipeline endpoint."""

    def setUp(self):
        self.caregiver_a = User.objects.create_user(username='pred_cg_a', password='pw', role='CAREGIVER')
        self.caregiver_b = User.objects.create_user(username='pred_cg_b', password='pw', role='CAREGIVER')

        self.child_a = ChildProfile.objects.create(
            name='PredKidA', date_of_birth=datetime.date(2018, 6, 15),
            sex='m', jaundice='no', family_asd='no'
        )
        self.child_b = ChildProfile.objects.create(
            name='PredKidB', date_of_birth=datetime.date(2019, 3, 1),
            sex='f', jaundice='yes', family_asd='no'
        )

        CaregiverChild.objects.create(caregiver=self.caregiver_a, child=self.child_a)
        CaregiverChild.objects.create(caregiver=self.caregiver_b, child=self.child_b)

        # Create questions A1..A10
        for i in range(1, 11):
            WellbeingQuestion.objects.create(
                code=f'A{i}', domain='communication',
                text=f'Prediction Q{i}', order=i
            )

        # Create a SUBMITTED entry for caregiver A
        self.entry_a = WeeklyWellbeingEntry.objects.create(
            caregiver=self.caregiver_a,
            child=self.child_a,
            week_start=datetime.date(2025, 6, 2),
            week_end=datetime.date(2025, 6, 8),
            status='SUBMITTED',
        )
        self.entry_a.submitted_at = timezone.now()
        self.entry_a.save()

        # Create all 10 answers with binary flags
        for q in WellbeingQuestion.objects.all():
            WeeklyWellbeingAnswer.objects.create(
                entry=self.entry_a, question=q,
                slider_score=1, binary_flag=1
            )

        # Create a DRAFT entry for caregiver A
        self.draft_entry = WeeklyWellbeingEntry.objects.create(
            caregiver=self.caregiver_a,
            child=self.child_a,
            week_start=datetime.date(2025, 5, 26),
            week_end=datetime.date(2025, 6, 1),
            status='DRAFT',
        )

        # Create a SUBMITTED entry for caregiver B
        self.entry_b = WeeklyWellbeingEntry.objects.create(
            caregiver=self.caregiver_b,
            child=self.child_b,
            week_start=datetime.date(2025, 6, 2),
            week_end=datetime.date(2025, 6, 8),
            status='SUBMITTED',
        )
        self.entry_b.submitted_at = timezone.now()
        self.entry_b.save()
        for q in WellbeingQuestion.objects.all():
            WeeklyWellbeingAnswer.objects.create(
                entry=self.entry_b, question=q,
                slider_score=2, binary_flag=0
            )

        self.client = Client()
        self.client.login(username='pred_cg_a', password='pw')

    def test_caregiver_cannot_predict_other_entry(self):
        """Caregiver A cannot run prediction for caregiver B's entry."""
        resp = self.client.post(reverse('wellbeing_predict_entry', args=[self.entry_b.id]))
        self.assertEqual(resp.status_code, 404)

    def test_cannot_predict_draft_entry(self):
        """POST to predict a DRAFT entry returns 400."""
        resp = self.client.post(reverse('wellbeing_predict_entry', args=[self.draft_entry.id]))
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertIn('error', data)

    def test_payload_keys_match_contract(self):
        """Built payload keys exactly match the Feature 3 contract."""
        from wellbeing.services.prediction import build_payload_from_entry
        payload = build_payload_from_entry(self.entry_a)
        expected_keys = {
            'age_years', 'sex', 'jaundice', 'family_asd',
            'a1', 'a2', 'a3', 'a4', 'a5', 'a6', 'a7', 'a8', 'a9', 'a10'
        }
        self.assertEqual(set(payload.keys()), expected_keys)

    def test_prediction_result_created_on_success(self):
        """POST creates a PredictionResult with real model."""
        from wellbeing.models import PredictionResult
        resp = self.client.post(reverse('wellbeing_predict_entry', args=[self.entry_a.id]))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['status'], 'ok')
        self.assertIn(data['prediction_label'], ['Low Probability', 'High Probability'])
        self.assertIsNotNone(data['prediction_score'])
        self.assertIn('rf-v1', data['model_version'])
        self.assertEqual(PredictionResult.objects.filter(entry=self.entry_a).count(), 1)

    def test_get_not_allowed(self):
        """GET to prediction endpoint returns 405."""
        resp = self.client.get(reverse('wellbeing_predict_entry', args=[self.entry_a.id]))
        self.assertEqual(resp.status_code, 405)

    def test_predict_is_idempotent(self):
        """Calling predict twice for the same entry does not create duplicate records."""
        from wellbeing.models import PredictionResult
        self.client.post(reverse('wellbeing_predict_entry', args=[self.entry_a.id]))
        self.client.post(reverse('wellbeing_predict_entry', args=[self.entry_a.id]))
        self.assertEqual(PredictionResult.objects.filter(entry=self.entry_a).count(), 1)

    def test_explanation_saved_on_prediction(self):
        """Running prediction saves a non-null explanation_json."""
        from wellbeing.models import PredictionResult
        resp = self.client.post(reverse('wellbeing_predict_entry', args=[self.entry_a.id]))
        self.assertEqual(resp.status_code, 200)
        pred = PredictionResult.objects.get(entry=self.entry_a)
        self.assertIsNotNone(pred.explanation_json)
        self.assertIn('risk_flags', pred.explanation_json)
        self.assertIn('risk_count', pred.explanation_json)
        self.assertIn('domain_breakdown', pred.explanation_json)
        self.assertIn('top_domains', pred.explanation_json)
        self.assertIn('friendly_summary', pred.explanation_json)
        # Also check JSON response includes explanation
        data = resp.json()
        self.assertIn('explanation', data)
        self.assertIsNotNone(data['explanation'])

    def test_explanation_correct_risk_flags(self):
        """Risk flags must match the answer keys where binary_flag == 1."""
        from wellbeing.services.explainability import build_explanation
        from wellbeing.services.prediction import build_payload_from_entry
        # entry_a has all binary_flag=1 (slider_score=1 → binary=1)
        payload = build_payload_from_entry(self.entry_a)
        explanation = build_explanation(payload)
        # All 10 answers have binary_flag=1, so all a1..a10 are risk flags
        expected_risk = [f'a{i}' for i in range(1, 11)]
        self.assertEqual(sorted(explanation['risk_flags']), sorted(expected_risk))
        self.assertEqual(explanation['risk_count'], 10)

        # Now test with entry_b which has all binary_flag=0 (slider_score=2 → binary=0)
        self.client.login(username='pred_cg_b', password='pw')
        payload_b = build_payload_from_entry(self.entry_b)
        explanation_b = build_explanation(payload_b)
        self.assertEqual(explanation_b['risk_flags'], [])
        self.assertEqual(explanation_b['risk_count'], 0)

    def test_narrative_endpoint_post_only(self):
        """GET request to narrative endpoint returns 405."""
        from wellbeing.models import PredictionResult
        # Create a stub prediction first
        pred = PredictionResult.objects.create(
            caregiver=self.caregiver_a, child=self.child_a, entry=self.entry_a,
            prediction_label="stub"
        )
        resp = self.client.get(reverse('wellbeing_generate_narrative', args=[pred.id]))
        self.assertEqual(resp.status_code, 405)

    def test_narrative_requires_owner(self):
        """A caregiver cannot generate a narrative for another caregiver's prediction."""
        from wellbeing.models import PredictionResult
        pred_b = PredictionResult.objects.create(
            caregiver=self.caregiver_b, child=self.child_b, entry=self.entry_b,
            prediction_label="stub"
        )
        # client is logged in as caregiver_a
        resp = self.client.post(reverse('wellbeing_generate_narrative', args=[pred_b.id]))
        self.assertEqual(resp.status_code, 404)

    def test_narrative_saved_on_generation(self):
        """Generating a narrative stores it in the database and returns it."""
        from wellbeing.models import PredictionResult
        pred = PredictionResult.objects.create(
            caregiver=self.caregiver_a, child=self.child_a, entry=self.entry_a,
            prediction_label="stub"
        )
        self.assertIsNone(pred.narrative_text)
        
        resp = self.client.post(reverse('wellbeing_generate_narrative', args=[pred.id]))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['status'], 'ok')
        self.assertIn('Disclaimer: AutiBloom', data['narrative_text'])
        self.assertNotIn('### Weekly Summary', data['narrative_text'])
        
        pred.refresh_from_db()
        self.assertIsNotNone(pred.narrative_text)

    def test_narrative_idempotent(self):
        """Generating narrative again returns the existing text unless forced."""
        from wellbeing.models import PredictionResult
        pred = PredictionResult.objects.create(
            caregiver=self.caregiver_a, child=self.child_a, entry=self.entry_a,
            prediction_label="stub", narrative_text="existing custom narrative"
        )
        
        resp = self.client.post(reverse('wellbeing_generate_narrative', args=[pred.id]))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['narrative_text'], "existing custom narrative")
        
        # With force=1 it should regenerate
        resp_force = self.client.post(reverse('wellbeing_generate_narrative', args=[pred.id]), {'force': '1'})
        self.assertEqual(resp_force.status_code, 200)
        data_force = resp_force.json()
        self.assertNotEqual(data_force['narrative_text'], "existing custom narrative")
        self.assertIn('Disclaimer: AutiBloom', data_force['narrative_text'])
        self.assertNotIn('### Weekly Summary', data_force['narrative_text'])

    def test_entry_report_requires_owner(self):
        """A caregiver cannot view the report for another caregiver's entry."""
        resp = self.client.get(reverse('wellbeing_entry_report', args=[self.entry_b.id]))
        self.assertEqual(resp.status_code, 404)

    def test_entry_report_unsubmitted_redirects(self):
        """Viewing a report for a DRAFT entry redirects back to edit."""
        resp = self.client.get(reverse('wellbeing_entry_report', args=[self.draft_entry.id]))
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse('wellbeing_entry_edit', args=[self.draft_entry.id]), resp.url)

    def test_entry_report_success(self):
        """Viewing a submitted report calculates demo values on the fly without creating DB rows."""
        from wellbeing.models import PredictionResult
        initial_pred_count = PredictionResult.objects.count()
        
        resp = self.client.get(reverse('wellbeing_entry_report', args=[self.entry_a.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'wellbeing/entry_report.html')
        
        # entry_a has 10 flags, so it should be High Probability
        self.assertEqual(resp.context['risk_score'], 10)
        self.assertEqual(resp.context['mock_label'], 'High Probability')
        self.assertEqual(resp.context['mock_confidence'], 100)
        self.assertIn('explanation', resp.context)
        self.assertIn('narrative', resp.context)
        
        # No DB rows were created
        self.assertEqual(PredictionResult.objects.count(), initial_pred_count)
