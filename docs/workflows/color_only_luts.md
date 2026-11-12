# Workflow: export color-only LUTs

Takes the manual adjustments on a run of timeline clips and saves **only their color balance** as numbered LUTs, named `<PREFIX>_<n>_<size>Pt.cube`. Brightness, contrast and saturation are left out. These are the app's second-pass ("color") LUTs.

**File:** `resolve_mcp/workflows/color_only_luts.py` (uses `resolve_mcp/cube.py`; needs numpy, so run it with the project's `.venv`)
**Resolve API used:** `TimelineItem.ExportLUT`, `SetLUT`, `Project.RefreshLUTList`
**Tested on:** DaVinci Resolve Studio 20.2.3 (macOS), 8 clips

## Command line

```bash
.venv/bin/python -m resolve_mcp.workflows.color_only_luts --prefix NIGHT_COLOR --count 8
```

| Option | Meaning |
|---|---|
| `--prefix NAME` | Name prefix (required), e.g. `NIGHT_COLOR` |
| `--count N` | How many clips (required) |
| `--start N` | First clip in timeline order (default 1). File numbering still starts at 1. |
| `--size N` | Cube size of the saved LUT (default 33) |
| `--tracks 1 2` | Only these video tracks |
| `--overwrite` | Replace existing files (default: refuse) |
| `--dry-run` | Show the clip → file mapping; change nothing |

Each LUT is saved to `luts/` and copied to Resolve's `LUT/MTN Luts/`. The output lists each LUT's **max tint**: the biggest shift it gives a grey, which tells you how strong it is.

## From Python

```python
from resolve_mcp.workflows.color_only_luts import export_color_only_luts, color_only

results = export_color_only_luts(prefix="NIGHT_COLOR", count=8)
table = color_only(cube.read_cube("some_grade.cube"))     # the maths on its own, no Resolve needed
```

## Why it works this way

**The API can't reset individual controls.** There is no call to read or zero the saturation, contrast, color boost and so on of a node. So "reset everything except color, then export" can't be scripted. This workflow gets the same kind of result by measurement.

1. **Isolate the manual adjustments.** A node applies its adjustments first and its LUT second (measured: exporting a clip's grade matches `LUT(adjustments(x))` to 5 decimal places). So the first-pass LUT is lifted off node 1, the grade is exported as a 65-point LUT, and the first-pass LUT is put straight back. That export is the adjustments alone.
2. **Read what they do to greys.** Feeding in neutral tones from black to white gives three curves, one per channel. Their shared brightness is the brightness/contrast part; how the channels differ is the color balance.
3. **Remove the brightness part.** The curves are re-indexed by output brightness, so a grey of a given brightness comes out tinted but **exactly as bright as it went in** (checked: zero luma error).
4. **Apply per channel**, as Resolve's balance controls (wheels, temp/tint, offset, RGB curves) do.

Saturation, color boost and hue rotation don't move greys, so they drop out on their own.

## What it can't capture

- **It's a measurement, not your literal settings.** It keeps what the adjustments do to color balance across shadows, mids and highlights. It can't keep things that only affect already-colorful areas: hue rotation, hue-vs-hue curves, qualifiers or windows.
- **Clips with no first-pass LUT** (their node is all manual grade) give the color balance of the *whole* grade, not just tweaks made on top of a LUT. On 2026-11-11 this applied to C0057 and C0058 (`NIGHT_COLOR_4` and `_5`).
- **Only node 1 is read.** Clips whose grade is split over several nodes aren't handled.
- **For the literal version:** duplicate the clip's grade as a new version in Resolve, reset the non-color controls by hand, then export with the `export_luts` workflow.

## Where the color LUT goes

Because adjustments act before the LUT inside a node, a color LUT has to be applied **before** the look LUT to behave like the adjustments it came from. The app does this by layering the two into one LUT file, color first and look on top (see [layer_luts.md](layer_luts.md)), and setting that on the clip's single node.

## Exported so far

2026-11-11: `NIGHT_COLOR_1` to `_8` from C0047, C0054, C0055, C0057, C0058, C0061, C0062, C0063. Max tints were 12.8%, 11.3%, 21.9%, 7.4%, 4.9%, 5.8%, 4.9% and 4.7%. Checksums are in [luts/README.md](../../luts/README.md).
