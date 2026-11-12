# Workflow: export clip grades as numbered LUTs

Exports the color grade of a run of timeline clips as `.cube` LUTs named `<PREFIX>_<n>_<size>Pt.cube`, with n counting 1, 2, 3, ... in timeline order. Each LUT is saved to the project's `luts/` folder and copied into Resolve's `LUT/MTN Luts/` folder. Resolve's LUT list is then refreshed so the LUTs show up in the Color page right away.

**File:** `resolve_mcp/workflows/export_luts.py`
**Resolve API used:** `TimelineItem.ExportLUT(resolve.EXPORT_LUT_33PTCUBE, path)`, `Project.RefreshLUTList()`, `Resolve.OpenPage()`
**Tested on:** DaVinci Resolve Studio 20.2.3 (macOS). NIGHT_1 came out byte-identical to a LUT exported by hand from the same clip.

## Command line

Run from the project root:

```bash
python3 -m resolve_mcp.workflows.export_luts --prefix NIGHT --count 8
```

| Option | Meaning |
|---|---|
| `--prefix NAME` | Name prefix (required), e.g. `NIGHT`, `DAY` |
| `--count N` | How many clips (required) |
| `--start N` | First clip, counted in timeline order (default 1). Numbering in the file names still starts at 1. |
| `--size 17\|33\|65` | Cube size (default 33). Also used in the file name. |
| `--tracks 1 2` | Only these video tracks (default: all) |
| `--overwrite` | Replace files that already exist (default: refuse and list them) |
| `--dry-run` | Show which clip maps to which file; export nothing |

## From Python

```python
from resolve_mcp.workflows.export_luts import export_luts

results = export_luts(prefix="NIGHT", count=8)
results = export_luts(prefix="DAY", start=9, count=4, size=65, copies=())  # project folder only
```

Returns one dict per clip:
`{"n": 1, "clip": "C0047.MP4", "file": "NIGHT_1_33Pt.cube", "paths": [...], "status": "exported"}`

`status` is `exported`, `would export` or `failed`. `dest` is the main folder (default `luts/`) and `copies` is a tuple of extra folders (default Resolve's `MTN Luts`).

## Behaviour notes

- **Needs the Color page.** `ExportLUT` silently returns False on any other page. The workflow switches to Color for the export, then switches back to the page you were on.
- "Clip n" means the nth video clip by start time, across the selected tracks. If you remove or reorder clips, the numbering changes, so run `--dry-run` first to confirm the mapping.
- The LUT bakes in the clip's whole grade. Ungraded clips export an identity LUT.
- Nothing is overwritten unless `--overwrite` is passed. Before exporting, all destination paths are checked; if any clash, nothing is written.

## Exported so far

2026-11-11: NIGHT_1 to NIGHT_8 from C0047, C0051, C0052, C0053, C0054, C0055, C0057 and C0058. Checksums are in [luts/README.md](../../luts/README.md).
