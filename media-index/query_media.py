#!/usr/bin/env python3
"""Fast single-file lookup against the media-index database, for the
slideshow's caption overlay (clock.lua).

Prints "<date>\\n<location>" (either line may be blank) and exits 0, or
exits 1 if the file hasn't been indexed by build_index.py yet.
"""
import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


def format_date(str_iso_date):
    if not str_iso_date:
        return None
    try:
        return datetime.strptime(str_iso_date[:10], "%Y-%m-%d").strftime("%d %b %Y")
    except ValueError:
        return None


def main():
    obj_parser = argparse.ArgumentParser(description=__doc__)
    obj_parser.add_argument("path")
    obj_parser.add_argument(
        "--db", default=str(Path.home() / "Desktop" / "media-index" / "media.db")
    )
    obj_args = obj_parser.parse_args()

    obj_db_path = Path(obj_args.db)
    if not obj_db_path.exists():
        sys.exit(1)

    obj_conn = sqlite3.connect(obj_db_path)
    obj_row = obj_conn.execute(
        """
        SELECT media_dates.date_taken, media_locations.location
        FROM media
        LEFT JOIN media_dates ON media_dates.media_id = media.id
        LEFT JOIN media_locations ON media_locations.media_id = media.id
        WHERE media.path = ?
        """,
        (obj_args.path,),
    ).fetchone()
    if obj_row is None:
        sys.exit(1)

    str_date_taken, str_location = obj_row
    print(format_date(str_date_taken) or "")
    print(str_location or "")


if __name__ == "__main__":
    main()
