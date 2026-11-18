#!/usr/bin/env python3
"""Set (or change) the shared login password for the photo-frame web app.

Run this once on the server before the first login, and again any time the
password should change -- no need to stop the server first.
"""
import getpass
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "frame_web.settings")

import django  # noqa: E402

django.setup()

from django.contrib.auth.hashers import make_password  # noqa: E402

from frame_web.auth import PASSWORD_HASH_PATH  # noqa: E402


def main():
    str_password = getpass.getpass("New shared password: ")
    str_confirm = getpass.getpass("Confirm: ")
    if not str_password:
        print("Password can't be empty.")
        raise SystemExit(1)
    if str_password != str_confirm:
        print("Passwords didn't match.")
        raise SystemExit(1)

    PASSWORD_HASH_PATH.parent.mkdir(parents=True, exist_ok=True)
    PASSWORD_HASH_PATH.write_text(make_password(str_password))
    PASSWORD_HASH_PATH.chmod(0o600)
    print(f"Password updated ({PASSWORD_HASH_PATH}).")


if __name__ == "__main__":
    main()
