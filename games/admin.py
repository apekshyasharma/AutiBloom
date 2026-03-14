from django.contrib import admin
from .models import TherapyGame

from django.utils.html import format_html
from django.urls import reverse

@admin.register(TherapyGame)
class TherapyGameAdmin(admin.ModelAdmin):
    list_display = ('title', 'embed_type', 'age_range', 'is_active', 'preview_link', 'created_at')
    list_filter = ('is_active',)
    prepopulated_fields = {'slug': ('title',)}
    search_fields = ('title', 'goal')

    def preview_link(self, obj):
        url = reverse('game_detail', args=[obj.slug])
        return format_html('<a href="{}" target="_blank">Preview</a>', url)
    preview_link.short_description = "Preview"
