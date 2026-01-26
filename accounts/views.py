from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.shortcuts import redirect, render, get_object_or_404
from django.views.decorators.http import require_POST
from .forms import CaregiverSignUpForm, ProfileForm, SettingsForm
from .models import User
from .permissions import role_required, clinician_verified_required
from django.contrib import messages
import logging
from django.contrib.auth import views as auth_views

logger = logging.getLogger(__name__)

class CustomLoginView(auth_views.LoginView):
    template_name = "accounts/login.html"

    def get_context_data(self, **kwargs):
        # True only when a real Google client_id has been configured via env.
        from django.conf import settings
        ctx = super().get_context_data(**kwargs)
        ctx["google_oauth_enabled"] = bool(getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", ""))
        return ctx

    def get_success_url(self):
        url = super().get_success_url()
        return f"{url}?event=login_success"

class CustomLogoutView(auth_views.LogoutView):
    def get_success_url(self):
        url = super().get_success_url()
        if url:
            return f"{url}?event=logout_success"
        from django.urls import reverse
        return f"{reverse('login')}?event=logout_success"


def caregiver_signup(request):
    if request.method == "POST":
        form = CaregiverSignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            logger.info(f"New Caregiver signed up: {user.username}")
            from django.urls import reverse
            return redirect(f"{reverse('login')}?event=signup_success")
    else:
        form = CaregiverSignUpForm()
    return render(request, "accounts/caregiver_signup.html", {"form": form})


@login_required
def dashboard(request):
    user: User = request.user

    # Preserve query string (e.g., ?event=login_success)
    query_string = request.GET.urlencode()
    suffix = f"?{query_string}" if query_string else ""

    if user.is_admin():
        return render(request, "accounts/dashboard_admin.html")
    if user.is_clinician():
        # block unverified clinicians
        if not user.clinician_verified:
            return render(request, "accounts/clinician_pending.html")
        return render(request, "accounts/dashboard_clinician.html")

    # Caregiver onboarding redirect
    from wellbeing.models import CaregiverChild
    from django.urls import reverse
    if CaregiverChild.objects.filter(caregiver=user).exists():
        return redirect(f"{reverse('wellbeing_dashboard')}{suffix}")
    else:
        return redirect(f"{reverse('wellbeing_child_create')}{suffix}")


@login_required
@role_required(["ADMIN"])
def admin_create_clinician(request):
    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")  # In prod, auto-generate this or send invite
        
        if User.objects.filter(username=username).exists():
             messages.error(request, "Username already exists")
             return render(request, "accounts/admin_create_clinician.html")

        # Create clinician
        user = User.objects.create_user(username=username, email=email, password=password)
        user.role = User.Role.CLINICIAN
        user.clinician_verified = True # Admin created, so auto-verified
        user.save()
        
        logger.warning(f"Admin {request.user.username} created Clinician {username}")
        messages.success(request, f"Clinician {username} created successfully.")
        return redirect("dashboard")

    return render(request, "accounts/admin_create_clinician.html")


@login_required
@role_required(["ADMIN"])
def admin_clinician_list(request):
    clinicians = User.objects.filter(role=User.Role.CLINICIAN)
    return render(request, "accounts/admin_clinician_list.html", {"clinicians": clinicians})


@login_required
@role_required(["ADMIN"])
@require_POST
def admin_verify_clinician(request, user_id):
    user = get_object_or_404(User, pk=user_id, role=User.Role.CLINICIAN)
    user.clinician_verified = True
    user.save()
    logger.warning(f"Admin {request.user.username} verified Clinician {user.username}")
    messages.success(request, f"Clinician {user.username} verified.")
    return redirect("clinician_list")


@login_required
@role_required(["ADMIN"])
@require_POST
def admin_unverify_clinician(request, user_id):
    user = get_object_or_404(User, pk=user_id, role=User.Role.CLINICIAN)
    user.clinician_verified = False
    user.save()
    logger.warning(f"Admin {request.user.username} unverified Clinician {user.username}")
    messages.success(request, f"Clinician {user.username} unverified.")
    return redirect("clinician_list")


@login_required
@role_required(["ADMIN"])
@require_POST
def admin_activate_clinician(request, user_id):
    user = get_object_or_404(User, pk=user_id, role=User.Role.CLINICIAN)
    user.is_active = True
    user.save()
    logger.warning(f"Admin {request.user.username} activated Clinician {user.username}")
    messages.success(request, f"Clinician {user.username} activated.")
    return redirect("clinician_list")


@login_required
@role_required(["ADMIN"])
@require_POST
def admin_deactivate_clinician(request, user_id):
    user = get_object_or_404(User, pk=user_id, role=User.Role.CLINICIAN)
    user.is_active = False
    user.save()
    logger.warning(f"Admin {request.user.username} deactivated Clinician {user.username}")
    messages.success(request, f"Clinician {user.username} deactivated.")
    return redirect("clinician_list")


# ─────────────────────────────────────────────────────────────────
#  Profile · Settings · Password
# ─────────────────────────────────────────────────────────────────

def _base_template_for(user) -> str:
    """Caregivers get the sidebar shell; clinicians/admins get the plain top-nav."""
    return "layouts/caregiver_base.html" if user.is_caregiver() else "accounts/base.html"


@login_required
def profile_view(request):
    """Edit your own profile. Works for caregivers, clinicians, and admins."""
    user = request.user

    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=user)
        if request.POST.get('remove_avatar') and user.avatar:
            user.avatar.delete(save=False)
            user.avatar = None
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated.")
            return redirect("profile")
    else:
        form = ProfileForm(instance=user)

    return render(request, "accounts/profile.html", {
        "form": form,
        "profile_user": user,
        "base_template": _base_template_for(user),
    })


@login_required
def settings_view(request):
    """Notification preferences + password change."""
    user = request.user
    password_form = PasswordChangeForm(user)
    form = SettingsForm(instance=user)

    if request.method == "POST":
        action = request.POST.get("action", "preferences")

        if action == "preferences":
            form = SettingsForm(request.POST, instance=user)
            if form.is_valid():
                form.save()
                messages.success(request, "Settings saved.")
                return redirect("settings")

        elif action == "password":
            password_form = PasswordChangeForm(user, request.POST)
            if password_form.is_valid():
                new_user = password_form.save()
                update_session_auth_hash(request, new_user)
                messages.success(request, "Password updated.")
                return redirect("settings")

    return render(request, "accounts/settings.html", {
        "form": form,
        "password_form": password_form,
        "base_template": _base_template_for(user),
    })
