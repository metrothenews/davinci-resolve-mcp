# The app: latest avenue resolve

A desktop app for fast first passes on a Resolve timeline. It has two tabs:

- **Color:** shows one frame from each clip, lets you try LUTs with single key presses, and applies the ones you pick to the clip in Resolve.
- **Crop:** one click zooms in every clip in the timeline by the same amount.

Design record and test results: [app-design.md](app-design.md).

## Start it

DaVinci Resolve Studio must be running with a project and timeline open, and *Preferences → System → General → External scripting using* set to **Local**.

Double-click **latest avenue resolve** on the Desktop. It's a small shortcut app that runs the app from this folder (`/Users/samrooker/Desktop/DaVinci Resolve MCP`); if the folder moves, update the path in the shortcut's `Contents/MacOS/launcher`. Errors go to `history/app.log`.

You can also double-click `start.command`, or from the project root:

```bash
.venv/bin/python -m app.main
```

To open the UI in a browser instead of the app window (useful for testing), run it with `--no-window` and go to `http://127.0.0.1:8791`.

## Crop tab

Press **Zoom all clips** to set the Inspector zoom of every video clip in the timeline to the value in the Zoom box (1.34 by default; Enter in the box works too). The line underneath says how many clips changed and how many were already at that zoom.

- Only zoom is changed. Position, rotation and crop edges are left alone.
- Clips already at the value are skipped, so pressing it twice is safe.
- To undo, enter the old value (1 for no zoom) and press the button again. Every run is logged to `history/crop_log.jsonl` with each clip's zoom before and after.
- If any clip changed, the Color tab grabs its frames again, because they show the old framing. That moves the playhead for a few seconds and puts it back.

It runs the `zoom_clips` workflow ([workflows/zoom_clips.md](workflows/zoom_clips.md)).

## Color tab

On start the app loads the timeline. It moves Resolve's playhead through each clip to grab the frame at 1 second, then puts the playhead and page back. Loading 24 clips takes about 10 seconds; you can start on clip 1 before it finishes.

There are two passes, switched with `tab` or the **Pass** buttons in the toolbar:

1. **Look:** the 8 first-pass LUTs (`NIGHT_1` to `NIGHT_8`).
2. **Color:** the 8 color-only LUTs (`NIGHT_COLOR_1` to `NIGHT_COLOR_8`). The preview shows the color LUT with the clip's look LUT layered on top.

| Key | Action |
|---|---|
| `1` `2` `3` `4` | Preview LUT 1–4 of the current pass |
| `7` `8` `9` `0` | Preview LUT 5–8 of the current pass |
| `⌫` Backspace | Preview with no LUT for this pass |
| `space` | Apply the previewed LUT to the clip in Resolve and go to the next clip |
| `←` `→` | Previous / next clip without applying |
| `tab` | Switch between the look pass and the color pass |

- **Space only changes Resolve if the preview differs from what's applied.** Arriving at a clip and pressing space straight away leaves it as it is.
- **Backspace then space removes that pass's LUT from the clip.**
- The top-right label shows what's applied in Resolve. The dot on a key marks the applied LUT for the current pass.
- **Load clips** re-reads the timeline. Press it after adding, removing or reordering clips; the toolbar says "Timeline changed" when it notices.
- After the last clip of the look pass, "First pass done" offers **Start color pass**.

Toolbar tags:

- **graded:** the clip has grading on it beyond these LUTs, so the preview stacks the LUTs on top of that grade.
- **has LUT: X:** node 1 has a LUT that isn't one of this mode's.

## What ends up in Resolve

Each clip keeps a **single node**, and the app sets one LUT on it (node 1):

| You chose | LUT on the clip |
|---|---|
| A look only | `MTN Luts/NIGHT_5_33Pt.cube` |
| A color only | `MTN Luts/NIGHT_COLOR_2_33Pt.cube` |
| A look and a color | `MTN Luts/Combined/NIGHT_5_33Pt__NIGHT_COLOR_2_33Pt.cube` |
| Neither | no LUT |

The combined file is the color LUT with the look LUT layered on top, so the look's brightness, contrast and saturation act on the color-balanced image. Look and color are chosen separately, which gives 8 × 8 = 64 combinations. A combined file is built the first time its combination is applied (about a second) and reused after that. Changing one pass keeps the other: switching a clip's look from 5 to 3 keeps its color.

The app replaces whatever LUT is on node 1. Manual adjustments on the node are left alone; Resolve applies them before the LUT.

## What it writes

- **In Resolve:** the LUT on node 1 of clips you press space on, and the zoom of every clip when you press Zoom all clips. Nothing else.
- **`history/color_log.jsonl`:** one line per change, with the clip, pass, the look and color slots, the LUT before and the LUT after.
- **`history/crop_log.jsonl`:** one line per Zoom all clips run, with each clip's zoom before and after.
- **`cache/`:** frames and previews, rebuilt on each load.
- **`luts/combined/`:** layered LUT files for the combinations you've applied.
- **Resolve's `LUT/MTN Luts/` folder:** if a mode LUT is missing there or differs from the copy in `luts/`, it's replaced with ours, because Resolve only applies LUTs from its own folders. Layered files go in its `Combined` subfolder.

## Modes

`modes/night.json` lists the night mode's LUT files (from `luts/`) in slot order 1–8: `luts` for the look pass and `color_luts` for the color pass. The toolbar only offers `night` for now.

## Building blocks

The Resolve-side functions are in `resolve_mcp/workflows/clip_luts.py` and can be used from other workflows:

| Function | What it does |
|---|---|
| `grab_still(project, timeline, item, path, fps)` | Export the frame 1 s into a clip as the timeline shows it. Lifts the LUTs on all nodes for the grab and restores them. Moves the playhead. |
| `set_clip_lut(item, lut_path, node=1)` | Set a LUT on a node; `""` removes it. Verifies the result. |
| `get_clip_lut(item, node=1)` | The LUT on a node, or `""`. |
| `resolve_copy(project, source_path, subfolder="")` | Make sure Resolve's LUT folder has an identical copy of a project LUT, and return its path. |
| `frame_to_timecode(frame, fps, drop_frame)` | Timeline frame number to timecode. |
