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

-- One row per media file once its capture date has been looked up via
-- exiftool. date_taken is NULL when the file carries no DateTimeOriginal
-- or CreateDate tag -- this still counts as "processed" so build_index.py
-- doesn't retry it on every run.
CREATE TABLE IF NOT EXISTS media_dates (
    media_id INTEGER PRIMARY KEY REFERENCES media(id) ON DELETE CASCADE,
    date_taken TEXT,
    date_source TEXT CHECK (date_source IN ('DateTimeOriginal', 'CreateDate'))
);

CREATE INDEX IF NOT EXISTS idx_media_dates_date_taken ON media_dates(date_taken);
