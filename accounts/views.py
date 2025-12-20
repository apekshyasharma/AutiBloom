from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.db import IntegrityError

from .forms import UserRegistrationForm, LoginForm

User = get_user_model()

def root_redirect(request: HttpRequest) -> HttpResponse:
    """Redirect authenticated users to dashboard, others to login."""
    if request.user.is_authenticated:
        return redirect(reverse("dashboard"))
    return redirect(reverse("login"))

@require_http_methods(["GET", "POST"])
def register(request: HttpRequest) -> HttpResponse:
    """Handle user registration with proper error handling."""
    if request.method == "GET":
        form = UserRegistrationForm()
        return render(request, "accounts/register.html", {"form": form})
    
    form = UserRegistrationForm(request.POST)
    
    if form.is_valid():
        try:
            user = form.save()
            messages.success(
                request, 
                f"Account created successfully! Please log in with your credentials.",
                extra_tags="success"
            )
            return redirect(reverse("login"))
        except IntegrityError as e:
            # Handle database integrity errors (e.g., duplicate username/email)
            form.add_error(None, "An account with this username or email already exists.")
            messages.error(
                request,
                "Registration failed. Please check your input and try again.",
                extra_tags="danger"
            )
            return render(request, "accounts/register.html", {"form": form}, status=400)
        except Exception as e:
            # Handle unexpected errors
            form.add_error(None, "An unexpected error occurred. Please try again later.")
            messages.error(
                request,
                "Registration failed due to a server error. Please try again.",
                extra_tags="danger"
            )
            return render(request, "accounts/register.html", {"form": form}, status=500)
    else:
        # Form validation failed
        for field, errors in form.errors.items():
            for error in errors:
                if field == '__all__':
                    messages.error(request, str(error), extra_tags="danger")
                else:
                    messages.error(request, f"{field.title()}: {error}", extra_tags="danger")
        
        return render(request, "accounts/register.html", {"form": form}, status=400)

@require_http_methods(["GET", "POST"])
def login_view(request: HttpRequest) -> HttpResponse:
    """Handle user login with proper error handling and security."""
    if request.user.is_authenticated:
        return redirect(reverse("dashboard"))
    
    if request.method == "GET":
        form = LoginForm()
        return render(request, "accounts/login.html", {"form": form})
    
    form = LoginForm(request.POST)
    
    if not form.is_valid():
        # Display form validation errors
        for field, errors in form.errors.items():
            for error in errors:
                if field == '__all__':
                    messages.error(request, str(error), extra_tags="danger")
                else:
                    messages.error(request, f"{field.title()}: {error}", extra_tags="danger")
        
        return render(request, "accounts/login.html", {"form": form}, status=400)

    try:
        identifier = form.cleaned_data.get("identifier", "").strip()
        password = form.cleaned_data.get("password", "")
        
        # Validate input
        if not identifier or not password:
            form.add_error(None, "Username/email and password are required.")
            messages.error(
                request,
                "Please provide both username/email and password.",
                extra_tags="danger"
            )
            return render(request, "accounts/login.html", {"form": form}, status=400)
        
        # Look up user by username or email
        user = User.objects.filter(username=identifier).first() or \
                User.objects.filter(email=identifier).first()
        
        # Validate user and password
        if user and user.check_password(password):
            # Check if user account is active
            if not user.is_active:
                form.add_error(None, "This account has been deactivated.")
                messages.error(
                    request,
                    "Your account is inactive. Please contact support.",
                    extra_tags="warning"
                )
                return render(request, "accounts/login.html", {"form": form}, status=403)
            
            # Successful login
            login(request, user)
            messages.success(
                request,
                f"Welcome back, {user.first_name or user.username}!",
                extra_tags="success"
            )
            return redirect(reverse("dashboard"))
        else:
            # Invalid credentials
            form.add_error(None, "Invalid username/email or password.")
            messages.error(
                request,
                "The username/email or password you entered is incorrect.",
                extra_tags="danger"
            )
            return render(request, "accounts/login.html", {"form": form}, status=401)
    
    except User.DoesNotExist:
        form.add_error(None, "Invalid username/email or password.")
        messages.error(
            request,
            "The username/email or password you entered is incorrect.",
            extra_tags="danger"
        )
        return render(request, "accounts/login.html", {"form": form}, status=401)
    
    except Exception as e:
        form.add_error(None, "An unexpected error occurred. Please try again later.")
        messages.error(
            request,
            "Login failed due to a server error. Please try again.",
            extra_tags="danger"
        )
        return render(request, "accounts/login.html", {"form": form}, status=500)

@login_required(login_url="login")
def dashboard(request: HttpRequest) -> HttpResponse:
    """Display user dashboard."""
    try:
        return render(request, "dashboard.html", {
            "user": request.user,
            "role": request.user.role
        })
    except Exception as e:
        messages.error(
            request,
            "Error loading dashboard. Please try again.",
            extra_tags="danger"
        )
        return redirect(reverse("login"))

@require_http_methods(["POST"])
def logout_view(request: HttpRequest) -> HttpResponse:
    """Handle user logout."""
    try:
        logout(request)
        messages.success(
            request,
            "You have been logged out successfully.",
            extra_tags="success"
        )
        return redirect(reverse("login"))
    except Exception as e:
        messages.error(
            request,
            "Error logging out. Please try again.",
            extra_tags="danger"
        )
        return redirect(reverse("login"))
