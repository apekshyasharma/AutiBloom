from django.contrib import admin
from .models import ChildProfile, CaregiverChild, WellbeingQuestion, WeeklyWellbeingEntry, WeeklyWellbeingAnswer, PredictionResult

# Register your models here.

@admin.register(ChildProfile)
class ChildProfileAdmin(admin.ModelAdmin):
    list_display = ('name', 'date_of_birth', 'created_at')
    search_fields = ('name',)

@admin.register(CaregiverChild)
class CaregiverChildAdmin(admin.ModelAdmin):
    list_display = ('caregiver', 'child', 'created_at')
    search_fields = ('caregiver__username', 'child__name')
    list_filter = ('created_at',)

@admin.register(WellbeingQuestion)
class WellbeingQuestionAdmin(admin.ModelAdmin):
    list_display = ('code', 'domain', 'text_preview', 'order', 'is_active')
    list_filter = ('domain', 'is_active')
    search_fields = ('code', 'text')
    ordering = ('order',)

    def text_preview(self, obj):
        return obj.text[:50] + "..." if len(obj.text) > 50 else obj.text
    text_preview.short_description = "Text"

class WeeklyWellbeingAnswerInline(admin.TabularInline):
    model = WeeklyWellbeingAnswer
    extra = 0
    readonly_fields = ('binary_flag',) # Computed, so typically readonly in admin or auto-calc on save
    fields = ('question', 'slider_score', 'binary_flag', 'comment')

@admin.register(WeeklyWellbeingEntry)
class WeeklyWellbeingEntryAdmin(admin.ModelAdmin):
    list_display = ('caregiver', 'child', 'week_start', 'status', 'overall_score', 'submitted_at')
    list_filter = ('status', 'week_start')
    search_fields = ('caregiver__username', 'child__name')
    inlines = [WeeklyWellbeingAnswerInline]
    readonly_fields = (
        'overall_score', 
        'communication_score', 
        'routines_score', 
        'emotional_score', 
        'sensory_score'
    )
    
    fieldsets = (
        ('Entry Details', {
            'fields': ('caregiver', 'child', 'week_start', 'week_end', 'status', 'submitted_at')
        }),
        ('Metrics (Computed)', {
            'fields': ('overall_score', 'communication_score', 'routines_score', 'emotional_score', 'sensory_score')
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
    )

@admin.register(WeeklyWellbeingAnswer)
class WeeklyWellbeingAnswerAdmin(admin.ModelAdmin):
    list_display = ('entry', 'question', 'slider_score', 'binary_flag')
    list_filter = ('question__domain',)


@admin.register(PredictionResult)
class PredictionResultAdmin(admin.ModelAdmin):
    list_display = ('caregiver', 'child', 'entry', 'prediction_label', 'model_version', 'created_at')
    list_filter = ('model_version', 'created_at')
    search_fields = ('caregiver__username', 'child__name')

