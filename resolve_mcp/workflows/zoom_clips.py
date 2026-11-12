"""Workflow: set the Inspector zoom on every clip in the timeline.

Use from Python:
    from resolve_mcp.workflows.zoom_clips import zoom_clips
    results = zoom_clips(zoom=1.34)

Or from the command line (run from the project root):
    python3 -m resolve_mcp.workflows.zoom_clips --zoom 1.34
    python3 -m resolve_mcp.workflows.zoom_clips --from-first
    python3 -m resolve_mcp.workflows.zoom_clips --zoom 1.0          # reset
"""

import argparse
import sys

from resolve_mcp.connection import ResolveError, get_timeline, video_items

_EPS = 1e-6


def zoom_clips(zoom=None, from_first=False, tracks=None, timeline=None, dry_run=False):
    """Set ZoomX/ZoomY on video clips in the current timeline.

    zoom:        target zoom (1.0 = 100%). Required unless from_first is True.
    from_first:  copy the zoom from the first clip on the first track used.
    tracks:      list of 1-based video track numbers; None = all video tracks.
    timeline:    a Resolve Timeline object; None = the current timeline.
    dry_run:     report what would change without changing anything.

    Returns a list of dicts: {track, clip, before, after, status}
    where status is "changed", "unchanged", "would change" or "failed".
    """
    timeline = timeline or get_timeline()
    items = list(video_items(timeline, tracks))
    if not items:
        raise ResolveError("No video clips found on the selected tracks.")

    if from_first:
        zoom = items[0][1].GetProperty("ZoomX")
    if zoom is None:
        raise ResolveError("Give a zoom value, or use from_first=True.")
    zoom = float(zoom)
    if zoom <= 0:
        raise ResolveError("Zoom must be greater than 0.")

    results = []
    for track, item in items:
        before = (item.GetProperty("ZoomX"), item.GetProperty("ZoomY"))
        row = {"track": track, "clip": item.GetName(), "before": before, "after": before}
        if abs(before[0] - zoom) < _EPS and abs(before[1] - zoom) < _EPS:
            row["status"] = "unchanged"
        elif dry_run:
            row["status"] = "would change"
        else:
            ok = item.SetProperty("ZoomX", zoom) and item.SetProperty("ZoomY", zoom)
            row["after"] = (item.GetProperty("ZoomX"), item.GetProperty("ZoomY"))
            row["status"] = "changed" if ok else "failed"
        results.append(row)
    return results


def main(argv=None):
    p = argparse.ArgumentParser(description="Set zoom on every clip in the current Resolve timeline.")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--zoom", type=float, help="Target zoom, e.g. 1.34")
    g.add_argument("--from-first", action="store_true", help="Copy zoom from the first clip")
    p.add_argument("--tracks", type=int, nargs="+", help="Video track numbers (default: all)")
    p.add_argument("--dry-run", action="store_true", help="Show changes without applying them")
    args = p.parse_args(argv)

    try:
        results = zoom_clips(args.zoom, args.from_first, args.tracks, dry_run=args.dry_run)
    except ResolveError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    for r in results:
        print(f"V{r['track']}  {r['clip']:<24} {r['before'][0]:.3f} -> {r['after'][0]:.3f}  {r['status']}")
    counts = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print(", ".join(f"{n} {s}" for s, n in counts.items()))
    return 1 if counts.get("failed") else 0


if __name__ == "__main__":
    sys.exit(main())
