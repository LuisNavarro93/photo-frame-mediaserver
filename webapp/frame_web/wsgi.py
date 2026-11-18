"""WSGI entrypoint for the photo-frame web app."""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "frame_web.settings")
application = get_wsgi_application()
