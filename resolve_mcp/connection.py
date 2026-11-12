"""Shared connection to a running DaVinci Resolve (Studio) instance.

Every workflow imports `get_resolve()` / `get_timeline()` from here so the
API path setup lives in one place. Later, the MCP server will use the same
helpers.
"""

import os
import sys

_API = "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting"
_LIB = "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so"


class ResolveError(RuntimeError):
    pass


def get_resolve():
    """Return the Resolve scripting object, or raise ResolveError."""
    os.environ.setdefault("RESOLVE_SCRIPT_API", _API)
    os.environ.setdefault("RESOLVE_SCRIPT_LIB", _LIB)
    modules = os.path.join(os.environ["RESOLVE_SCRIPT_API"], "Modules")
    if modules not in sys.path:
        sys.path.append(modules)
    try:
        import DaVinciResolveScript as dvr
    except ImportError as e:
        raise ResolveError(f"Could not import DaVinciResolveScript: {e}")
    resolve = dvr.scriptapp("Resolve")
    if resolve is None:
        raise ResolveError(
            "Could not connect to Resolve. Is it running, and is "
            "Preferences > System > General > External scripting set to Local?"
        )
    return resolve


def get_project(resolve=None):
    resolve = resolve or get_resolve()
    project = resolve.GetProjectManager().GetCurrentProject()
    if project is None:
        raise ResolveError("No project is open in Resolve.")
    return project


def get_timeline(project=None):
    project = project or get_project()
    timeline = project.GetCurrentTimeline()
    if timeline is None:
        raise ResolveError("The current project has no open timeline.")
    return timeline


def video_items(timeline, tracks=None):
    """Yield (track_index, item) for every clip on the given video tracks.

    tracks: iterable of 1-based track numbers, or None for all video tracks.
    """
    count = timeline.GetTrackCount("video")
    indices = tracks if tracks else range(1, count + 1)
    for i in indices:
        if i < 1 or i > count:
            raise ResolveError(f"Video track {i} does not exist (timeline has {count}).")
        for item in timeline.GetItemListInTrack("video", i) or []:
            yield i, item
