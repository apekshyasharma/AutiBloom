from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.http import HttpResponseForbidden

from .forms import UserRegistrationForm, LoginForm, SymptomTrackingForm
from .models import SymptomTracking, Profile


def root_redirect(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return redirect("login")


@require_http_methods(["GET", "POST"])
def register(request):
    if request.method == "POST":
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Account created. Please log in.")
            return redirect("login")
    else:
        form = UserRegistrationForm()
    return render(request, "accounts/register.html", {"form": form})


@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            user = authenticate(
                username=form.cleaned_data["username"],
                password=form.cleaned_data["password"],
            )
            login(request, user)
            return redirect("dashboard")
    else:
        form = LoginForm()

    return render(request, "accounts/login.html", {"form": form})


@login_required
def dashboard(request):
    """Caregiver dashboard with role-based access control"""
    user_role = get_user_role(request.user)
    
    # Only caregivers can access the dashboard
    if user_role != "caregiver":
        return HttpResponseForbidden("You do not have permission to access this page.")
    
    # Get user's symptom tracking records, ordered by newest first
    symptoms = SymptomTracking.objects.filter(user=request.user).order_by("-created_at")
    
    # Get latest symptom entry
    latest_symptom = symptoms.first()
    
    # Calculate support status label based on latest symptom
    support_status = None
    support_explanation = None
    
    if latest_symptom:
        support_status, support_explanation = get_support_status(latest_symptom)
    
    context = {
        "symptoms": symptoms,
        "latest_symptom": latest_symptom,
        "support_status": support_status,
        "support_explanation": support_explanation,
    }
    
    return render(request, "dashboard.html", context)


def get_support_status(symptom):
    """
    Map symptom severity to friendly support labels.
    
    Returns: (label, explanation)
    """
    severity = symptom.severity
    
    if severity <= 3:
        return (
            "Doing Well This Week",
            "Your child is managing well. Keep up the great support!"
        )
    elif severity <= 6:
        return (
            "Needs a Little Extra Support",
            "Consider implementing additional strategies this week."
        )
    else:
        return (
            "Support Recommended",
            "We recommend reaching out to your healthcare team for guidance."
        )


@login_required
@require_http_methods(["POST", "GET"])
def logout_view(request):
    logout(request)
    return redirect("login")


def get_user_role(user):
    """Helper to get user's role"""
    try:
        return user.profile.role
    except Profile.DoesNotExist:
        return None


def is_caregiver(user):
    return get_user_role(user) == "caregiver"


def is_doctor(user):
    return get_user_role(user) == "doctor"


def is_admin(user):
    return get_user_role(user) == "admin"


@login_required
def symptom_tracking_list(request):
    """List symptoms - role-aware access"""
    user_role = get_user_role(request.user)

    if user_role == "caregiver":
        # Caregivers see only their own records
        symptoms = SymptomTracking.objects.filter(user=request.user)
    elif user_role == "doctor":
        # Doctors see all records (read-only)
        symptoms = SymptomTracking.objects.all()
    elif user_role == "admin":
        # Admins see all records
        symptoms = SymptomTracking.objects.all()
    else:
        return HttpResponseForbidden("You do not have permission to view this page.")

    return render(request, "symptom_tracking_list.html", {"symptoms": symptoms})


@login_required
def symptom_tracking_create(request):
    """Create symptom tracking - caregiver and admin only"""
    user_role = get_user_role(request.user)

    if user_role not in ["caregiver", "admin"]:
        return HttpResponseForbidden("Only caregivers and admins can create symptom records.")

    if request.method == "POST":
        form = SymptomTrackingForm(request.POST)
        if form.is_valid():
            symptom = form.save(commit=False)
            symptom.user = request.user  # Bind to current user
            symptom.save()
            messages.success(request, "Symptom tracked successfully.")
            return redirect("dashboard")
    else:
        form = SymptomTrackingForm()

    return render(request, "symptom_tracking_form.html", {"form": form})


@login_required
def symptom_tracking_update(request, pk):
    """Update symptom tracking - caregiver and admin only"""
    user_role = get_user_role(request.user)

    if user_role not in ["caregiver", "admin"]:
        return HttpResponseForbidden("Only caregivers and admins can update symptom records.")

    # Always filter by user to enforce ownership
    symptom = get_object_or_404(SymptomTracking, pk=pk, user=request.user)

    if request.method == "POST":
        form = SymptomTrackingForm(request.POST, instance=symptom)
        if form.is_valid():
            form.save()
            messages.success(request, "Symptom updated successfully.")
            return redirect("dashboard")
    else:
        form = SymptomTrackingForm(instance=symptom)

    return render(request, "symptom_tracking_form.html", {"form": form, "symptom": symptom})


@login_required
def symptom_tracking_delete(request, pk):
    """Delete symptom tracking - caregiver and admin only"""
    user_role = get_user_role(request.user)

    if user_role not in ["caregiver", "admin"]:
        return HttpResponseForbidden("Only caregivers and admins can delete symptom records.")

    # Always filter by user to enforce ownership
    symptom = get_object_or_404(SymptomTracking, pk=pk, user=request.user)

    if request.method == "POST":
        symptom.delete()
        messages.success(request, "Symptom deleted successfully.")
        return redirect("dashboard")

    return render(request, "symptom_tracking_confirm_delete.html", {"symptom": symptom})
