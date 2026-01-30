from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Appointment, ClinicianReview, SupportPlan
from accounts.models import User
from wellbeing.models import WeeklyWellbeingEntry, ChildProfile


MAX_REPORT_BYTES = 10 * 1024 * 1024   # 10 MB
PDF_MAGIC = b'%PDF-'


def validate_pdf_upload(uploaded):
    """Shared validation for each PDF file in a multi-upload booking."""
    if uploaded.size > MAX_REPORT_BYTES:
        raise ValidationError(
            f"'{uploaded.name}' is too large. Maximum size is {MAX_REPORT_BYTES // (1024 * 1024)} MB."
        )
    if not uploaded.name.lower().endswith('.pdf'):
        raise ValidationError(f"'{uploaded.name}' is not a PDF.")
    head = uploaded.read(5)
    uploaded.seek(0)
    if not head.startswith(PDF_MAGIC):
        raise ValidationError(f"'{uploaded.name}' does not appear to be a valid PDF.")


class AppointmentRequestForm(forms.ModelForm):
    # The raw file input is handled in the view via request.FILES.getlist()
    # because Django's FileField validates only a single upload by default.

    class Meta:
        model = Appointment
        fields = ['child', 'reason_type', 'reason_text', 'preferred_date', 'preferred_time_window', 'clinician', 'entry']
        widgets = {
            'child': forms.Select(attrs={'class': 'form-select form-select-lg rounded-3'}),
            'reason_type': forms.RadioSelect(),
            'reason_text': forms.Textarea(attrs={'class': 'form-control rounded-3', 'rows': 3, 'placeholder': "Tell us what you'd like to discuss..."}),
            'preferred_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control rounded-3'}),
            'preferred_time_window': forms.Select(attrs={'class': 'form-select rounded-3'}),
            'clinician': forms.Select(attrs={'class': 'form-select form-select-lg rounded-3'}),
            'entry': forms.Select(attrs={'class': 'form-select form-select-lg rounded-3'}),
        }

    def __init__(self, *args, **kwargs):
        self.caregiver = kwargs.pop('caregiver', None)
        super().__init__(*args, **kwargs)

        self.fields['reason_type'].choices = Appointment.REASON_CHOICES
        today = timezone.localdate()
        self.fields['preferred_date'].widget.attrs['min'] = today.isoformat()
        self.fields['preferred_time_window'].choices = Appointment.TIME_WINDOW_CHOICES

        # The weekly wellbeing entry is optional — it's our internal data,
        # not the clinician's uploaded report.
        self.fields['entry'].required = False

        if self.caregiver:
            self.fields['child'].queryset = ChildProfile.objects.filter(
                caregiver_relationships__caregiver=self.caregiver
            )
            self.fields['child'].empty_label = "Select your child"
            self.fields['entry'].queryset = WeeklyWellbeingEntry.objects.filter(
                caregiver=self.caregiver, status='SUBMITTED'
            ).order_by('-week_start')
            self.fields['entry'].empty_label = "Choose a submitted report (optional)"

        self.fields['clinician'].queryset = User.objects.filter(
            role='CLINICIAN', clinician_verified=True, is_active=True
        )
        self.fields['clinician'].empty_label = "Select a clinician"

    def clean_preferred_date(self):
        date = self.cleaned_data.get('preferred_date')
        if date:
            today = timezone.localdate()
            if date < today:
                raise ValidationError("You cannot book a date in the past. Please select today or a future date.")
            if date.weekday() in (5, 6):
                raise ValidationError("Appointments are only available on weekdays (Monday–Friday).")
        return date

    def clean(self):
        cleaned_data = super().clean()
        child = cleaned_data.get('child')
        entry = cleaned_data.get('entry')

        if entry and child:
            if entry.child != child:
                raise ValidationError("The attached wellbeing report must belong to the selected child.")
            if entry.status != 'SUBMITTED':
                raise ValidationError("Only finalized/submitted wellbeing reports can be attached.")

        return cleaned_data


class ClinicianReviewForm(forms.ModelForm):
    """
    Fields are optional at form level so the clinician can Confirm or Save
    Draft with a blank review. Completion is gated separately in the view
    (recommendations must exist to complete the case).
    """
    class Meta:
        model = ClinicianReview
        fields = ['clinician_notes']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['clinician_notes'].required = False


class SupportPlanForm(forms.ModelForm):
    class Meta:
        model = SupportPlan
        fields = ['title', 'recommendations', 'follow_up_required', 'follow_up_date']
        widgets = {
            'follow_up_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['title'].required = False
        self.fields['recommendations'].required = False
