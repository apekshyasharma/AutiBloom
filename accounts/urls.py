from django.urls import path, include
from . import views


urlpatterns = [
    path("signup/", views.caregiver_signup, name="caregiver_signup"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("create-clinician/", views.admin_create_clinician, name="create_clinician"),
    path("clinicians/", views.admin_clinician_list, name="clinician_list"),
    path("clinicians/verify/<int:user_id>/", views.admin_verify_clinician, name="verify_clinician"),
    path("clinicians/unverify/<int:user_id>/", views.admin_unverify_clinician, name="unverify_clinician"),
    path("clinicians/activate/<int:user_id>/", views.admin_activate_clinician, name="activate_clinician"),
    path("clinicians/deactivate/<int:user_id>/", views.admin_deactivate_clinician, name="deactivate_clinician"),
    
    # Profile + settings (all roles)
    path("profile/", views.profile_view, name="profile"),
    path("settings/", views.settings_view, name="settings"),

    # Custom Auth overrides to inject ?event= params
    path("accounts/login/", views.CustomLoginView.as_view(), name="login"),
    path("accounts/logout/", views.CustomLogoutView.as_view(), name="logout"),

    # Built-in auth urls for password reset
    path("accounts/", include("django.contrib.auth.urls")), # e.g. /accounts/password_reset/

    path("", views.dashboard, name="home"),
]
