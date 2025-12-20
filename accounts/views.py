from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required  

from .forms import UserRegistrationForm, LoginForm

@require_http_methods(["GET", "POST"])
def register(request: HttpRequest) -> HttpResponse:
    if request.method == "GET":
        form = UserRegistrationForm()
        return JsonResponse({"form": {"fields": list(form.fields.keys())}})
    form = UserRegistrationForm(request.POST)
    if form.is_valid():
        form.save()  # passwords hashed via set_password in the form
        return redirect(reverse("login"))
    return JsonResponse({"errors": form.errors}, status=400)

@require_http_methods(["GET", "POST"])
def login_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect(reverse("dashboard"))
    if request.method == "GET":
        form = LoginForm()
        return JsonResponse({"form": {"fields": list(form.fields.keys())}})
    form = LoginForm(request.POST)
    if not form.is_valid():
        return JsonResponse({"errors": form.errors}, status=400)

    identifier = form.cleaned_data["identifier"]
    password = form.cleaned_data["password"]
    user = authenticate(request, username=identifier, password=password)
    if user is None:
        form.add_error(None, "Invalid credentials.")
        return JsonResponse({"errors": form.errors}, status=401)

    login(request, user)
    return redirect(reverse("dashboard"))

@login_required(login_url="login")
def dashboard(request: HttpRequest) -> HttpResponse:
    return HttpResponse("Dashboard")

@require_http_methods(["GET", "POST"])
def logout_view(request):
    logout(request)
    return redirect(reverse("login"))
