from django import forms
from django.forms import inlineformset_factory
from .models import ChildProfile, WeeklyWellbeingAnswer, WeeklyWellbeingEntry

class ChildProfileForm(forms.ModelForm):
    class Meta:
        model = ChildProfile
        fields = ['name', 'profile_picture', 'date_of_birth', 'sex', 'jaundice', 'family_asd', 'notes']
        widgets = {
            'profile_picture': forms.FileInput(attrs={'class': 'form-control'}),
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'sex': forms.Select(attrs={'class': 'form-select'}),
            'jaundice': forms.Select(attrs={'class': 'form-select'}),
            'family_asd': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }
        help_texts = {
            'sex': 'Sex assigned at birth (required for analysis)',
            'jaundice': 'Was the child born with jaundice? (yellowing of skin/eyes)',
            'family_asd': 'Is there a family history of Autism Spectrum Disorder?',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set "Select..." placeholder for dropdowns
        for field in ['sex', 'jaundice', 'family_asd']:
            self.fields[field].empty_label = "Select..."
        # Make demographic fields mandatory for onboarding
        for field in ['date_of_birth', 'sex', 'jaundice', 'family_asd']:
            self.fields[field].required = True

    def clean_date_of_birth(self):
        import datetime
        dob = self.cleaned_data.get('date_of_birth')
        if dob:
            today = datetime.date.today()
            # Calculate clinical bounds (1.5 years and 11 years ago)
            max_dob = today - datetime.timedelta(days=548) # 18 months
            min_dob = today - datetime.timedelta(days=4018) # 11 years
            
            if dob > today:
                raise forms.ValidationError("Date of birth cannot be in the future.")
            if dob > max_dob:
                raise forms.ValidationError("AutiBloom is designed for children aged 1.5 to 11 years. Your child must be at least 18 months old.")
            if dob < min_dob:
                raise forms.ValidationError("AutiBloom is designed for children aged 1.5 to 11 years. Your child must be under 11 years old.")
        return dob

class WeeklyWellbeingAnswerForm(forms.ModelForm):
    # Hidden field to track explicit user interaction
    touched = forms.CharField(
        required=False, 
        widget=forms.HiddenInput()
    )

    # Using string keys for compatibility with ChoiceField, coerced to int in clean_slider_score
    slider_score = forms.IntegerField(
        required=False,
        min_value=0, max_value=4,
        widget=forms.HiddenInput(),
        label="Score"
    )

    class Meta:
        model = WeeklyWellbeingAnswer
        fields = ['slider_score', 'comment']
        widgets = {
            'comment': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Optional notes for this question'}),
        }


# Factory for creating formsets of answers attached to an entry
WeeklyAnswerFormSet = inlineformset_factory(
    WeeklyWellbeingEntry,
    WeeklyWellbeingAnswer,
    form=WeeklyWellbeingAnswerForm,
    fields=['slider_score', 'comment'], # touched is not a model field, so not in 'fields' here? Wait.
    # If 'touched' is not in 'fields' list of inlineformset_factory AND it is not a model field, 
    # django might exclude it from the form unless we are careful.
    # However, since we defined it in the form class, we should ensure it's processed.
    # inlineformset_factory uses modelform_factory.
    # If we define a custom form, fields in Meta must usually include model fields. 
    # Non-model fields in the Form class are usually fine.
    # But let's verify if `fields` argument restricts it? 
    # "fields" argument to inlineformset_factory restricts which MODEL fields are used.
    # It does not strip extra form fields defined in the form class.
    extra=0,
    can_delete=False
)
