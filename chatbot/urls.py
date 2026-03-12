from django.urls import path
from . import views

app_name = "chatbot"

urlpatterns = [
    path("", views.chat_page, name="chat_page"),
    path("api/ask/", views.chat_ask, name="chat_ask"),
]
