from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from .models import SymptomTracking

class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")


class LoginForm(forms.Form):
    username = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput)

    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get("username")
        password = cleaned_data.get("password")

        if username and password:
            user = authenticate(username=username, password=password)
            if user is None:
                raise forms.ValidationError("Invalid username or password.")
        return cleaned_data


class SymptomTrackingForm(forms.ModelForm):
    """Form for symptom tracking - excludes user field"""
    
    class Meta:
        model = SymptomTracking
        fields = ["description", "severity"]
        widgets = {
            "description": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Describe your symptoms..."
            }),
            "severity": forms.Select(attrs={
                "class": "form-control"
            }),
        }
