"""Shared-password gate for the whole site -- no user accounts, no database.

Everything here can write into ~/Pictures, so every page except the login
form itself requires the one shared password (set with set_password.py)
before LoginRequiredMiddleware lets the request through.
"""
import os
from pathlib import Path

from django.contrib.auth.hashers import check_password
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

PASSWORD_HASH_PATH = Path(
    os.environ.get(
        "PHOTO_FRAME_WEB_PASSWORD_FILE",
        Path.home() / ".config" / "photo-frame-web" / "password.hash",
    )
)

SESSION_KEY = "photo_frame_authenticated"


def is_authenticated(obj_request) -> bool:
    return bool(obj_request.session.get(SESSION_KEY))


class LoginRequiredMiddleware:
    """Redirect every request to the login page until the password is entered."""

    def __init__(self, obj_get_response):
        self.obj_get_response = obj_get_response

    def __call__(self, obj_request):
        str_login_path = reverse("login")
        bool_exempt = obj_request.path.startswith("/static/") or obj_request.path == str_login_path
        if not bool_exempt and not is_authenticated(obj_request):
            return redirect(f"{str_login_path}?next={obj_request.get_full_path()}")
        return self.obj_get_response(obj_request)


@require_http_methods(["GET", "POST"])
def login_view(obj_request):
    str_error = ""
    if obj_request.method == "POST":
        str_entered = obj_request.POST.get("password", "")
        str_stored_hash = (
            PASSWORD_HASH_PATH.read_text().strip() if PASSWORD_HASH_PATH.exists() else ""
        )
        if str_stored_hash and check_password(str_entered, str_stored_hash):
            obj_request.session[SESSION_KEY] = True
            obj_request.session.set_expiry(60 * 60 * 24 * 30)
            return redirect(obj_request.GET.get("next") or reverse("gallery:upload"))
        str_error = (
            "Wrong password."
            if str_stored_hash
            else "No password set yet -- run webapp/set_password.py on the server first."
        )
    return render(obj_request, "login.html", {"str_error": str_error})


def logout_view(obj_request):
    obj_request.session.pop(SESSION_KEY, None)
    return redirect(reverse("login"))
