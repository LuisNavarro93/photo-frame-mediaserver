#!/usr/bin/env python3
"""Scan ~/Pictures for photos/videos and record each file's capture date in SQLite.

Walks the media folder, inserts any new files into the `media` table, then
reads each new file's EXIF DateTimeOriginal (falling back to CreateDate) via
exiftool and records it in `media_dates`. When a file has no EXIF date at
all (most commonly WhatsApp-forwarded images, which strip EXIF), its
filename is checked for an embedded date as a second fallback. Safe to
re-run: already-indexed files are skipped.
"""

import argparse
import json
import re
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path

PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".webp", ".nef", ".gif"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi"}
MEDIA_EXTENSIONS = PHOTO_EXTENSIONS | VIDEO_EXTENSIONS
EXIFTOOL_BATCH_SIZE = 200
MIN_YEAR = 1990

# WhatsApp Image 2026-06-19 at 4.42.18 PM(1).jpeg
FILENAME_WHATSAPP_PATTERN = re.compile(
    r"(\d{4})-(\d{2})-(\d{2}) at (\d{1,2})\.(\d{2})\.(\d{2})\s*([AaPp][Mm])"
)
# PHOTO-2026-02-18-20-03-12.jpg
FILENAME_DASHED_DATETIME_PATTERN = re.compile(
    r"(?<!\d)(\d{4})-(\d{2})-(\d{2})-(\d{2})-(\d{2})-(\d{2})(?!\d)"
)
# IMG_20251230_202041.jpg, PANO_20260202_095742.jpg
FILENAME_COMPACT_DATETIME_PATTERN = re.compile(
    r"(?<!\d)(\d{4})(\d{2})(\d{2})[_-](\d{2})(\d{2})(\d{2})(?!\d)"
)
# a bare YYYY-MM-DD somewhere in the name
FILENAME_DASHED_DATE_PATTERN = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")
# IMG-20190809-WA0010.jpg -- date with no embedded time
FILENAME_COMPACT_DATE_PATTERN = re.compile(r"(?<!\d)(\d{4})(\d{2})(\d{2})(?!\d)")


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


def build_datetime_str(str_year, str_month, str_day, str_hour="0", str_minute="0", str_second="0"):
    int_year = int(str_year)
    if not MIN_YEAR <= int_year <= datetime.now().year + 1:
        return None
    try:
        obj_datetime = datetime(
            int_year, int(str_month), int(str_day), int(str_hour), int(str_minute), int(str_second)
        )
    except ValueError:
        return None
    return obj_datetime.strftime("%Y-%m-%dT%H:%M:%S")


def parse_epoch_stem(str_stem):
    if not str_stem.isdigit() or len(str_stem) not in (10, 13):
        return None
    int_epoch_seconds = int(str_stem) // (1000 if len(str_stem) == 13 else 1)
    try:
        obj_datetime = datetime.fromtimestamp(int_epoch_seconds)
    except (ValueError, OSError, OverflowError):
        return None
    if not MIN_YEAR <= obj_datetime.year <= datetime.now().year + 1:
        return None
    return obj_datetime.strftime("%Y-%m-%dT%H:%M:%S")


def extract_date_from_filename(str_stem):
    obj_whatsapp_match = FILENAME_WHATSAPP_PATTERN.search(str_stem)
    if obj_whatsapp_match:
        str_year, str_month, str_day, str_hour12, str_minute, str_second, str_ampm = (
            obj_whatsapp_match.groups()
        )
        int_hour24 = int(str_hour12) % 12
        if str_ampm.upper() == "PM":
            int_hour24 += 12
        str_date_taken = build_datetime_str(str_year, str_month, str_day, int_hour24, str_minute, str_second)
        if str_date_taken:
            return str_date_taken

    for obj_pattern in (FILENAME_DASHED_DATETIME_PATTERN, FILENAME_COMPACT_DATETIME_PATTERN):
        for obj_match in obj_pattern.finditer(str_stem):
            str_date_taken = build_datetime_str(*obj_match.groups())
            if str_date_taken:
                return str_date_taken

    str_date_taken = parse_epoch_stem(str_stem)
    if str_date_taken:
        return str_date_taken

    for obj_pattern in (FILENAME_DASHED_DATE_PATTERN, FILENAME_COMPACT_DATE_PATTERN):
        for obj_match in obj_pattern.finditer(str_stem):
            str_date_taken = build_datetime_str(*obj_match.groups())
            if str_date_taken:
                return str_date_taken

    return None


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
        if not str_date_taken:
            str_date_taken = extract_date_from_filename(Path(str_path).stem)
            if str_date_taken:
                str_date_source = "filename"
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
