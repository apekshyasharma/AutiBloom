from django import forms
from .models import CaregiverCommunityProfile

class CommunityOptInForm(forms.ModelForm):
    class Meta:
        model = CaregiverCommunityProfile
        fields = ['opt_in', 'city', 'postal_code', 'bio']
        widgets = {
            'opt_in': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'city': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Target City'}),
            'postal_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 10001 (Optional)'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Tell other caregivers about yourself and what support you are seeking or offering.'}),
        }
