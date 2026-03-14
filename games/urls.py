from django.urls import path
from . import views

urlpatterns = [
    path('', views.game_list, name='game_list'),
    path('debug/static-check/', views.static_check, name='static_check'),
    path('<slug:slug>/', views.game_detail, name='game_detail'),
]
