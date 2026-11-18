"""Template context available on every page."""
from frame_web import __version__


def version(obj_request):
    return {"str_version": __version__}
