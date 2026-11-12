# Desktop app: design

A standalone macOS app that connects to a live DaVinci Resolve Studio session. Version 1 has **one tab, Color**: a keyboard-driven first pass that puts a LUT on every clip in the timeline. The interface matches latestavenue.com.

**Status:** the Color tab is **built and tested** (2026-11-11). How to run and use it: [app.md](app.md). This file is the design record.
**Mockup:** `docs/app-design/mockup.html` is the original sketch, with real frames from clips 9–14 of Timeline 1.

---

## 1. The Color tab

### What it's for

You load a new group of clips into the timeline, then step through them one at a time:

1. Look at the frame.
2. Tap a key to try each LUT.
3. Press space on the one you like.

When you reach the end, every clip has a LUT applied in Resolve and you carry on with manual adjustment there.

### Layout (top to bottom)

1. **Toolbar.** The "latest avenue" wordmark and `resolve` pill, then the **Color** tab (the only one), then **Mode** (`night`, the only mode for now). After that: clip position and name (e.g. `9 / 24  C0059.MP4`), a **Load clips** button, and the Resolve connection pill.
2. **Preview.** It fills the middle of the window and shows the current clip's frame at 1 s, framed as it is in the timeline. Labels show the LUT being previewed (top-left, e.g. `NIGHT 3` or `no LUT`) and the LUT already applied in Resolve, if there is one (top-right).
3. **LUT keys.** Eight square buttons below the preview, in two groups of four, laid out like the keyboard. Each shows its key and its LUT name. The one being previewed is highlighted. Clicking a button does the same as pressing its key. A line of key hints sits underneath.

### Keys

The keys follow a natural hand position: left hand on 1–4, right hand on 7–0, thumb on space. The LUT names stay 1–8.

| Key | Action |
|---|---|
| `1` `2` `3` `4` | Preview NIGHT 1, 2, 3, 4 |
| `7` `8` `9` `0` | Preview NIGHT 5, 6, 7, 8 |
| `⌫` Backspace | Preview with no LUT |
| `space` | **Apply** the previewed LUT to this clip in Resolve, then go to the next clip. With no LUT previewed, the clip is left as it is. |
| `←` `→` | Previous / next clip without applying anything |

After the last clip, a "First pass done" card says how many clips got a LUT. It offers "Back to first clip" or "Load clips".

### Modes

A mode is a named set of 8 LUTs, stored in `modes/<mode>.json`:

```json
{"name": "night", "luts": ["NIGHT_1_33Pt.cube", "NIGHT_2_33Pt.cube", "...", "NIGHT_8_33Pt.cube"]}
```

Key → slot mapping is the same for every mode. Adding a mode means exporting its LUTs (with the `export_luts` workflow) and adding a JSON file. No code changes.

## 2. How it works

### Load clips

Press **Load clips**, or let it happen automatically when the app starts or the timeline changes.

1. Read the video clips in timeline order.
2. For each clip, move the playhead to **1 s into the clip** (or the middle, for clips 1 s or shorter) and call `Project.ExportCurrentFrameAsStill()`. This gives the frame exactly as the timeline shows it: 1440×1080, with its zoom and scaling. **Tested:** 0.37 s per clip, and it works on the Edit page.
3. Put the playhead and page back where you had them.

Stills are cached per clip in `cache/`. The first clip's preview shows as soon as its still is ready, and the rest load in the background.

### Previews

Each still is run through the mode's 8 LUTs with ffmpeg's `lut3d` filter at display size.

- **Tested:** about 0.15 s per preview. All 8 for a clip are ready in about a second, so key presses swap images instantly.
- The current clip is done first, then the next few.

This should match Resolve because the project is plain DaVinci YRGB with no color management, so a node LUT is a straight per-pixel transform of the frame.

### Apply (space)

- Calls `TimelineItem.SetLUT(1, path)`, which sets the LUT on node 1.
- Resolve only accepts LUTs from its own LUT folders. So it uses the identical copy in `…/LUT/MTN Luts/`, after checking it matches the checksum of our copy in `luts/`.
- It runs in the background, so you never wait. If it fails, the clip is flagged and the error shown.
- If node 1 already has a LUT, it's replaced. When you arrive at a clip that already has one, the preview starts on that LUT.

