from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from .models import User


MAX_AVATAR_BYTES = 4 * 1024 * 1024  # 4 MB
ALLOWED_IMAGE_EXTS = ('jpg', 'jpeg', 'png', 'webp', 'gif')


class CaregiverSignUpForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("username", "email")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.CAREGIVER  # force caregiver
        if commit:
            user.save()
        return user


class ProfileForm(forms.ModelForm):
    """
    Unified profile form. The same form class is used for all roles;
    clinician-specific fields stay in the Meta.fields list and the
    template hides them for non-clinicians.
    """
    first_name = forms.CharField(max_length=150, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First name'}))
    last_name = forms.CharField(max_length=150, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last name'}))
    email = forms.EmailField(required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'you@example.com'}))

    class Meta:
        model = User
        fields = (
            'avatar',
            'first_name', 'last_name', 'email',
            'phone_number', 'date_of_birth', 'address', 'bio',
            # clinician-only
            'specialization', 'license_number', 'years_of_experience', 'qualifications',
        )
        widgets = {
            'avatar': forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+1 555 123 4567'}),
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Street, City, Country'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'A short introduction…'}),
            'specialization': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Developmental Paediatrics'}),
            'license_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Professional licence number'}),
            'years_of_experience': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 80}),
            'qualifications': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Degrees, certifications, memberships…'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Drop clinician-only fields for non-clinicians so their POST can't smuggle values in.
        if self.instance and not self.instance.is_clinician():
            for f in ('specialization', 'license_number', 'years_of_experience', 'qualifications'):
                self.fields.pop(f, None)

    def clean_avatar(self):
        f = self.cleaned_data.get('avatar')
        # `f` is only a new upload when the user actually chose a file; the
        # ClearableFileInput otherwise returns the existing FieldFile.
        if f and hasattr(f, 'size'):
            if f.size > MAX_AVATAR_BYTES:
                raise ValidationError(f"Avatar too large. Max {MAX_AVATAR_BYTES // (1024 * 1024)} MB.")
            name = getattr(f, 'name', '') or ''
            ext = name.rsplit('.', 1)[-1].lower() if '.' in name else ''
            if ext and ext not in ALLOWED_IMAGE_EXTS:
                raise ValidationError(f"Unsupported image type '.{ext}'. Use: {', '.join(ALLOWED_IMAGE_EXTS)}.")
        return f

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if not email:
            raise ValidationError("Email is required.")
        qs = User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("That email is already used by another account.")
        return email


class SettingsForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('notify_email', 'notify_appointments', 'notify_community_digest', 'preferred_timezone')
        widgets = {
            'preferred_timezone': forms.Select(attrs={'class': 'form-select'}),
        }

    TIMEZONE_CHOICES = [
        ('UTC',               'UTC (Coordinated Universal Time)'),
        ('Asia/Kathmandu',    'Asia/Kathmandu (NPT +05:45)'),
        ('Asia/Kolkata',      'Asia/Kolkata (IST +05:30)'),
        ('Asia/Dubai',        'Asia/Dubai (GST +04:00)'),
        ('Asia/Singapore',    'Asia/Singapore (SGT +08:00)'),
        ('Europe/London',     'Europe/London'),
        ('Europe/Berlin',     'Europe/Berlin'),
        ('America/New_York',  'America/New_York'),
        ('America/Chicago',   'America/Chicago'),
        ('America/Los_Angeles', 'America/Los_Angeles'),
        ('Australia/Sydney',  'Australia/Sydney'),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['preferred_timezone'] = forms.ChoiceField(
            choices=self.TIMEZONE_CHOICES,
            widget=forms.Select(attrs={'class': 'form-select'}),
            initial=self.instance.preferred_timezone or 'UTC',
        )
