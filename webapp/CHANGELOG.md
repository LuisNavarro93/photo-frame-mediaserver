# Changelog

All notable changes to the photo-frame web app are documented here, in the
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format.

## [1.0.0] - 2026-11-17

### Added

- Upload app: add pictures/videos into `~/Pictures/uploads/` from any
  device on the LAN.
- Locator app: fix a picture/video's GPS location on a map, ported from
  [exif-location-patcher](https://github.com/LuisNavarro93/exif-location-patcher)
  and confined to `~/Pictures`.
- Shared-password login gating the whole site (no user accounts, no
  database).
