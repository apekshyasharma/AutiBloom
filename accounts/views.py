from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model

from .forms import UserRegistrationForm, LoginForm

User = get_user_model()

def root_redirect(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect(reverse("dashboard"))
    return redirect(reverse("login"))

@require_http_methods(["GET", "POST"])
def register(request: HttpRequest) -> HttpResponse:
    if request.method == "GET":
        form = UserRegistrationForm()
        return render(request, "accounts/register.html", {"form": form})
    form = UserRegistrationForm(request.POST)
    if form.is_valid():
        form.save()
        return redirect(reverse("login"))
    return render(request, "accounts/register.html", {"form": form}, status=400)

@require_http_methods(["GET", "POST"])
def login_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect(reverse("dashboard"))
    if request.method == "GET":
        form = LoginForm()
        return render(request, "accounts/login.html", {"form": form})
    
    form = LoginForm(request.POST)
    if not form.is_valid():
        return render(request, "accounts/login.html", {"form": form}, status=400)

    identifier = form.cleaned_data.get("identifier")
    password = form.cleaned_data.get("password")
    
    # Look up user by username or email
    user = User.objects.filter(username=identifier).first() or User.objects.filter(email=identifier).first()
    
    if user and user.check_password(password):
        login(request, user)
        return redirect(reverse("dashboard"))
    
    form.add_error(None, "Invalid credentials.")
    return render(request, "accounts/login.html", {"form": form}, status=401)

@login_required(login_url="login")
def dashboard(request: HttpRequest) -> HttpResponse:
    return render(request, "dashboard.html")

@require_http_methods(["POST"])
def logout_view(request: HttpRequest) -> HttpResponse:
    logout(request)
    return redirect(reverse("login"))
