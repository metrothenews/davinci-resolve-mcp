"""Workflow: layer two LUTs into one file (first LUT, then second LUT on top).

The app uses this to give a clip one LUT that combines a color LUT (applied
first) with a look LUT (applied on top), so both can be chosen separately.

Command line (project root, with the venv because it needs numpy):
    .venv/bin/python -m resolve_mcp.workflows.layer_luts luts/NIGHT_COLOR_2_33Pt.cube luts/NIGHT_5_33Pt.cube

From Python:
    from resolve_mcp.workflows.layer_luts import layered_lut
    path = layered_lut("luts/NIGHT_COLOR_2_33Pt.cube", "luts/NIGHT_5_33Pt.cube")
"""

import argparse
import os
import sys

from resolve_mcp import cube

SEP = "__"          # <second>__<first>.cube, e.g. NIGHT_5_33Pt__NIGHT_COLOR_2_33Pt.cube
SIZE = 65           # finer than the 33-point sources, so layering loses almost nothing


def layered_name(first_path, second_path):
    stem = lambda p: os.path.splitext(os.path.basename(p))[0]
    return f"{stem(second_path)}{SEP}{stem(first_path)}.cube"


def split_name(lut_path):
    """('NIGHT_5_33Pt', 'NIGHT_COLOR_2_33Pt') for a layered file, else (stem, '')."""
    stem = os.path.splitext(os.path.basename(lut_path))[0] if lut_path else ""
    second, _, first = stem.partition(SEP)
    return second, first


def layered_lut(first_path, second_path, out_dir=None, size=SIZE, overwrite=False):
    """Write the LUT that applies `first_path` then `second_path`; return its path.

    Saved in `out_dir` (default: a 'combined' folder beside the second LUT).
    An existing file is reused unless overwrite=True.
    """
    out_dir = out_dir or os.path.join(os.path.dirname(os.path.abspath(second_path)), "combined")
    out = os.path.join(out_dir, layered_name(first_path, second_path))
    if overwrite or not os.path.exists(out):
        table = cube.layer(cube.read_cube(first_path), cube.read_cube(second_path), size)
        os.makedirs(out_dir, exist_ok=True)
        tmp = out + ".tmp"
        cube.write_cube(tmp, table, title=f"{os.path.basename(first_path)} then {os.path.basename(second_path)}")
        os.replace(tmp, out)
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description="Layer two LUTs into one: FIRST is applied first, SECOND on top.")
    p.add_argument("first")
    p.add_argument("second")
    p.add_argument("--out-dir")
    p.add_argument("--size", type=int, default=SIZE)
    p.add_argument("--overwrite", action="store_true")
    a = p.parse_args(argv)
    try:
        print(layered_lut(a.first, a.second, a.out_dir, a.size, a.overwrite))
    except (OSError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
