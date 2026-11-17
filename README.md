# DaVinci Resolve MCP

**Programmatic control of DaVinci Resolve Studio, built as composable tools that an AI agent can call.**

Color grading a batch of clips by hand is slow and repetitive. This project wraps Resolve's scripting API in small, typed, dry-run-able workflows (LUT export and layering, color-only LUT extraction, timeline-wide zoom), then puts a fast keyboard-driven desktop app on top for the human pass. Every workflow returns structured results and can run from the CLI, from Python, or as a tool in an MCP server, so an agent like Claude can operate an editing session directly.

**Highlights**

- **A colorist's first pass in minutes.** The desktop app grabs a frame from every clip, previews 8 look LUTs × 8 color LUTs with single key presses, and applies your pick to the clip in Resolve. Combined LUTs (64 combinations) are built on demand from `.cube` math in NumPy and cached.
- **Agent-ready workflow design.** One module per workflow: plain arguments in, structured results out, `dry_run` support, user-facing errors as `ResolveError`. That's the shape an MCP tool needs.
- **Built around Resolve API quirks.** Some calls only work on certain pages (for example `ExportLUT` only works on the Color page). Workflows switch pages and restore the user's page and playhead afterwards. Every change is logged with its before and after values, so it can be undone.
- **Tested against a live session.** Design record and test results are in [docs/app-design.md](docs/app-design.md).

**Stack:** Python 3.13 · DaVinci Resolve scripting API · NumPy (3D LUT math) · pywebview + a local HTTP server for the UI · ffmpeg

**Status:** the workflows and desktop app are done. The MCP server wrapper is next, and the workflow interfaces were designed for it.

There are two parts:

- **The app** (`app/`): a desktop app with a Color tab (fast, keyboard-driven first pass of color) and a Crop tab (one click zooms every clip). Double-click `start.command`. See [docs/app.md](docs/app.md).
- **Workflows** (`resolve_mcp/workflows/`): built one at a time. Each can be used from the command line, from Python as a step in a larger workflow, and later as a tool in an MCP server so Claude can drive Resolve.

## Requirements

- DaVinci Resolve **Studio**, running, with *Preferences → System → General → External scripting using: Local*
- Python 3 (tested with 3.13)
- For the app: `pywebview` (in `.venv`, which `start.command` sets up) and ffmpeg
- For the app, `color_only_luts` and `layer_luts`: `numpy` (in `.venv`)

`resolve_mcp/connection.py` finds the Resolve scripting API on macOS automatically.

## Layout

```
app/                   the desktop app (engine, local server, UI)
modes/                 LUT sets for the app's modes (night.json: 8 look LUTs + 8 color LUTs)
resolve_mcp/
  connection.py        get_resolve / get_project / get_timeline / video_items
  cube.py              read, write and apply .cube LUTs (needs numpy)
  workflows/           one module per workflow
docs/workflows/        one doc per workflow
docs/app.md            how to run and use the app
docs/app-design.md     the app's design record and test results
luts/                  backed-up LUTs that workflows use (see luts/README.md); luts/combined/ holds layered LUTs
```

## Workflows

| Workflow | What it does | Doc |
|---|---|---|
| `zoom_clips` | Set Inspector zoom on every clip in the timeline | [docs/workflows/zoom_clips.md](docs/workflows/zoom_clips.md) |
| `export_luts` | Export clip grades as numbered LUTs (e.g. NIGHT_1_33Pt) to luts/ and Resolve | [docs/workflows/export_luts.md](docs/workflows/export_luts.md) |
| `color_only_luts` | Export only the color balance of clips' manual adjustments as numbered LUTs (e.g. NIGHT_COLOR_1_33Pt) | [docs/workflows/color_only_luts.md](docs/workflows/color_only_luts.md) |
| `layer_luts` | Layer two LUTs into one file (first LUT, then the second on top) | [docs/workflows/layer_luts.md](docs/workflows/layer_luts.md) |
| `clip_luts` | Building blocks: grab a clip's frame, set or remove a LUT on a node | [docs/app.md](docs/app.md#building-blocks) |

**Gotcha:** some API calls, such as `ExportLUT`, only work on the Color page and silently fail elsewhere. Workflows that need a page switch to it and restore the page you were on. `SetLUT` and still export work from the Edit page. Resolve only applies LUTs that are inside its own LUT folders. Inside a node, adjustments are applied before the node's LUT. The API can't add nodes, reset individual controls, or export gallery stills (`ExportStills` returns False).

## Conventions for new workflows

- One module in `resolve_mcp/workflows/`. It has a main function that takes plain arguments plus an optional `timeline`, and returns structured results.
- Support `dry_run` where the workflow changes things.
- Raise `ResolveError` for user-facing problems.
- Add a `main()` CLI, a doc in `docs/workflows/` and a row in the table above.
