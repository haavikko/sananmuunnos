"""URL Configuration"""

from django.urls import path

from . import views

urlpatterns = [
    path('', views.word_transform, name='word_transform'),
]
