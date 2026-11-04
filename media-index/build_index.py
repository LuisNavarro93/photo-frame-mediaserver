#!/usr/bin/env python3
"""Scan ~/Pictures for photos/videos and record each file's capture date in SQLite.

Walks the media folder, inserts any new files into the `media` table, then
reads each new file's EXIF DateTimeOriginal (falling back to CreateDate) via
exiftool and records it in `media_dates`. Safe to re-run: already-indexed
files are skipped.
"""

import argparse
import json
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path

PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".webp", ".nef", ".gif"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi"}
MEDIA_EXTENSIONS = PHOTO_EXTENSIONS | VIDEO_EXTENSIONS
EXIFTOOL_BATCH_SIZE = 200


def parse_args():
    obj_parser = argparse.ArgumentParser(description=__doc__)
    obj_parser.add_argument(
        "--pictures-dir",
        default=str(Path.home() / "Pictures"),
        help="Folder to scan for photos/videos (default: ~/Pictures)",
    )
    obj_parser.add_argument(
        "--db",
        default=str(Path.home() / "Desktop" / "media-index" / "media.db"),
        help="SQLite database path (default: ~/Desktop/media-index/media.db)",
    )
    return obj_parser.parse_args()


def connect(obj_db_path: Path) -> sqlite3.Connection:
    obj_db_path.parent.mkdir(parents=True, exist_ok=True)
    obj_conn = sqlite3.connect(obj_db_path)
    obj_conn.execute("PRAGMA foreign_keys = ON")
    str_schema = (Path(__file__).parent / "schema.sql").read_text()
    obj_conn.executescript(str_schema)
    return obj_conn


def discover_media_files(obj_pictures_dir: Path):
    lst_files = [
        obj_path
        for obj_path in obj_pictures_dir.rglob("*")
        if obj_path.is_file() and obj_path.suffix.lower() in MEDIA_EXTENSIONS
    ]
    return lst_files


def insert_new_media(obj_conn: sqlite3.Connection, lst_files) -> None:
    for obj_path in lst_files:
        str_extension = obj_path.suffix.lower().lstrip(".")
        str_media_type = "video" if obj_path.suffix.lower() in VIDEO_EXTENSIONS else "photo"
        int_size_bytes = obj_path.stat().st_size
        obj_conn.execute(
            """
            INSERT OR IGNORE INTO media (path, filename, media_type, extension, size_bytes)
            VALUES (?, ?, ?, ?, ?)
            """,
            (str(obj_path), obj_path.name, str_media_type, str_extension, int_size_bytes),
        )
    obj_conn.commit()


def fetch_unprocessed_media(obj_conn: sqlite3.Connection):
    obj_cursor = obj_conn.execute(
        """
        SELECT media.id, media.path
        FROM media
        LEFT JOIN media_dates ON media_dates.media_id = media.id
        WHERE media_dates.media_id IS NULL
        """
    )
    return obj_cursor.fetchall()


def parse_exif_date(str_raw_date):
    if not str_raw_date:
        return None
    try:
        obj_datetime = datetime.strptime(str_raw_date[:19], "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None
    return obj_datetime.strftime("%Y-%m-%dT%H:%M:%S")


def read_capture_dates(lst_paths):
    dict_dates_by_path = {}
    for int_start in range(0, len(lst_paths), EXIFTOOL_BATCH_SIZE):
        lst_batch = lst_paths[int_start : int_start + EXIFTOOL_BATCH_SIZE]
        # exiftool exits 1 whenever any single file in the batch triggers a
        # warning (e.g. an unsupported/corrupt file), even though it still
        # prints valid JSON for every other file -- so the exit code isn't
        # checked here.
        str_output = subprocess.run(
            ["exiftool", "-j", "-DateTimeOriginal", "-CreateDate", *lst_batch],
            capture_output=True,
            text=True,
        ).stdout
        lst_entries = json.loads(str_output)
        for dict_entry in lst_entries:
            str_path = dict_entry["SourceFile"]
            str_date_taken = None
            str_date_source = None
            for str_tag in ("DateTimeOriginal", "CreateDate"):
                str_date_taken = parse_exif_date(dict_entry.get(str_tag))
                if str_date_taken:
                    str_date_source = str_tag
                    break
            dict_dates_by_path[str_path] = (str_date_taken, str_date_source)
    return dict_dates_by_path


def insert_dates(obj_conn: sqlite3.Connection, lst_pending, dict_dates_by_path) -> None:
    for int_media_id, str_path in lst_pending:
        tup_date = dict_dates_by_path.get(str_path, (None, None))
        str_date_taken, str_date_source = tup_date
        obj_conn.execute(
            """
            INSERT INTO media_dates (media_id, date_taken, date_source)
            VALUES (?, ?, ?)
            """,
            (int_media_id, str_date_taken, str_date_source),
        )
    obj_conn.commit()


def main():
    obj_args = parse_args()
    obj_pictures_dir = Path(obj_args.pictures_dir).expanduser()
    obj_db_path = Path(obj_args.db).expanduser()

    obj_conn = connect(obj_db_path)

    lst_files = discover_media_files(obj_pictures_dir)
    print(f"Found {len(lst_files)} media files under {obj_pictures_dir}")

    insert_new_media(obj_conn, lst_files)

    lst_pending = fetch_unprocessed_media(obj_conn)
    print(f"Reading capture dates for {len(lst_pending)} new/unprocessed files")

    if lst_pending:
        lst_pending_paths = [str_path for _, str_path in lst_pending]
        dict_dates_by_path = read_capture_dates(lst_pending_paths)
        insert_dates(obj_conn, lst_pending, dict_dates_by_path)

    int_total = obj_conn.execute("SELECT COUNT(*) FROM media").fetchone()[0]
    int_with_date = obj_conn.execute(
        "SELECT COUNT(*) FROM media_dates WHERE date_taken IS NOT NULL"
    ).fetchone()[0]
    print(f"Database now has {int_total} files indexed, {int_with_date} with a capture date")

    obj_conn.close()


if __name__ == "__main__":
    main()
