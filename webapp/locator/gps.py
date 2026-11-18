"""Read and write the GPS location stored in pictures and videos.

Pictures use EXIF GPS tags (read with Pillow, written with piexif).
Videos use the QuickTime/MP4 ISO 6709 location tag (read with ffprobe,
written with ffmpeg by remuxing the streams unchanged).

Writes go to a temporary file next to the original, which then replaces
it, so a failed write never leaves a half-written file behind. The
original file's permissions and modification time are kept.

Ported from the exif-location-patcher project (same author); the only
change from that project's patcher/gps.py is this docstring note.
"""

import io
import json
import math
import os
import re
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path

import piexif
from PIL import ExifTags, Image

TUP_IMAGE_READ_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff")
TUP_IMAGE_WRITE_EXTENSIONS = (".jpg", ".jpeg", ".webp")
TUP_VIDEO_EXTENSIONS = (".mp4", ".mov", ".m4v", ".3gp")
TUP_VIDEO_WRITE_EXTENSIONS = (".mp4", ".mov", ".m4v")

# Tags in which phones/cameras store an ISO 6709 location string in videos.
LST_VIDEO_LOCATION_TAGS = [
    "com.apple.quicktime.location.ISO6709",
    "location",
    "location-eng",
]

_RE_ISO6709 = re.compile(r"^\s*([+-]\d+(?:\.\d+)?)([+-]\d+(?:\.\d+)?)")


class LocationError(Exception):
    """Raised when a location can't be read from or written to a file."""


def is_image(obj_path: Path) -> bool:
    return obj_path.suffix.lower() in TUP_IMAGE_READ_EXTENSIONS


def is_video(obj_path: Path) -> bool:
    return obj_path.suffix.lower() in TUP_VIDEO_EXTENSIONS


def is_writable_format(obj_path: Path) -> bool:
    """Whether this app knows how to write a location into this file type."""
    str_suffix = obj_path.suffix.lower()
    if str_suffix in TUP_VIDEO_WRITE_EXTENSIONS:
        return shutil.which("ffmpeg") is not None
    return str_suffix in TUP_IMAGE_WRITE_EXTENSIONS


def validate_coordinates(flt_lat: float, flt_lon: float) -> None:
    if not (-90.0 <= flt_lat <= 90.0) or not (-180.0 <= flt_lon <= 180.0):
        raise LocationError("Latitude must be within ±90 and longitude within ±180.")


# --------------------------------------------------------------------------
# Reading
# --------------------------------------------------------------------------


def read_location(obj_path: Path) -> dict | None:
    """Return ``{"lat": float, "lon": float}`` or None if the file has no location."""
    try:
        if is_image(obj_path):
            return _read_image_location(obj_path)
        if is_video(obj_path):
            return _read_video_location(obj_path)
    except (OSError, ValueError, ZeroDivisionError, subprocess.SubprocessError):
        return None
    return None


def _read_image_location(obj_path: Path) -> dict | None:
    with Image.open(obj_path) as obj_image:
        dict_gps = obj_image.getexif().get_ifd(ExifTags.IFD.GPSInfo)
    if not dict_gps:
        return None
    tup_lat = dict_gps.get(ExifTags.GPS.GPSLatitude)
    tup_lon = dict_gps.get(ExifTags.GPS.GPSLongitude)
    if not tup_lat or not tup_lon:
        return None
    flt_lat = _dms_to_degrees(tup_lat)
    flt_lon = _dms_to_degrees(tup_lon)
    if str(dict_gps.get(ExifTags.GPS.GPSLatitudeRef, "N")).upper().startswith("S"):
        flt_lat = -flt_lat
    if str(dict_gps.get(ExifTags.GPS.GPSLongitudeRef, "E")).upper().startswith("W"):
        flt_lon = -flt_lon
    # Some phones write a GPS block full of 0/0 values when they had no fix,
    # which reads as NaN.
    if not (math.isfinite(flt_lat) and math.isfinite(flt_lon)):
        return None
    if not (-90.0 <= flt_lat <= 90.0 and -180.0 <= flt_lon <= 180.0):
        return None
    if flt_lat == 0.0 and flt_lon == 0.0:
        # Some cameras write 0/0 when they had no fix.
        return None
    return {"lat": round(flt_lat, 7), "lon": round(flt_lon, 7)}


