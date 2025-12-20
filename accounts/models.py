"""
Custom User model for AutiBloom.
Extends Django AbstractUser to support role-based authentication
for caregivers and clinicians.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    ROLE_CHOICES = (
        ("caregiver", "Caregiver"),
        ("clinician", "Clinician"),
    )

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES
    )

    def __str__(self):
        return f"{self.username} ({self.role})"
