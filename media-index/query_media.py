#!/usr/bin/env python3
"""Fast single-file lookup against the media-index database, for the
slideshow's caption overlay (clock.lua).

Prints "<date>\\n<location>\\n<map_path>" (any line may be blank) and
exits 0, or exits 1 if the file hasn't been indexed by build_index.py yet.
"""
import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

GEO_ROUND = 2  # must match build_index.py's rounding, to land on the same geo_key


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
        SELECT media_dates.date_taken, media_locations.location,
               media_locations.lat, media_locations.lon
        FROM media
        LEFT JOIN media_dates ON media_dates.media_id = media.id
        LEFT JOIN media_locations ON media_locations.media_id = media.id
        WHERE media.path = ?
        """,
        (obj_args.path,),
    ).fetchone()
    if obj_row is None:
        sys.exit(1)

    str_date_taken, str_location, num_lat, num_lon = obj_row

    str_map_path = ""
    if num_lat is not None and num_lon is not None:
        str_geo_key = f"{round(num_lat, GEO_ROUND)},{round(num_lon, GEO_ROUND)}"
        obj_map_row = obj_conn.execute(
            "SELECT map_path FROM map_cache WHERE geo_key = ?", (str_geo_key,)
        ).fetchone()
        if obj_map_row and obj_map_row[0]:
            str_map_path = obj_map_row[0]

    print(format_date(str_date_taken) or "")
    print(str_location or "")
    print(str_map_path)


if __name__ == "__main__":
    main()