def _dms_to_degrees(tup_dms) -> float:
    if not isinstance(tup_dms, (tuple, list)):
        tup_dms = (tup_dms,)
    lst_parts = [float(obj_value) for obj_value in tup_dms]
    while len(lst_parts) < 3:
        lst_parts.append(0.0)
    return lst_parts[0] + lst_parts[1] / 60.0 + lst_parts[2] / 3600.0


def _read_video_location(obj_path: Path) -> dict | None:
    if shutil.which("ffprobe") is None:
        return None
    obj_result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-print_format", "json",
            "-show_entries", "format_tags", str(obj_path),
        ],
        capture_output=True, text=True, timeout=30, check=False,
    )
    if obj_result.returncode != 0:
        return None
    dict_tags = json.loads(obj_result.stdout or "{}").get("format", {}).get("tags", {})
    dict_tags_lower = {str_key.lower(): str_value for str_key, str_value in dict_tags.items()}
    for str_tag in LST_VIDEO_LOCATION_TAGS:
        str_value = dict_tags_lower.get(str_tag.lower())
        if str_value:
            dict_location = parse_iso6709(str_value)
            if dict_location:
                return dict_location
    return None


def parse_iso6709(str_value: str) -> dict | None:
    """Parse the leading ``+DD.DDDD+DDD.DDDD`` part of an ISO 6709 string."""
    obj_match = _RE_ISO6709.match(str_value)
    if not obj_match:
        return None
    flt_lat, flt_lon = float(obj_match.group(1)), float(obj_match.group(2))
    if not (-90 <= flt_lat <= 90 and -180 <= flt_lon <= 180):
        return None
    return {"lat": round(flt_lat, 7), "lon": round(flt_lon, 7)}


def format_iso6709(flt_lat: float, flt_lon: float) -> str:
    return f"{flt_lat:+08.4f}{flt_lon:+09.4f}/"


# --------------------------------------------------------------------------
# Writing
# --------------------------------------------------------------------------


def write_location(obj_path: Path, flt_lat: float, flt_lon: float) -> None:
    """Write a GPS location into the file, replacing any existing one."""
    validate_coordinates(flt_lat, flt_lon)
    if not is_writable_format(obj_path):
        raise LocationError(f"Writing a location into {obj_path.suffix or 'this'} files isn't supported.")
    _check_can_replace(obj_path)

    obj_stat = obj_path.stat()
    obj_tmp_path = obj_path.with_name(f".{obj_path.stem}.patching{obj_path.suffix}")
    try:
        if obj_path.suffix.lower() in TUP_IMAGE_WRITE_EXTENSIONS:
            _write_image_location(obj_path, obj_tmp_path, flt_lat, flt_lon)
        else:
            _write_video_location(obj_path, obj_tmp_path, flt_lat, flt_lon)
        shutil.copymode(obj_path, obj_tmp_path)
        os.replace(obj_tmp_path, obj_path)
        os.utime(obj_path, ns=(obj_stat.st_atime_ns, obj_stat.st_mtime_ns))
    finally:
        if obj_tmp_path.exists():
            obj_tmp_path.unlink()


def _check_can_replace(obj_path: Path) -> None:
    """Raise unless the file can be swapped for an updated copy.

    The write replaces the file through its folder, so the folder must be
    writable. A file you own that is merely marked read-only (common for
    photos copied off phones) is allowed: its read-only mode is kept.
    """
    if not os.access(obj_path.parent, os.W_OK):
        raise LocationError(f"No permission to write in the folder {obj_path.parent}.")
    bool_is_owner = obj_path.stat().st_uid == os.getuid()
    if not os.access(obj_path, os.W_OK) and not bool_is_owner:
        raise LocationError("This file is read-only and belongs to another user.")


