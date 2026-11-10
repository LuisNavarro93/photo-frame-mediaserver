PRAGMA foreign_keys = ON;

-- One row per file found under ~/Pictures.
CREATE TABLE IF NOT EXISTS media (
    id INTEGER PRIMARY KEY,
    path TEXT NOT NULL UNIQUE,
    filename TEXT NOT NULL,
    media_type TEXT NOT NULL CHECK (media_type IN ('photo', 'video')),
    extension TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    indexed_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now'))
);

-- One row per media file once its capture date has been looked up: via
-- exiftool first (DateTimeOriginal, falling back to CreateDate), then by
-- parsing a date out of the filename when neither EXIF tag is present.
-- date_taken is NULL when none of those yield a date -- this still counts
-- as "processed" so build_index.py doesn't retry it on every run.
CREATE TABLE IF NOT EXISTS media_dates (
    media_id INTEGER PRIMARY KEY REFERENCES media(id) ON DELETE CASCADE,
    date_taken TEXT,
    date_source TEXT CHECK (date_source IN ('DateTimeOriginal', 'CreateDate', 'filename'))
);

CREATE INDEX IF NOT EXISTS idx_media_dates_date_taken ON media_dates(date_taken);

-- One row per media file once its GPS location has been looked up (same
-- "processed, possibly empty" idiom as media_dates): lat/lon/location are
-- all NULL when the file carries no GPS EXIF tags.
CREATE TABLE IF NOT EXISTS media_locations (
    media_id INTEGER PRIMARY KEY REFERENCES media(id) ON DELETE CASCADE,
    lat REAL,
    lon REAL,
    location TEXT
);

-- Reverse-geocode results cached by rounded (~1.1km) coordinate, so photos
-- taken near each other share one Nominatim lookup instead of one each.
CREATE TABLE IF NOT EXISTS geocode_cache (
    geo_key TEXT PRIMARY KEY,
    location TEXT
);
