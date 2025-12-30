from django.urls import path
from .views import SymptomLogCreateView

app_name = 'symptoms'

urlpatterns = [
    # Changed from 'log/' to 'daily-log/' to match requirements
    path('daily-log/', SymptomLogCreateView.as_view(), name='log_symptoms'),
]