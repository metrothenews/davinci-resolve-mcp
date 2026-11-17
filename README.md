# DaVinci Resolve MCP

**Look consistency at volume: tooling that applies a defined color system across every clip in a timeline, with a person's eye making each call.**

Built for the part of production where taste matters and repetition doesn't: reviewing a batch, choosing the right look for each shot, and keeping the whole set on one visual language.

- **A look system, not one-off grades.** Eight look LUTs and eight color-balance LUTs combine into 64 consistent treatments. Color balance is separated from contrast and saturation, so a shot can be corrected without drifting off the look.
- **Fast curation.** Step through every clip, compare options with single key presses, approve with space. It's built for judging many outputs quickly and telling the right one from the nearly right one.
- **Automation underneath.** The same operations are scriptable, dry-run-able tools, designed so an AI agent can call them (MCP-ready).

Color grading a batch of clips by hand is slow and repetitive. This project wraps Resolve's scripting API in small, typed, dry-run-able workflows (LUT export and layering, color-only LUT extraction, timeline-wide zoom), then puts a fast keyboard-driven desktop app on top for the human pass. Every workflow returns structured results and can run from the CLI, from Python, or as a tool in an MCP server, so an agent like Claude can operate an editing session directly.

**Highlights**

- **A colorist's first pass in minutes.** The desktop app grabs a frame from every clip, previews 8 look LUTs × 8 color LUTs with single key presses, and applies your pick to the clip in Resolve. Combined LUTs (64 combinations) are built on demand from `.cube` math in NumPy and cached.
- **Agent-ready workflow design.** One module per workflow: plain arguments in, structured results out, `dry_run` support, user-facing errors as `ResolveError`. That's the shape an MCP tool needs.
- **Built around Resolve API quirks.** Some calls only work on certain pages (for example `ExportLUT` only works on the Color page). Workflows switch pages and restore the user's page and playhead afterwards. Every change is logged with its before and after values, so it can be undone.
- **Tested against a live session.** Design record and test results are in [docs/app-design.md](docs/app-design.md).

**Stack:** Python 3.13 · DaVinci Resolve scripting API · NumPy (3D LUT math) · pywebview + a local HTTP server for the UI · ffmpeg

**Status:** the workflows and desktop app are done. The MCP server wrapper is next, and the workflow interfaces were designed for it.

## Applications at scale

- **A tool layer for agentic post-production.** Professional editing software is a GUI that models can't operate. Wrapping it in typed, dry-run-able functions is what turns "an LLM that can talk about color" into an agent that can grade a timeline. Each workflow here maps one-to-one onto an MCP tool definition.
- **Human-in-the-loop by design.** The app's loop is propose → preview → approve with one key. That's the interaction pattern for AI-assisted creative tools: swap the fixed set of 8 LUTs for model-suggested looks and the UI, the apply step and the undo trail stay the same.
- **Preference data as a by-product.** Every choice is logged (`history/color_log.jsonl`: which clip, which look was applied). At scale that's labelled data for learning a creator's or a brand's grading taste.
- **Who needs it.** Creators and small studios who can't staff a colorist, and agencies that grade high volumes of footage to a consistent brand look.

**What it demonstrates:** API design for LLM tool use, working around an undocumented third-party API, numerical image processing (3D LUT composition), desktop UI engineering, safe and reversible automation.

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
