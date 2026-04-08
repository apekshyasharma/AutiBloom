from django.contrib import admin
from .models import CaregiverCommunityProfile, BlockedUser, Thread, Message

@admin.register(CaregiverCommunityProfile)
class CaregiverCommunityProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'opt_in', 'city', 'postal_code', 'updated_at')
    list_filter = ('opt_in',)
    search_fields = ('user__username', 'city', 'postal_code')

@admin.register(BlockedUser)
class BlockedUserAdmin(admin.ModelAdmin):
    list_display = ('blocker', 'blocked', 'created_at')
    search_fields = ('blocker__username', 'blocked__username')

@admin.register(Thread)
class ThreadAdmin(admin.ModelAdmin):
    list_display = ('id', 'created_at')
    filter_horizontal = ('participants',)

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('thread', 'sender', 'created_at', 'body_summary')
    list_filter = ('created_at',)
    search_fields = ('sender__username', 'body')

    def body_summary(self, obj):
        return obj.body[:50]
