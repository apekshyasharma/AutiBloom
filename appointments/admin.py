from django.contrib import admin
from .models import (
    Appointment, ClinicianReview, SupportPlan, AppointmentMessage,
    MedicalReport, AppointmentAuditLog,
)


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'child', 'caregiver', 'clinician', 'status', 'reason_type', 'preferred_date', 'created_at')
    list_filter = ('status', 'reason_type', 'created_at')
    search_fields = ('child__name', 'caregiver__username', 'caregiver__email', 'clinician__username')
    readonly_fields = ('created_at', 'updated_at', 'confirmed_at', 'completed_at')
    date_hierarchy = 'created_at'


@admin.register(MedicalReport)
class MedicalReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'appointment', 'original_filename', 'uploaded_by', 'size_bytes', 'uploaded_at')
    list_filter = ('uploaded_at',)
    search_fields = ('original_filename', 'appointment__id', 'uploaded_by__username')
    readonly_fields = ('uploaded_at', 'sha256', 'content_type', 'size_bytes')


@admin.register(ClinicianReview)
class ClinicianReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'appointment', 'updated_at')
    search_fields = ('appointment__id',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(SupportPlan)
class SupportPlanAdmin(admin.ModelAdmin):
    list_display = ('id', 'appointment', 'title', 'follow_up_required', 'follow_up_date', 'updated_at')
    list_filter = ('follow_up_required',)
    search_fields = ('title', 'appointment__id')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(AppointmentMessage)
class AppointmentMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'appointment', 'sender', 'created_at')
    search_fields = ('body', 'sender__username', 'appointment__id')
    readonly_fields = ('created_at',)


@admin.register(AppointmentAuditLog)
class AppointmentAuditLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'created_at', 'appointment', 'actor', 'action', 'from_status', 'to_status', 'ip_address')
    list_filter = ('action', 'created_at')
    search_fields = ('appointment__id', 'actor__username', 'action')
    readonly_fields = (
        'appointment', 'actor', 'action', 'from_status', 'to_status',
        'metadata', 'ip_address', 'created_at',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
