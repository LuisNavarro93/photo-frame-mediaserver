"""Root URL config: login/logout, then the gallery and locator apps."""
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, path

from frame_web import auth

urlpatterns = [
    path("login/", auth.login_view, name="login"),
    path("logout/", auth.logout_view, name="logout"),
    path("", include("gallery.urls")),
    path("locate/", include("locator.urls")),
]
urlpatterns += staticfiles_urlpatterns()
