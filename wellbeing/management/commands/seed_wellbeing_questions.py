from django.core.management.base import BaseCommand
from wellbeing.models import WellbeingQuestion

class Command(BaseCommand):
    help = 'Seeds the 10 canonical Wellbeing Questions from the Data Dictionary'

    def handle(self, *args, **options):
        questions = [
            {
                "code": "A1",
                "domain": "communication",
                "text": "How often did your child look at you when you called their name this week?",
                "order": 1
            },
            {
                "code": "A2",
                "domain": "communication",
                "text": "How easy was it for your child to have a back-and-forth conversation this week?",
                "order": 2
            },
            {
                "code": "A3",
                "domain": "emotional_responses",
                "text": "How often did your child show emotional expressions appropriate to situations this week?",
                "order": 3
            },
            {
                "code": "A4",
                "domain": "routines",
                "text": "How comfortable was your child with changes to daily routines this week?",
                "order": 4
            },
            {
                "code": "A5",
                "domain": "routines",
                "text": "How often did your child engage in repetitive play or movements this week?",
                "order": 5
            },
            {
                "code": "A6",
                "domain": "sensory_behaviors",
                "text": "How did your child respond to loud sounds or bright lights this week?",
                "order": 6
            },
            {
                "code": "A7",
                "domain": "communication",
                "text": "How often did your child point at things to show interest this week?",
                "order": 7
            },
            {
                "code": "A8",
                "domain": "emotional_responses",
                "text": "How easily could you tell what your child was feeling this week?",
                "order": 8
            },
            {
                "code": "A9",
                "domain": "sensory_behaviors",
                "text": "How comfortable was your child with certain textures or physical sensations this week?",
                "order": 9
            },
            {
                "code": "A10",
                "domain": "routines",
                "text": "How easily did your child transition between activities this week?",
                "order": 10
            }
        ]

        self.stdout.write(f"Seeding {len(questions)} questions...")

        created_count = 0
        updated_count = 0

        for q_data in questions:
            obj, created = WellbeingQuestion.objects.update_or_create(
                code=q_data['code'],
                defaults={
                    'domain': q_data['domain'],
                    'text': q_data['text'],
                    'order': q_data['order'],
                    'is_active': True 
                }
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(self.style.SUCCESS(f"Successfully seeded. Created: {created_count}, Updated: {updated_count}"))
