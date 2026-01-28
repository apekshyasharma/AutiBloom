from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import datetime

class ChildProfile(models.Model):
    name = models.CharField(max_length=255)
    profile_picture = models.ImageField(upload_to='child_profiles/', null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    sex = models.CharField(
        max_length=1, 
        choices=[("m", "Male"), ("f", "Female")], 
        null=True, blank=True
    )
    jaundice = models.CharField(
        max_length=3, 
        choices=[("yes", "Yes"), ("no", "No")], 
        null=True, blank=True
    )
    family_asd = models.CharField(
        max_length=3, 
        choices=[("yes", "Yes"), ("no", "No")], 
        null=True, blank=True
    )

    def __str__(self):
        return self.name

class CaregiverChild(models.Model):
    caregiver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='caregiver_relationships')
    child = models.ForeignKey(ChildProfile, on_delete=models.CASCADE, related_name='caregiver_relationships')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['caregiver', 'child'], name='unique_caregiver_child')
        ]

    def __str__(self):
        return f"{self.caregiver} -> {self.child}"

class WellbeingQuestion(models.Model):
    DOMAIN_CHOICES = [
        ('communication', 'Communication'),
        ('routines', 'Routines'),
        ('emotional_responses', 'Emotional Responses'),
        ('sensory_behaviors', 'Sensory Behaviors'),
    ]

    code = models.CharField(
        max_length=10, 
        unique=True, 
        help_text="e.g. A1, A2... A10",
        validators=[RegexValidator(r"^A([1-9]|10)$", "Code must be A1..A10")]
    )
    domain = models.CharField(max_length=50, choices=DOMAIN_CHOICES)
    text = models.TextField()
    order = models.PositiveSmallIntegerField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.code}: {self.text[:50]}"

class WeeklyWellbeingEntry(models.Model):
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('SUBMITTED', 'Submitted'),
    ]

    caregiver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wellbeing_entries')
    child = models.ForeignKey(ChildProfile, on_delete=models.CASCADE, related_name='wellbeing_entries')
    week_start = models.DateField(help_text="Monday of the week")
    week_end = models.DateField(help_text="Sunday of the week")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    notes = models.TextField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    
    # Computed metrics
    communication_score = models.FloatField(null=True, blank=True)
    routines_score = models.FloatField(null=True, blank=True)
    emotional_score = models.FloatField(null=True, blank=True)
    sensory_score = models.FloatField(null=True, blank=True)
    overall_score = models.FloatField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['caregiver', 'child', 'week_start'], name='unique_weekly_entry')
        ]
        indexes = [
            models.Index(fields=['child', '-week_start']),
            models.Index(fields=['caregiver', '-week_start']),
        ]
        verbose_name_plural = "Weekly Wellbeing Entries"

    def __str__(self):
        return f"{self.child} - {self.week_start} ({self.status})"

    def clean(self):
        if self.week_start and self.week_end:
            if self.week_end != self.week_start + datetime.timedelta(days=6):
                raise ValidationError("week_end must be exactly 6 days after week_start (Monday-Sunday cycle).")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def recompute_metrics(self):
        """
        Average slider scores by domain and overall. Ignored if no answers present.
        Only considers answers with non-null slider_score.
        """
        answers = self.answers.filter(slider_score__isnull=False)
        if not answers.exists():
            self.communication_score = None
            self.routines_score = None
            self.emotional_score = None
            self.sensory_score = None
            self.overall_score = None
            return

        total_sum = 0
        total_count = 0
        domain_sums = {
            'communication': [],
            'routines': [],
            'emotional_responses': [],
            'sensory_behaviors': []
        }

        for ans in answers:
            score = ans.slider_score
            domain = ans.question.domain
            
            total_sum += score
            total_count += 1
            if domain in domain_sums:
                domain_sums[domain].append(score)

        def avg(values):
            return sum(values) / len(values) if values else None

        self.overall_score = total_sum / total_count if total_count > 0 else None
        self.communication_score = avg(domain_sums['communication'])
        self.routines_score = avg(domain_sums['routines'])
        self.emotional_score = avg(domain_sums['emotional_responses'])
        self.sensory_score = avg(domain_sums['sensory_behaviors'])
        
        # We generally don't save inside helper methods to allow bulk operations, 
        # but for single entry updates it's often convenient. 
        # Here we assume the caller will save().
        pass 

class WeeklyWellbeingAnswer(models.Model):
    entry = models.ForeignKey(WeeklyWellbeingEntry, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(WellbeingQuestion, on_delete=models.CASCADE)
    
    slider_score = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(4)],
        help_text="0-4 scale"
    )
    binary_flag = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="Derived: 1 if slider <= 1 (Risk), else 0"
    )
    comment = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['entry', 'question'], name='unique_entry_question')
        ]

    def __str__(self):
        return f"{self.entry} - {self.question.code}: {self.slider_score}"

    def compute_binary_from_slider(self):
        """
        Rule: binary = 1 if slider <= 1 else 0
        """
        if self.slider_score is not None:
            if self.slider_score <= 1:
                self.binary_flag = 1
            else:
                self.binary_flag = 0
        else:
            self.binary_flag = None

    def save(self, *args, **kwargs):
        self.compute_binary_from_slider()
        super().save(*args, **kwargs)
        # Recalculate parent metrics
        self.entry.recompute_metrics()
        self.entry.save(update_fields=[
            'communication_score', 
            'routines_score', 
            'emotional_score', 
            'sensory_score', 
            'overall_score', 
            'updated_at'
        ])


class PredictionResult(models.Model):
    caregiver = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='prediction_results'
    )
    child = models.ForeignKey(
        ChildProfile, on_delete=models.CASCADE, related_name='prediction_results'
    )
    entry = models.ForeignKey(
        WeeklyWellbeingEntry, on_delete=models.CASCADE, related_name='predictions'
    )
    prediction_label = models.CharField(max_length=255, default="Model not trained yet")
    prediction_score = models.FloatField(null=True, blank=True)
    model_version = models.CharField(max_length=50, default="stub-v1")
    explanation_json = models.JSONField(null=True, blank=True)
    narrative_text = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Prediction for {self.child} (entry {self.entry_id}) — {self.prediction_label}"
