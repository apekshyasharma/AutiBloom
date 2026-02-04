from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('dashboard/', views.wellbeing_dashboard, name='wellbeing_dashboard'),

    # Child CRUD
    path('children/', views.child_list, name='wellbeing_child_list'),
    path('children/add/', views.child_create, name='wellbeing_child_create'),
    path('children/<int:child_id>/', views.child_detail, name='wellbeing_child_detail'),
    path('children/<int:child_id>/edit/', views.child_edit, name='wellbeing_child_edit'),

    # API
    path('api/dashboard/child/<int:child_id>/', views.dashboard_api, name='wellbeing_dashboard_api'),

    # Entry Workflow
    path('children/<int:child_id>/entry/start/', views.entry_start, name='wellbeing_entry_start'),
    path('entries/<int:entry_id>/edit/', views.entry_edit, name='wellbeing_entry_edit'),
    path('entries/<int:entry_id>/submit/', views.entry_submit, name='wellbeing_entry_submit'),
    path('entries/<int:entry_id>/report/', views.entry_report, name='wellbeing_entry_report'),
    path('entries/<int:entry_id>/export_pdf/', views.entry_export_pdf, name='wellbeing_entry_export_pdf'),

    # Reports
    path('reports/child/<int:child_id>/', views.child_report, name='wellbeing_child_report'),

    # Prediction
    path('predict/entry/<int:entry_id>/', views.predict_entry, name='wellbeing_predict_entry'),
    path('narrative/<int:prediction_id>/', views.generate_narrative, name='wellbeing_generate_narrative'),

    # Export
    # path('entries/<int:entry_id>/export_json/', views.entry_export_json, name='wellbeing_entry_export_json'),
]
