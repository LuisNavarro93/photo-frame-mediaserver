"""Views: folder picker, workspace page, and the JSON endpoints they use."""

import json
from pathlib import Path

from django.http import FileResponse, Http404, HttpResponseBadRequest, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_http_methods

from . import gps, services


@require_GET
def landing_view(obj_request):
    """Folder browser confined to the pictures library: pick a folder, then open it."""
    str_path = obj_request.GET.get("path") or ""
    str_error = ""
    try:
        obj_folder = services.resolve_folder(str_path)
    except services.InvalidPathError as obj_error:
        str_error = str(obj_error)
        obj_folder = services.resolve_folder("")

    obj_root = services.resolve_folder("")
    obj_parent = obj_folder.parent if obj_folder != obj_root else None
    return render(obj_request, "locator/landing.html", {
        "str_folder": str(obj_folder),
        "str_relative": services.relative_label(obj_folder),
        "str_parent": str(obj_parent) if obj_parent is not None else None,
        "lst_subfolders": services.list_subfolders(obj_folder),
        "int_media_count": services.count_media(obj_folder),
        "str_error": str_error,
    })


@require_GET
def workspace_view(obj_request):
    """Thumbnails on the left, map with the location pin on the right."""
    try:
        obj_folder = services.resolve_folder(obj_request.GET.get("folder", ""))
    except services.InvalidPathError as obj_error:
        raise Http404(str(obj_error)) from obj_error
    return render(obj_request, "locator/workspace.html", {
        "str_folder": str(obj_folder),
        "str_relative": services.relative_label(obj_folder),
    })


@require_GET
def media_list_api(obj_request):
    try:
        obj_folder = services.resolve_folder(obj_request.GET.get("folder", ""))
    except services.InvalidPathError as obj_error:
        return JsonResponse({"error": str(obj_error)}, status=400)
    return JsonResponse({"folder": str(obj_folder), "items": services.list_media(obj_folder)})


@require_GET
def thumbnail_view(obj_request):
    try:
        obj_path = services.resolve_media_file(
            obj_request.GET.get("folder", ""), obj_request.GET.get("name", "")
        )
    except services.InvalidPathError as obj_error:
        raise Http404(str(obj_error)) from obj_error
    obj_response = FileResponse(open(services.get_thumbnail(obj_path), "rb"), content_type="image/jpeg")
    obj_response["Cache-Control"] = "private, max-age=3600"
    return obj_response


@require_GET
def media_file_view(obj_request):
    """Serve the original picture or video so the browser can show it full size."""
    try:
        obj_path = services.resolve_media_file(
            obj_request.GET.get("folder", ""), obj_request.GET.get("name", "")
        )
    except services.InvalidPathError as obj_error:
        raise Http404(str(obj_error)) from obj_error
    obj_response = FileResponse(open(obj_path, "rb"), filename=obj_path.name)
    obj_response["Cache-Control"] = "private, no-cache"
    return obj_response


@require_http_methods(["GET", "POST"])
def location_api(obj_request):
    """GET re-reads one file's location; POST writes a location into files."""
    if obj_request.method == "GET":
        try:
            obj_path = services.resolve_media_file(
                obj_request.GET.get("folder", ""), obj_request.GET.get("name", "")
            )
        except services.InvalidPathError as obj_error:
            return JsonResponse({"error": str(obj_error)}, status=400)
        return JsonResponse({"name": obj_path.name, "location": gps.read_location(obj_path)})

    try:
        dict_body = json.loads(obj_request.body or b"{}")
        str_folder = str(dict_body["folder"])
        lst_names = [str(str_name) for str_name in dict_body["names"]]
        flt_lat, flt_lon = float(dict_body["lat"]), float(dict_body["lon"])
        gps.validate_coordinates(flt_lat, flt_lon)
    except (ValueError, KeyError, TypeError, gps.LocationError) as obj_error:
        return HttpResponseBadRequest(f"Invalid request: {obj_error}")

    lst_results = []
    for str_name in lst_names:
        dict_result = {"name": str_name, "ok": False, "location": None, "error": ""}
        try:
            obj_path = services.resolve_media_file(str_folder, str_name)
            gps.write_location(obj_path, flt_lat, flt_lon)
            dict_result["location"] = gps.read_location(obj_path)
            dict_result["ok"] = True
        except (services.InvalidPathError, gps.LocationError, OSError) as obj_error:
            dict_result["error"] = str(obj_error)
        lst_results.append(dict_result)
    return JsonResponse({"results": lst_results})
