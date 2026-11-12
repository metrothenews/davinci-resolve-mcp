# Workflow: zoom all clips

Sets the Inspector **Zoom** (X and Y) on every video clip in the current timeline. It's the scripted version of setting Transform → Zoom by hand on each clip.

**File:** `resolve_mcp/workflows/zoom_clips.py`
**Resolve API used:** `TimelineItem.GetProperty / SetProperty("ZoomX" | "ZoomY")`
**Tested on:** DaVinci Resolve Studio 20.2.3 (macOS), 28 clips on V1

The app's Crop tab runs this workflow with one click; see [../app.md](../app.md).

## Command line

Run from the project root:

```bash
python3 -m resolve_mcp.workflows.zoom_clips --zoom 1.34
```

| Option | Meaning |
|---|---|
| `--zoom N` | Target zoom (1.0 = 100%, 1.34 = 134%) |
| `--from-first` | Copy the zoom of the first clip on the first selected track |
| `--tracks 1 2` | Only these video tracks (default: all video tracks) |
| `--dry-run` | Show what would change; change nothing |

Use either `--zoom` or `--from-first`, not both. The exit code is non-zero if any clip fails.

## From Python (for larger workflows)

```python
from resolve_mcp.workflows.zoom_clips import zoom_clips

results = zoom_clips(zoom=1.34)                 # all video tracks
results = zoom_clips(from_first=True, tracks=[1])
results = zoom_clips(zoom=1.2, timeline=tl, dry_run=True)
```

Returns one dict per clip:
`{"track": 1, "clip": "C0048.MP4", "before": (1.0, 1.0), "after": (1.34, 1.34), "status": "changed"}`

`status` is one of `changed`, `unchanged` (already at target), `would change` (dry run) or `failed`. Errors such as Resolve not running, no timeline or a bad track raise `ResolveError`.

## Behaviour notes

- X and Y are always set to the same value, which matches the gang-linked Zoom control.
- Only zoom is changed. Pan, tilt, rotation, crop and keyframes are left alone.
- Clips already at the target are skipped, so running it twice is safe.
- **Undo:** API changes don't reliably show up in Resolve's undo history. To revert, run again with the old value, e.g. `--zoom 1.0`. Every run also prints each clip's `before` value.
- Zoom keyframes, if any, aren't touched. The API only sets the static value.
