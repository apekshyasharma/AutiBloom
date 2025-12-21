from django.db import models
from django.contrib.auth.models import User

class Profile(models.Model):
    ROLE_CHOICES = (
        ("caregiver", "Caregiver"),
        ("doctor", "Doctor"),
        ("admin", "Admin"),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="caregiver")

    def __str__(self):
        return f"{self.user.username} - {self.role}"


class SymptomTracking(models.Model):
    """User-owned symptom tracking data"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="symptom_tracks")
    description = models.TextField()
    severity = models.IntegerField(choices=[(i, i) for i in range(1, 11)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.created_at.date()}"
