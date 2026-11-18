"""Upload pictures/videos into the slideshow's Pictures folder.

Saved files land in GALLERY_ROOT_DIR/uploads and show up in the slideshow
the next time it loops the playlist (slideshow.sh re-scans the whole
folder on every pass) -- see README.md for how to pick up their EXIF date
and location sooner by re-running media-index/build_index.py.
"""
import re
from pathlib import Path

from django.conf import settings
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

TUP_ALLOWED_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".heic", ".heif",
    ".tif", ".tiff", ".mp4", ".mov", ".m4v", ".3gp", ".avi", ".mkv", ".webm",
)

_RE_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9 ._-]")


def _safe_filename(str_name: str) -> str:
    """A plain basename with no path separators or unusual characters."""
    str_name = Path(str_name).name  # drops any directory components
    str_name = _RE_UNSAFE_CHARS.sub("_", str_name)
    return str_name.strip(" .") or "upload"


def _unique_destination(obj_dir: Path, str_name: str) -> Path:
    """Avoid clobbering an existing file by appending a numeric suffix."""
    obj_dest = obj_dir / str_name
    if not obj_dest.exists():
        return obj_dest
    str_stem, str_suffix = Path(str_name).stem, Path(str_name).suffix
    int_counter = 1
    while True:
        obj_dest = obj_dir / f"{str_stem}_{int_counter}{str_suffix}"
        if not obj_dest.exists():
            return obj_dest
        int_counter += 1


@require_http_methods(["GET", "POST"])
def upload_view(obj_request):
    lst_results = []
    if obj_request.method == "POST":
        obj_upload_dir = settings.GALLERY_ROOT_DIR / "uploads"
        obj_upload_dir.mkdir(parents=True, exist_ok=True)
        for obj_file in obj_request.FILES.getlist("files"):
            dict_result = {"name": obj_file.name, "ok": False, "error": ""}
            str_ext = Path(obj_file.name).suffix.lower()
            if str_ext not in TUP_ALLOWED_EXTENSIONS:
                dict_result["error"] = f"Unsupported file type ({str_ext or 'none'})."
            else:
                obj_dest = _unique_destination(obj_upload_dir, _safe_filename(obj_file.name))
                with open(obj_dest, "wb") as obj_out:
                    for obj_chunk in obj_file.chunks():
                        obj_out.write(obj_chunk)
                dict_result["ok"] = True
                dict_result["name"] = obj_dest.name
            lst_results.append(dict_result)
    return render(obj_request, "gallery/upload.html", {"lst_results": lst_results})
