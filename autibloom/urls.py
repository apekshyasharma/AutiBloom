"""
URL configuration for autibloom project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),

    # Social auth (Google). Mounted under /social/ so it doesn't collide
    # with the existing /accounts/login/ and /accounts/logout/ overrides
    # that inject the ?event= flash parameters.
    path("social/", include("allauth.urls")),

    path("", include("accounts.urls")),
    path("wellbeing/", include("wellbeing.urls")), # Feature 2 Routes
    path("chat/", include("chatbot.urls")),
    path("community/", include("community.urls")),
    path("games/", include("games.urls")),
    path('appointments/', include('appointments.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)