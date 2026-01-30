from django.urls import path
from . import views

urlpatterns = [
    # Caregiver routes
    path('', views.caregiver_appointment_list, name='caregiver_appointment_list'),
    path('request/', views.caregiver_request_appointment, name='caregiver_request_appointment'),
    path('<int:appointment_id>/', views.caregiver_appointment_detail, name='caregiver_appointment_detail'),

    # Clinician routes
    path('clinician/', views.clinician_appointment_list, name='clinician_appointment_list'),
    path('clinician/<int:appointment_id>/', views.clinician_appointment_detail, name='clinician_appointment_detail'),
    path('clinician/<int:appointment_id>/review/', views.clinician_write_review, name='clinician_write_review'),
    path('clinician/<int:appointment_id>/report_json/', views.clinician_appointment_report_json, name='clinician_appointment_report_json'),
    path('clinician/<int:appointment_id>/confirm/', views.clinician_confirm_appointment, name='clinician_confirm_appointment'),

    # Dedicated message thread page (both roles)
    path('<int:appointment_id>/messages/', views.appointment_messages_page, name='appointment_messages_page'),

    # Secure PDF download (role + state gated, audited)
    path(
        '<int:appointment_id>/reports/<int:report_id>/download/',
        views.appointment_report_download,
        name='appointment_report_download',
    ),

    # Thread Message Router
    path('<int:appointment_id>/message/', views.add_appointment_message, name='add_appointment_message'),
]