def _to_rational_dms(flt_degrees: float) -> tuple:
    flt_degrees = abs(flt_degrees)
    int_deg = int(flt_degrees)
    flt_min_full = (flt_degrees - int_deg) * 60
    int_min = int(flt_min_full)
    obj_sec = Fraction((flt_min_full - int_min) * 60).limit_denominator(10000)
    return ((int_deg, 1), (int_min, 1), (obj_sec.numerator, obj_sec.denominator))


def _write_image_location(obj_src: Path, obj_dst: Path, flt_lat: float, flt_lon: float) -> None:
    obj_image_bytes = obj_src.read_bytes()
    try:
        dict_exif = piexif.load(obj_image_bytes)
    except Exception:  # noqa: BLE001 - piexif raises plain Exceptions on odd files
        dict_exif = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}

    dict_exif["GPS"] = {
        piexif.GPSIFD.GPSVersionID: (2, 3, 0, 0),
        piexif.GPSIFD.GPSLatitudeRef: b"N" if flt_lat >= 0 else b"S",
        piexif.GPSIFD.GPSLatitude: _to_rational_dms(flt_lat),
        piexif.GPSIFD.GPSLongitudeRef: b"E" if flt_lon >= 0 else b"W",
        piexif.GPSIFD.GPSLongitude: _to_rational_dms(flt_lon),
    }
    obj_exif_bytes = _dump_exif_tolerantly(dict_exif)

    obj_buffer = io.BytesIO()
    try:
        piexif.insert(obj_exif_bytes, obj_image_bytes, obj_buffer)
    except Exception as obj_error:  # noqa: BLE001
        raise LocationError(f"Couldn't write EXIF data: {obj_error}") from obj_error
    obj_dst.write_bytes(obj_buffer.getvalue())


def _dump_exif_tolerantly(dict_exif: dict) -> bytes:
    """piexif.dump, dropping the tags that commonly break it when needed."""
    try:
        return piexif.dump(dict_exif)
    except Exception:  # noqa: BLE001
        pass
    # SceneType is often stored with a type piexif can't re-encode, and the
    # embedded thumbnail can be malformed; neither matters for the location.
    dict_exif.get("Exif", {}).pop(piexif.ExifIFD.SceneType, None)
    dict_exif.get("Exif", {}).pop(piexif.ExifIFD.MakerNote, None)
    dict_exif["1st"] = {}
    dict_exif["thumbnail"] = None
    try:
        return piexif.dump(dict_exif)
    except Exception as obj_error:  # noqa: BLE001
        raise LocationError(f"Couldn't encode EXIF data: {obj_error}") from obj_error


def _write_video_location(obj_src: Path, obj_dst: Path, flt_lat: float, flt_lon: float) -> None:
    str_iso = format_iso6709(flt_lat, flt_lon)
    lst_metadata_args = []
    for str_tag in LST_VIDEO_LOCATION_TAGS:
        lst_metadata_args += ["-metadata", f"{str_tag}={str_iso}"]

    lst_base = ["ffmpeg", "-v", "error", "-y", "-i", str(obj_src)]
    lst_tail = [
        "-c", "copy", "-map_metadata", "0", *lst_metadata_args,
        "-movflags", "use_metadata_tags", str(obj_dst),
    ]
    # Keep every stream first; if the container refuses one (e.g. a data
    # track), fall back to ffmpeg's default video+audio selection.
    for lst_map in (["-map", "0"], []):
        obj_result = subprocess.run(
            lst_base + lst_map + lst_tail,
            capture_output=True, text=True, timeout=600, check=False,
        )
        if obj_result.returncode == 0 and obj_dst.exists() and obj_dst.stat().st_size > 0:
            return
    raise LocationError(f"ffmpeg couldn't write the location: {obj_result.stderr.strip()[-300:]}")
