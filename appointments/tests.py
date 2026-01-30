from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
import json

from accounts.models import User
from wellbeing.models import ChildProfile, CaregiverChild, WeeklyWellbeingEntry, WellbeingQuestion, WeeklyWellbeingAnswer
from .models import Appointment, ClinicianReview, SupportPlan

class AppointmentsTestCase(TestCase):
    def setUp(self):
        # Users
        self.caregiver = User.objects.create_user(username='cg1', password='pw', role='CAREGIVER')
        self.caregiver2 = User.objects.create_user(username='cg2', password='pw', role='CAREGIVER')
        
        self.clinician_valid = User.objects.create_user(username='cl1', password='pw', role='CLINICIAN', clinician_verified=True, is_active=True)
        self.clinician_invalid = User.objects.create_user(username='cl2', password='pw', role='CLINICIAN', clinician_verified=False, is_active=True)
        self.clinician2 = User.objects.create_user(username='cl3', password='pw', role='CLINICIAN', clinician_verified=True, is_active=True)
        
        self.practitioner = User.objects.create_user(username='pr1', password='pw', role='PRACTITIONER')

         # Child and relations
        self.child1 = ChildProfile.objects.create(name='Child 1', date_of_birth='2015-01-01', sex='m', jaundice='no', family_asd='no')
        self.child2 = ChildProfile.objects.create(name='Child 2', date_of_birth='2016-01-01', sex='f', jaundice='yes', family_asd='no')
        
        CaregiverChild.objects.create(caregiver=self.caregiver, child=self.child1)
        CaregiverChild.objects.create(caregiver=self.caregiver2, child=self.child2)

        # Questions for the entry
        for i in range(1, 11):
            WellbeingQuestion.objects.create(code=f'A{i}', text=f'Q{i}', domain='communication', order=i)
        
        # Entries
        self.entry_sub = WeeklyWellbeingEntry.objects.create(caregiver=self.caregiver, child=self.child1, week_start='2026-01-05', week_end='2026-01-11', status='SUBMITTED')
        for i in range(1, 11):
            q = WellbeingQuestion.objects.get(code=f'A{i}')
            ans = WeeklyWellbeingAnswer.objects.create(entry=self.entry_sub, question=q, slider_score=2)
            ans.compute_binary_from_slider()
            ans.save()

        self.entry_draft = WeeklyWellbeingEntry.objects.create(caregiver=self.caregiver, child=self.child1, week_start='2026-01-12', week_end='2026-01-18', status='DRAFT')
        
        self.entry_cg2 = WeeklyWellbeingEntry.objects.create(caregiver=self.caregiver2, child=self.child2, week_start='2026-01-05', week_end='2026-01-11', status='SUBMITTED')

        # Existing appointment
        self.appt1 = Appointment.objects.create(
            caregiver=self.caregiver, child=self.child1, clinician=self.clinician_valid, 
            reason_type='CASUAL', preferred_time_window='ANY', status='REQUESTED'
        )

        self.client = Client()

    def test_caregiver_create_foreign_child(self):
        self.client.login(username='cg1', password='pw')
        response = self.client.post(reverse('caregiver_request_appointment'), {
            'child': self.child2.id,
            'reason_type': 'CASUAL',
            'reason_text': 'test',
            'preferred_time_window': 'ANY',
            'clinician': self.clinician_valid.id
        })
        # Should not create because child2 isn't in queryset
        self.assertEqual(Appointment.objects.count(), 1)
        self.assertTrue(response.context['form'].errors)

    def test_caregiver_create_invalid_entry(self):
        self.client.login(username='cg1', password='pw')
        # Draft entry
        response = self.client.post(reverse('caregiver_request_appointment'), {
            'child': self.child1.id,
            'reason_type': 'CASUAL',
            'reason_text': 'test',
            'preferred_time_window': 'ANY',
            'clinician': self.clinician_valid.id,
            'entry': self.entry_draft.id
        })
        self.assertIn('entry', response.context['form'].errors)
        
        # Foreign entry
        response2 = self.client.post(reverse('caregiver_request_appointment'), {
            'child': self.child1.id,
            'reason_type': 'CASUAL',
            'reason_text': 'test',
            'preferred_time_window': 'ANY',
            'clinician': self.clinician_valid.id,
            'entry': self.entry_cg2.id
        })
        self.assertIn('entry', response2.context['form'].errors)

    def test_clinician_assigned_only(self):
        # Create an appointment for clinician2
        Appointment.objects.create(caregiver=self.caregiver, child=self.child1, clinician=self.clinician2, reason_type='CASUAL', preferred_time_window='ANY')
        
        self.client.login(username='cl1', password='pw')
        res = self.client.get(reverse('clinician_appointment_list'))
        self.assertEqual(len(res.context['appointments']), 1)
        self.assertEqual(res.context['appointments'][0].id, self.appt1.id)

    def test_unverified_clinician_blocked(self):
        self.client.login(username='cl2', password='pw')
        # Expect redirect to login or not-authorized
        res = self.client.get(reverse('clinician_appointment_list'))
        self.assertRedirects(res, '/not-authorized/?next=/appointments/clinician/', fetch_redirect_response=False)
        
    def test_clinician_report_json(self):
        self.appt1.entry = self.entry_sub
        self.appt1.save()
        
        self.client.login(username='cl1', password='pw')
        res = self.client.get(reverse('clinician_appointment_report_json', args=[self.appt1.id]))
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('age_years', data)
        self.assertIn('a1', data)
        self.assertIn('a10', data)
        self.assertEqual(len(data.keys()), 14) # 4 bio + 10 features

    def test_cross_user_access_404(self):
        self.client.login(username='cg2', password='pw')
        res = self.client.get(reverse('caregiver_appointment_detail', args=[self.appt1.id]))
        self.assertEqual(res.status_code, 404)
        
        # Unverified clinician will get 302 to /not-authorized/
        # Use verified clinician2
        self.client.login(username='cl3', password='pw')
        res = self.client.get(reverse('clinician_appointment_detail', args=[self.appt1.id]))
        self.assertEqual(res.status_code, 404)
