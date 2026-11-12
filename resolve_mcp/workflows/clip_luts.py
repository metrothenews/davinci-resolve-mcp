"""Workflow building blocks: grab a still from a clip, set/clear a clip's LUT.

These are the Resolve-side pieces the Color tab of the app is built on. They
take Resolve objects, so call them from the thread that owns the connection.

    from resolve_mcp.workflows.clip_luts import grab_still, set_clip_lut, get_clip_lut

All verified on Resolve Studio 20.2.3; they work from the Edit page.
"""

import hashlib
import os
import shutil

from resolve_mcp.connection import ResolveError

RESOLVE_LUT_ROOT = "/Library/Application Support/Blackmagic Design/DaVinci Resolve/LUT"
RESOLVE_LUTS = os.path.join(RESOLVE_LUT_ROOT, "MTN Luts")


def frame_to_timecode(frame, fps, drop_frame=False):
    """Absolute timeline frame number -> 'HH:MM:SS:FF' (or ';FF' for drop-frame)."""
    nominal = int(round(fps))
    if drop_frame:
        drop = int(round(fps * 0.066666))            # 2 for 29.97, 4 for 59.94
        per_10min = int(round(fps * 600))
        per_min = nominal * 60 - drop
        tens, rem = divmod(frame, per_10min)
        frame += drop * 9 * tens
        if rem > drop:
            frame += drop * ((rem - drop) // per_min)
    ff = frame % nominal
    ss = (frame // nominal) % 60
    mm = (frame // (nominal * 60)) % 60
    hh = frame // (nominal * 3600)
    return f"{hh:02d}:{mm:02d}:{ss:02d}{';' if drop_frame else ':'}{ff:02d}"


def still_frame(item, fps, seconds=1.0):
    """Timeline frame to grab for a clip: `seconds` in, or the middle if the clip is too short."""
    offset = int(round(fps * seconds))
    duration = item.GetDuration()
    if duration <= offset:
        offset = duration // 2
    return item.GetStart() + offset


def get_clip_lut(item, node=1):
    """LUT on the clip's node as Resolve reports it (relative path), or ''."""
    graph = item.GetNodeGraph()
    return (graph.GetLUT(node) or "") if graph else ""


def set_clip_lut(item, lut_path, node=1):
    """Set a LUT on a clip's node. lut_path '' clears it.

    lut_path must be inside one of Resolve's LUT folders (absolute, or relative
    to the LUT root). Raises ResolveError if Resolve refuses.
    """
    if lut_path and not os.path.isabs(lut_path):
        lut_path = os.path.join(RESOLVE_LUT_ROOT, lut_path)
    if not item.SetLUT(node, lut_path or ""):
        raise ResolveError(f"Resolve refused to {'set' if lut_path else 'clear'} the LUT on {item.GetName()}.")
    now = get_clip_lut(item, node)
    if bool(now) != bool(lut_path) or (lut_path and os.path.basename(now) != os.path.basename(lut_path)):
        raise ResolveError(f"LUT on {item.GetName()} is '{now}' after the change; expected '{os.path.basename(lut_path)}'.")


def grab_still(project, timeline, item, path, fps, drop_frame=False, seconds=1.0, without_lut=True):
    """Export the frame `seconds` into a clip, as the timeline shows it, to `path` (.png).

    Moves the playhead; the caller restores it. With without_lut=True, the LUTs
    on all of the clip's nodes are removed for the grab and put back afterwards,
    so the still shows the clip without them.
    """
    luts = {}
    if without_lut:
        graph = item.GetNodeGraph()
        for node in range(1, (graph.GetNumNodes() if graph else 0) + 1):
            lut = get_clip_lut(item, node)
            if lut:
                luts[node] = lut
    for node in luts:
        set_clip_lut(item, "", node)
    try:
        tc = frame_to_timecode(still_frame(item, fps, seconds), fps, drop_frame)
        if not timeline.SetCurrentTimecode(tc):
            raise ResolveError(f"Could not move the playhead to {tc}.")
        if not project.ExportCurrentFrameAsStill(path) or not os.path.exists(path):
            raise ResolveError(f"Resolve could not export a still for {item.GetName()}.")
    finally:
        for node, lut in luts.items():
            set_clip_lut(item, lut, node)


def node_tools(item, node=1):
    """Grading tools used in a node, not counting its LUT."""
    graph = item.GetNodeGraph()
    return [t for t in ((graph.GetToolsInNode(node) if graph else None) or []) if not t.startswith("LUT:")]


def _sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def resolve_copy(project, source_path, subfolder=""):
    """Path of the copy of a project LUT inside Resolve's LUT folder.

    Resolve only applies LUTs from its own folders. This makes sure the copy
    there (in MTN Luts, or MTN Luts/<subfolder>) exists and is identical to
    ours, copying it in if not, and returns it.
    """
    if not os.path.exists(source_path):
        raise ResolveError(f"LUT not found: {source_path}")
    folder = os.path.join(RESOLVE_LUTS, subfolder) if subfolder else RESOLVE_LUTS
    target = os.path.join(folder, os.path.basename(source_path))
    if not os.path.exists(target) or _sha(target) != _sha(source_path):
        os.makedirs(folder, exist_ok=True)
        shutil.copy2(source_path, target)
        project.RefreshLUTList()
    return target
