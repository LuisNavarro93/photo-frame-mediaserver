"""URL routes for the locator (GPS fixer) app."""

from django.urls import path

from . import views

app_name = "locator"

urlpatterns = [
    path("", views.landing_view, name="landing"),
    path("workspace/", views.workspace_view, name="workspace"),
    path("api/media/", views.media_list_api, name="media_list"),
    path("api/location/", views.location_api, name="location"),
    path("thumbnail/", views.thumbnail_view, name="thumbnail"),
    path("file/", views.media_file_view, name="media_file"),
]
