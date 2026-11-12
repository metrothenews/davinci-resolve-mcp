"""Workflow: export each clip's grade as a LUT, numbered in timeline order.

Use from Python:
    from resolve_mcp.workflows.export_luts import export_luts
    results = export_luts(prefix="NIGHT", count=8)

Or from the command line (run from the project root):
    python3 -m resolve_mcp.workflows.export_luts --prefix NIGHT --count 8
    python3 -m resolve_mcp.workflows.export_luts --prefix DAY --start 9 --count 4 --size 65

Files are named "<PREFIX>_<n>_<size>Pt.cube" (e.g. NIGHT_1_33Pt.cube), with n
counting from 1. They're exported into the project's luts/ folder and copied
into Resolve's LUT folder, then Resolve's LUT list is refreshed.
"""

import argparse
import os
import shutil
import sys

from resolve_mcp.connection import ResolveError, get_resolve, get_project, video_items

PROJECT_LUTS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "luts")
RESOLVE_LUTS = "/Library/Application Support/Blackmagic Design/DaVinci Resolve/LUT/MTN Luts"

_SIZES = {17: "EXPORT_LUT_17PTCUBE", 33: "EXPORT_LUT_33PTCUBE", 65: "EXPORT_LUT_65PTCUBE"}


def clips_in_order(timeline, tracks=None):
    """Video clips sorted by timeline position (then track)."""
    items = list(video_items(timeline, tracks))
    items.sort(key=lambda ti: (ti[1].GetStart(), ti[0]))
    return [it for _, it in items]


def export_luts(prefix, count, start=1, size=33, tracks=None,
                dest=PROJECT_LUTS, copies=(RESOLVE_LUTS,), overwrite=False, dry_run=False):
    """Export LUTs for `count` clips starting at clip number `start` (1-based).

    Returns a list of dicts: {n, clip, file, paths, status}
    where status is "exported", "would export" or "failed".
    Refuses to overwrite existing files unless overwrite=True.
    """
    if size not in _SIZES:
        raise ResolveError(f"LUT size must be one of {sorted(_SIZES)}.")
    if count < 1 or start < 1:
        raise ResolveError("start and count must be 1 or more.")

    resolve = get_resolve()
    project = get_project(resolve)
    timeline = project.GetCurrentTimeline()
    if timeline is None:
        raise ResolveError("The current project has no open timeline.")

    clips = clips_in_order(timeline, tracks)
    chosen = clips[start - 1:start - 1 + count]
    if len(chosen) < count:
        raise ResolveError(f"Asked for {count} clips from clip {start}, but only {len(chosen)} exist.")

    folders = [dest, *copies]
    plan = []
    for n, item in enumerate(chosen, 1):
        name = f"{prefix}_{n}_{size}Pt.cube"
        paths = [os.path.join(f, name) for f in folders]
        plan.append((n, item, name, paths))

    if not overwrite:
        clashes = [p for *_, paths in plan for p in paths if os.path.exists(p)]
        if clashes:
            raise ResolveError("These files already exist (use overwrite=True / --overwrite):\n  " + "\n  ".join(clashes))

    # ExportLUT silently returns False unless Resolve is on the Color page,
    # so switch there for the export and switch back afterwards.
    original_page = resolve.GetCurrentPage()
    if not dry_run and original_page != "color":
        resolve.OpenPage("color")

    results = []
    try:
        for n, item, name, paths in plan:
            row = {"n": n, "clip": item.GetName(), "file": name, "paths": paths}
            if dry_run:
                row["status"] = "would export"
            else:
                for f in folders:
                    os.makedirs(f, exist_ok=True)
                ok = bool(item.ExportLUT(getattr(resolve, _SIZES[size]), paths[0])) and os.path.exists(paths[0])
                if ok:
                    for p in paths[1:]:
                        shutil.copy2(paths[0], p)
                row["status"] = "exported" if ok else "failed"
            results.append(row)
    finally:
        if not dry_run:
            project.RefreshLUTList()
            if original_page and original_page != "color":
                resolve.OpenPage(original_page)
    return results


def main(argv=None):
    p = argparse.ArgumentParser(description="Export clip grades as numbered LUTs.")
    p.add_argument("--prefix", required=True, help="Name prefix, e.g. NIGHT")
    p.add_argument("--count", type=int, required=True, help="Number of clips")
    p.add_argument("--start", type=int, default=1, help="First clip number in timeline order (default 1)")
    p.add_argument("--size", type=int, default=33, choices=sorted(_SIZES), help="Cube size (default 33)")
    p.add_argument("--tracks", type=int, nargs="+", help="Video track numbers (default: all)")
    p.add_argument("--overwrite", action="store_true", help="Replace existing files")
    p.add_argument("--dry-run", action="store_true", help="Show what would be exported")
    args = p.parse_args(argv)

    try:
        results = export_luts(args.prefix, args.count, args.start, args.size, args.tracks,
                              overwrite=args.overwrite, dry_run=args.dry_run)
    except ResolveError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    for r in results:
        print(f"{r['n']:>2}  {r['clip']:<20} -> {r['file']:<22} {r['status']}")
    failed = sum(r["status"] == "failed" for r in results)
    print(f"{len(results) - failed} ok, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
