#!/usr/bin/env python3
"""Django's command-line utility for the photo-frame web app."""
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "frame_web.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as obj_error:
        raise ImportError(
            "Couldn't import Django. Install it with: sudo apt install python3-django"
        ) from obj_error
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
