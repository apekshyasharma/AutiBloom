"""
Forms for AutiBloom authentication.
Includes caregiver-only registration with automatic role assignment.
"""

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model

User = get_user_model()


class CaregiverRegistrationForm(UserCreationForm):
    """
    Registration form for caregivers only.
    Clinicians are created by admin and cannot self-register.
    """

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = "caregiver"
        if commit:
            user.save()
        return user
