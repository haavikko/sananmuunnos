"""URL Configuration"""

from django.urls import include, path

urlpatterns = [
    path('word_transform/', include('word_transform.urls'))
]
