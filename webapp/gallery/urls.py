"""URL routes for the gallery (upload) app."""
from django.urls import path

from . import views

app_name = "gallery"

urlpatterns = [
    path("", views.upload_view, name="upload"),
]
