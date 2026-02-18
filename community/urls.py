from django.urls import path
from . import views

urlpatterns = [
    path("", views.community_home, name="community_home"),
    path("inbox/", views.community_inbox, name="community_inbox"),
    path("start/<int:user_id>/", views.community_start_thread, name="community_start_thread"),
    path("thread/<int:thread_id>/", views.community_thread, name="community_thread"),
    path("block/<int:user_id>/", views.community_block_user, name="community_block_user"),
    path("unblock/<int:user_id>/", views.community_unblock_user, name="community_unblock_user"),
    path("thread/<int:thread_id>/mark-read/", views.mark_messages_read, name="community_mark_read"),
    path("api/thread/<int:thread_id>/read-status/", views.thread_read_status, name="community_read_status"),
]
