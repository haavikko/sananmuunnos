"""sananmuunnos URL Configuration

from django.urls import path

import word_transform.views

urlpatterns = [
    path("/word_transform/", word_transform.views.word_transform, name="word_transform"),
]
