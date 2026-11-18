"""Django settings for the photo-frame web app (uploads + GPS location fixer).

Runs in place inside the photo-frame-mediaserver repo, bound to the whole
LAN so any device on the home network can reach it -- see README.md for
the reasoning. It can write into ~/Pictures, so every page except the
login form itself is gated behind a single shared password (set with
set_password.py); see frame_web/auth.py.
"""

import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_or_create_secret_key() -> str:
    """A key that survives restarts, generated once and cached outside the repo."""
    str_env_key = os.environ.get("DJANGO_SECRET_KEY")
    if str_env_key:
        return str_env_key
    obj_key_path = Path.home() / ".config" / "photo-frame-web" / "secret_key"
    if obj_key_path.exists():
        return obj_key_path.read_text().strip()
    obj_key_path.parent.mkdir(parents=True, exist_ok=True)
    str_key = secrets.token_hex(32)
    obj_key_path.write_text(str_key)
    obj_key_path.chmod(0o600)
    return str_key


SECRET_KEY = _load_or_create_secret_key()

DEBUG = os.environ.get("DJANGO_DEBUG", "false").lower() == "true"

ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "django.contrib.sessions",
    "gallery",
    "locator",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "frame_web.auth.LoginRequiredMiddleware",
]

ROOT_URLCONF = "frame_web.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "frame_web" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
            ],
        },
    },
]

WSGI_APPLICATION = "frame_web.wsgi.application"

# No database: sessions are signed cookies and there's one shared password
# (frame_web/auth.py), not a User model -- nothing here needs persistence
# Django itself would own.
DATABASES = {}
SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 30
SESSION_COOKIE_SECURE = False  # plain http on the LAN, no TLS
CSRF_COOKIE_SECURE = False

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = True

# OpenStreetMap blocks tile requests with no Referer header, which Django's
# default "same-origin" policy strips from the map's own cross-site tile
# requests (same reasoning as the original exif-location-patcher).
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "frame_web" / "static"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# A multi-file photo/video upload must not be rejected for exceeding the
# default POST data cap. Files still spill to a temp file on disk past
# FILE_UPLOAD_MAX_MEMORY_SIZE regardless of this setting.
DATA_UPLOAD_MAX_MEMORY_SIZE = None

# Every upload and every GPS fix is confined to this folder (and its
# subfolders) -- resolve_folder()/resolve_media_file() in locator/services.py
# refuse to resolve anything outside it, even if a request asks to.
GALLERY_ROOT_DIR = Path(os.environ.get("PHOTO_FRAME_PICTURES_DIR", Path.home() / "Pictures"))

# Cached GPS-workspace thumbnails, keyed by file path + mtime.
OBJ_LOCATOR_THUMBNAIL_CACHE_DIR = Path(
    os.environ.get(
        "PHOTO_FRAME_THUMBNAIL_CACHE_DIR",
        Path.home() / ".cache" / "photo-frame-web" / "thumbnails",
    )
)
INT_LOCATOR_THUMBNAIL_SIZE_PX = int(os.environ.get("PHOTO_FRAME_THUMBNAIL_SIZE_PX", "320"))
