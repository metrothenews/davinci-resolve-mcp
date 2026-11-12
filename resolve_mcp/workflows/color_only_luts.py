"""Workflow: export each clip's COLOR-ONLY adjustments as numbered LUTs.

"Color only" means the color balance of a clip's manual adjustments (the tint
they give to neutral tones, across shadows/mids/highlights) with brightness,
contrast and saturation left out. See docs/workflows/color_only_luts.md for
how that is worked out and what it can't capture.

Use from the command line (project root, with the venv because it needs numpy):
    .venv/bin/python -m resolve_mcp.workflows.color_only_luts --prefix NIGHT_COLOR --count 8

Or from Python:
    from resolve_mcp.workflows.color_only_luts import export_color_only_luts
    results = export_color_only_luts(prefix="NIGHT_COLOR", count=8)
"""

import argparse
import os
import shutil
import sys
import tempfile

import numpy as np

from resolve_mcp import cube
from resolve_mcp.connection import ResolveError, get_resolve, get_project
from resolve_mcp.workflows import clip_luts
from resolve_mcp.workflows.export_luts import PROJECT_LUTS, RESOLVE_LUTS, clips_in_order


def color_only(adjustments, size=33):
    """Reduce a LUT of a clip's adjustments to a color-balance-only LUT.

    1. Read what the adjustments do to greys (r=g=b): three curves f_R, f_G, f_B.
    2. Their luma m(g) is the brightness/contrast part. Remove it by re-indexing
       the curves by output luma: h_c(v) = f_c(m^-1(v)). Now a grey of luma v
       comes out tinted but with the same luma v.
    3. Apply h_c to each channel on its own, as Resolve's balance controls do.

    Saturation, color boost and hue changes don't move greys, so they drop out.
    Returns a (size, size, size, 3) table.
    """
    _, f = cube.neutral_axis(adjustments)            # (n, 3)
    m = f @ cube.LUMA                                # brightness curve
    m = np.maximum.accumulate(m)                     # guard against tiny non-monotonic steps
    v, first = np.unique(m, return_index=True)       # flat (clipped) stretches collapse to one point
    tint = f[first] - v[:, None]                     # what each channel adds at luma v; sums to 0 in luma

    levels = np.linspace(0, 1, size)
    curves = np.stack([levels + np.interp(levels, v, tint[:, c]) for c in range(3)], axis=-1)   # ends hold the last tint
    curves = np.clip(curves, 0, 1)

    t = np.empty((size, size, size, 3))
    t[..., 0] = curves[:, 0][:, None, None]
    t[..., 1] = curves[:, 1][None, :, None]
    t[..., 2] = curves[:, 2][None, None, :]
    return t


def export_adjustments(resolve, item, path, size_enum="EXPORT_LUT_65PTCUBE"):
    """Export a clip's node-1 adjustments WITHOUT its node-1 LUT. Needs the Color page.

    The LUT is lifted for the export and put straight back. (Resolve applies a
    node's adjustments first and its LUT second, so this isolates the adjustments.)
    """
    lut = clip_luts.get_clip_lut(item)
    if lut:
        clip_luts.set_clip_lut(item, "")
    try:
        if not item.ExportLUT(getattr(resolve, size_enum), path) or not os.path.exists(path):
            raise ResolveError(f"Resolve could not export the grade of {item.GetName()}.")
    finally:
        if lut:
            clip_luts.set_clip_lut(item, lut)


def export_color_only_luts(prefix, count, start=1, size=33, tracks=None,
                           dest=PROJECT_LUTS, copies=(RESOLVE_LUTS,), overwrite=False, dry_run=False):
    """Export color-only LUTs for `count` clips from clip `start`, named <prefix>_<n>_<size>Pt.cube.

    Returns a list of dicts: {n, clip, file, paths, max_tint, status}; max_tint is the
    largest shift the LUT gives a grey, as a fraction (0.05 = 5%).
    """
    resolve = get_resolve()
    project = get_project(resolve)
    timeline = project.GetCurrentTimeline()
    if timeline is None:
        raise ResolveError("The current project has no open timeline.")
    chosen = clips_in_order(timeline, tracks)[start - 1:start - 1 + count]
    if len(chosen) < count:
        raise ResolveError(f"Asked for {count} clips from clip {start}, but only {len(chosen)} exist.")

    folders = [dest, *copies]
    plan = [(n, item, f"{prefix}_{n}_{size}Pt.cube") for n, item in enumerate(chosen, 1)]
    if not overwrite:
        clashes = [os.path.join(f, name) for _, _, name in plan for f in folders if os.path.exists(os.path.join(f, name))]
        if clashes:
            raise ResolveError("These files already exist (use overwrite=True / --overwrite):\n  " + "\n  ".join(clashes))

    results = []
    page = resolve.GetCurrentPage()
    tmp = tempfile.mkdtemp(prefix="color_only_")
    if not dry_run and page != "color":
        resolve.OpenPage("color")           # ExportLUT only works on the Color page
    try:
        for n, item, name in plan:
            paths = [os.path.join(f, name) for f in folders]
            row = {"n": n, "clip": item.GetName(), "file": name, "paths": paths, "max_tint": None}
            if dry_run:
                row["status"] = "would export"
            else:
                try:
                    raw = os.path.join(tmp, f"adj_{n}.cube")
                    export_adjustments(resolve, item, raw)
                    table = color_only(cube.read_cube(raw), size)
                    greys = cube.neutral_axis(table)[1]
                    row["max_tint"] = float(np.abs(greys - (greys @ cube.LUMA)[:, None]).max())
                    for f in folders:
                        os.makedirs(f, exist_ok=True)
                    cube.write_cube(paths[0], table, title=f"{prefix} {n}: color only, from {item.GetName()}")
                    for p in paths[1:]:
                        shutil.copy2(paths[0], p)
                    row["status"] = "exported"
                except (ResolveError, ValueError) as e:
                    row["status"] = f"failed: {e}"
            results.append(row)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        if not dry_run:
            project.RefreshLUTList()
            if page and page != "color":
                resolve.OpenPage(page)
    return results


def main(argv=None):
    p = argparse.ArgumentParser(description="Export clips' color-only adjustments as numbered LUTs.")
    p.add_argument("--prefix", required=True, help="Name prefix, e.g. NIGHT_COLOR")
    p.add_argument("--count", type=int, required=True, help="Number of clips")
    p.add_argument("--start", type=int, default=1, help="First clip number in timeline order (default 1)")
    p.add_argument("--size", type=int, default=33, help="Cube size (default 33)")
    p.add_argument("--tracks", type=int, nargs="+", help="Video track numbers (default: all)")
    p.add_argument("--overwrite", action="store_true", help="Replace existing files")
    p.add_argument("--dry-run", action="store_true", help="Show what would be exported")
    args = p.parse_args(argv)
    try:
        results = export_color_only_luts(args.prefix, args.count, args.start, args.size, args.tracks,
                                         overwrite=args.overwrite, dry_run=args.dry_run)
    except ResolveError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    for r in results:
        tint = f"max tint {r['max_tint'] * 100:.1f}%" if r["max_tint"] is not None else ""
        print(f"{r['n']:>2}  {r['clip']:<20} -> {r['file']:<26} {r['status']}  {tint}")
    failed = sum(r["status"].startswith("failed") for r in results)
    print(f"{len(results) - failed} ok, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
