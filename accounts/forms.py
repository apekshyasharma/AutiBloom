"""
Forms for AutiBloom authentication.
Includes caregiver-only registration with automatic role assignment.
"""

from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import get_user_model
from django.db import models

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


class UserRegistrationForm(CaregiverRegistrationForm):
    """Alias for caregiver registration."""
    pass


class LoginForm(forms.Form):
    """Login form supporting username/email and password."""
    identifier = forms.CharField(
        label="Username or Email",
        max_length=254,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Username or email address'
        })
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your password'
        })
    )

    def clean(self):
        identifier = self.cleaned_data.get("identifier")
        password = self.cleaned_data.get("password")
        
        if identifier and password:
            self.user_cache = User.objects.filter(
                models.Q(username=identifier) | models.Q(email=identifier)
            ).first()
            if self.user_cache is None or not self.user_cache.check_password(password):
                raise forms.ValidationError("Invalid credentials.")
        
        return self.cleaned_data
