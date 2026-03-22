from django.test import TestCase
from django.urls import reverse
from accounts.models import User
from .models import CaregiverCommunityProfile, BlockedUser, Thread, Message

class CommunityTestCase(TestCase):
    def setUp(self):
        # Create 4 Caregiver users
        self.user_a = User.objects.create_user(username='A', password='pw', role=User.Role.CAREGIVER)
        self.user_b = User.objects.create_user(username='B', password='pw', role=User.Role.CAREGIVER)
        self.user_c = User.objects.create_user(username='C', password='pw', role=User.Role.CAREGIVER)
        self.non_participant = User.objects.create_user(username='N', password='pw', role=User.Role.CAREGIVER)
        
        # Another user but not caregiver
        self.clinician = User.objects.create_user(username='Cl', password='pw', role=User.Role.CLINICIAN)

    def test_caregiver_opt_in(self):
        self.client.login(username='A', password='pw')
        response = self.client.post(reverse('community_home'), {
            'opt_in': 'on',
            'city': 'New York',
            'postal_code': '10001',
            'bio': 'Test bio'
        })
        self.assertEqual(response.status_code, 200)  # Renders page with form_success inline
        profile = CaregiverCommunityProfile.objects.get(user=self.user_a)
        self.assertTrue(profile.opt_in)
        self.assertEqual(profile.city, 'New York')

    def test_nearby_list(self):
        # Setup profiles manually
        CaregiverCommunityProfile.objects.create(user=self.user_a, opt_in=True, city='City1', postal_code='111')
        CaregiverCommunityProfile.objects.create(user=self.user_b, opt_in=True, city='City1', postal_code='111')
        # Same city, different postal
        CaregiverCommunityProfile.objects.create(user=self.user_c, opt_in=True, city='City1', postal_code='222')
        # Not opted in
        CaregiverCommunityProfile.objects.create(user=self.non_participant, opt_in=False, city='City1')

        self.client.login(username='A', password='pw')
        res = self.client.get(reverse('community_home'))
        
        nearby = res.context['nearby_caregivers']
        nearby_ids = [c.user.id for c in nearby]
        
        self.assertIn(self.user_b.id, nearby_ids)
        self.assertIn(self.user_c.id, nearby_ids)
        self.assertNotIn(self.user_a.id, nearby_ids) # Excludes self
        self.assertNotIn(self.non_participant.id, nearby_ids) # Excludes non-optin

        # Ensure same postal code is first (User_b's postal code == User_a's postal code)
        self.assertEqual(nearby_ids[0], self.user_b.id)

    def test_start_thread_opt_in_blocked(self):
        # A opted in, B not opted in
        CaregiverCommunityProfile.objects.create(user=self.user_a, opt_in=True, city='City1')
        CaregiverCommunityProfile.objects.create(user=self.user_b, opt_in=False, city='City1')

        self.client.login(username='A', password='pw')
        res = self.client.get(reverse('community_start_thread', args=[self.user_b.id]))
        # Should redirect back to home due to error
        self.assertRedirects(res, reverse('community_home'))
        
        # Now B opts in
        profile_b = CaregiverCommunityProfile.objects.get(user=self.user_b)
        profile_b.opt_in = True
        profile_b.save()

        # It should work now
        res2 = self.client.get(reverse('community_start_thread', args=[self.user_b.id]))
        thread = Thread.objects.first()
        self.assertRedirects(res2, reverse('community_thread', args=[thread.id]))

    def test_start_thread_if_blocked(self):
        CaregiverCommunityProfile.objects.create(user=self.user_a, opt_in=True, city='City1')
        CaregiverCommunityProfile.objects.create(user=self.user_b, opt_in=True, city='City1')

        # A blocks B
        BlockedUser.objects.create(blocker=self.user_a, blocked=self.user_b)

        self.client.login(username='A', password='pw')
        # Try to start thread
        res = self.client.get(reverse('community_start_thread', args=[self.user_b.id]))
        self.assertRedirects(res, reverse('community_home'))

    def test_thread_access_for_participants_only(self):
        thread = Thread.objects.create()
        thread.participants.add(self.user_a, self.user_b)

        # Login as non participant
        self.client.login(username='N', password='pw')
        res = self.client.get(reverse('community_thread', args=[thread.id]))
        self.assertEqual(res.status_code, 404)

        # Login as participant
        self.client.login(username='A', password='pw')
        res = self.client.get(reverse('community_thread', args=[thread.id]))
        self.assertEqual(res.status_code, 200)

    def test_post_message_and_block_behavior(self):
        thread = Thread.objects.create()
        thread.participants.add(self.user_a, self.user_b)

        self.client.login(username='A', password='pw')
        res = self.client.post(reverse('community_thread', args=[thread.id]), {'body': 'Hello B'})
        self.assertRedirects(res, reverse('community_thread', args=[thread.id]))
        self.assertEqual(Message.objects.count(), 1)
        self.assertEqual(Message.objects.first().body, 'Hello B')

        # Now B blocks A
        BlockedUser.objects.create(blocker=self.user_b, blocked=self.user_a)

        # Try to post again from A
        res2 = self.client.post(reverse('community_thread', args=[thread.id]), {'body': 'You there?'})
        self.assertEqual(Message.objects.count(), 1)  # Message not saved!
