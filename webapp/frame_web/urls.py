"""Root URL config: login/logout, then the gallery and locator apps."""
from django.contrib.staticfiles.views import serve as static_serve
from django.urls import include, path, re_path

from frame_web import auth

urlpatterns = [
    path("login/", auth.login_view, name="login"),
    path("logout/", auth.logout_view, name="logout"),
    path("", include("gallery.urls")),
    path("locate/", include("locator.urls")),
]
# staticfiles_urlpatterns() only registers this route when settings.DEBUG is
# true, which this project deliberately isn't (it's reachable from the
# whole LAN). Calling the finders-aware view directly with insecure=True
# serves the same per-app static/ folders without needing collectstatic --
# fine at this project's tiny, fixed set of CSS/JS files.
urlpatterns += [
    re_path(r"^static/(?P<path>.*)$", static_serve, kwargs={"insecure": True}),
]
