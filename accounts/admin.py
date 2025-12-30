from django.contrib import admin
from .models import Profile, SymptomTracking


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role")
    list_filter = ("role",)


@admin.register(SymptomTracking)
class SymptomTrackingAdmin(admin.ModelAdmin):
    list_display = ("user", "severity", "created_at", "updated_at")
    list_filter = ("severity", "created_at", "user__profile__role")
    search_fields = ("user__username", "description")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)
