from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .forms import UserRegistrationForm, LoginForm


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
    return render(request, "dashboard.html")  # ✅ Fixed: changed from "accounts/dashboard.html"


@login_required
@require_http_methods(["POST", "GET"])
def logout_view(request):
    logout(request)
    return redirect("login")
