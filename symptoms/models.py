from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone

class SymptomLog(models.Model):
    caregiver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='symptom_logs'
    )
    date = models.DateField(default=timezone.now)

    # Core Symptom Ratings (1-5 Scale)
    communication_rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Rating from 1 (Low) to 5 (High)"
    )
    social_interaction_rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Rating from 1 (Low) to 5 (High)"
    )
    repetitive_behavior_rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Rating from 1 (Low) to 5 (High)"
    )
    sensory_sensitivity_rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Rating from 1 (Low) to 5 (High)"
    )
    mood_rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Rating from 1 (Low) to 5 (High)"
    )

    # Detailed Behaviors
    behaviors_checklist = models.JSONField(
        default=dict,
        blank=True,
        help_text="JSON object storing checked specific behaviors"
    )
    
    notes = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']
        constraints = [
            models.UniqueConstraint(
                fields=['caregiver', 'date'],
                name='unique_daily_log_per_caregiver_date'
            )
        ]