### History

Every apply is logged (clip, previous LUT, new LUT) so a pass can be reverted later.

## 3. What testing showed

- **`SetLUT` works from the Edit page.** No page switching is needed, unlike `ExportLUT`.
- **A LUT can be removed** with `SetLUT(1, "")`. Backspace then space removes a clip's LUT, and revert is possible later.
- **Resolve refuses LUTs outside its own LUT folders.** The app applies the identical copy in `MTN Luts`; if that copy is missing or differs from ours in `luts/`, it's replaced with ours first.
- **Previews match Resolve.** An ffmpeg preview against Resolve's own render of the same frame and LUT measured 50.7 dB PSNR, which is under one brightness level of difference per pixel.
- **Loading 24 clips takes about 10 s** for the frames, and the 216 previews finish a few seconds later.
- **Clips with a LUT already on node 1.** The LUT is lifted for the frame grab and put straight back, so "no LUT" really shows no LUT.
- **Already-graded clips.** Their frame includes the existing grade, so a LUT preview stacks on top. The toolbar marks them "already graded".
- **Clips 1 s or shorter** use their middle frame.

## 4. Architecture

```
app window (pywebview → native macOS WKWebView)
  UI: HTML + Tailwind with latest avenue's styles
    │ HTTP on 127.0.0.1:8791 only (requests from other sites are refused)
  app/server.py    serves the UI, preview frames and a small JSON API
  app/engine.py    ONE thread owns the Resolve connection (API isn't thread-safe);
                   a small pool runs ffmpeg for the previews
  resolve_mcp/workflows/clip_luts.py   grab a still, set/clear a clip's LUT
  resolve_mcp/     existing connection + workflows (unchanged)
    │ DaVinciResolveScript
DaVinci Resolve Studio (running)
```

**Change from the first design:** the UI talks to Python over a localhost-only HTTP server, not pywebview's JS bridge. That lets the same UI be opened and tested in a browser (`--no-window`).

**Why pywebview:** the site's look depends on CSS frosted-glass blur, and a web view renders it exactly. Qt and Tk can't. It's still a real app window; it packages as a `.app` later.

**Polling:** Resolve has no events. The worker checks the version, project, timeline and clip count every 2 s to keep the connection pill current and to notice when the timeline changes.

**Dependencies:** `pywebview`, installed in the project's `.venv`, and ffmpeg (already installed).

## 5. Look

The look is copied from `Intellijend Clone/src/index.css`, `tailwind.config.js` and `components/ui/Button.jsx`:

| Element | Spec |
|---|---|
| Background | `#0a0a0a` with a blue-violet glow at the top (`rgba(130,115,255,.14)`) and faint cyan bottom-right (`rgba(60,170,255,.06)`) |
| Panels, LUT keys | `.glass`: `rounded-xl border-gray-700/50 bg-gray-900/30 backdrop-blur-md`, inset top highlight |
| Toolbar | `.glass-bar`: `border-white/10 bg-black/30 backdrop-blur-md`, `h-16` |
| Active key / tab | `bg-white/20 border-white/40` / `bg-white/10` |
| Buttons | Pill-shaped secondary glass (`bg-white/5 border-white/15`) |
| Text | White; secondary `white/40–70` |
| Type | Inter; bold, tight tracking |
| Motion | None |

## 6. Files

```
app/main.py        starts the engine, the server and the window
app/engine.py      Resolve thread, clip loading, previews, apply, log
app/server.py      localhost HTTP server
app/ui/            index.html, app.js, styles.css
modes/night.json   the 8 LUTs of the night mode
cache/             stills + previews, rebuilt on every load (safe to delete)
history/color_log.jsonl   every LUT applied or removed, with the LUT before it
start.command      double-click launcher
```

## 7. Not built yet

- A Revert button. The log already has what it needs.
- More modes. The engine reads `modes/<name>.json`, but the toolbar only offers `night`.
- Packaging as a `.app`.

## Later

These were in the first draft of this design and are parked until the Color tab works:

- More tabs: Workflows (zoom, LUT export), Recipes (chained workflows), LUTs and History with Revert.
- Running the same workflows from Claude through an MCP server.
