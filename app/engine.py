"""The app's engine: one thread that owns the Resolve connection, plus preview rendering.

Everything that touches the Resolve API runs on the single Resolve thread
(the API isn't thread-safe). Other threads (the HTTP server) only read
`state()`, queue jobs and render preview frames with ffmpeg.

Two passes, each with 8 LUTs per mode:
  look   first pass, the NIGHT_n LUTs
  color  second pass, the NIGHT_COLOR_n LUTs (color balance only)
The two are chosen separately and layered into ONE LUT on the clip's node 1:
color first, look on top (the order manual adjustments and a LUT have inside a node).
Only a look, or only a color, uses that LUT file as it is; both together use a
layered file built on demand in luts/combined/ (resolve_mcp/workflows/layer_luts.py).
"""

import itertools
import json
import os
import queue
import shutil
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from resolve_mcp.connection import ResolveError, get_resolve, video_items
from resolve_mcp.workflows import clip_luts
from resolve_mcp.workflows.layer_luts import layered_lut, split_name
from resolve_mcp.workflows.zoom_clips import zoom_clips

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LUTS = os.path.join(ROOT, "luts")
MODES = os.path.join(ROOT, "modes")
CACHE = os.path.join(ROOT, "cache")
HISTORY = os.path.join(ROOT, "history")
COMBINED = "Combined"     # subfolder of Resolve's MTN Luts for layered LUTs

PREVIEW_WIDTH = 1200
POLL_SECONDS = 2
PRIO_APPLY, PRIO_LOAD, PRIO_POLL = 0, 1, 2
PASSES = ("look", "color")


def _ffmpeg():
    for p in (shutil.which("ffmpeg"), "/usr/local/bin/ffmpeg", "/opt/homebrew/bin/ffmpeg"):
        if p and os.path.exists(p):
            return p
    return None


def _stem(path):
    return os.path.splitext(os.path.basename(path))[0] if path else ""


def load_mode(name):
    with open(os.path.join(MODES, f"{name}.json")) as f:
        mode = json.load(f)
    mode = {"name": mode["name"], "look": mode["luts"], "color": mode.get("color_luts", [])}
    if len(mode["look"]) != 8 or len(mode["color"]) not in (0, 8):
        raise ValueError(f"Mode '{name}' must list exactly 8 LUTs per pass.")
    return mode


class Engine:
    def __init__(self, mode="night"):
        self._lock = threading.Lock()
        self._jobs = queue.PriorityQueue()
        self._seq = itertools.count()
        self._pool = ThreadPoolExecutor(max_workers=4)
        self._ffmpeg = _ffmpeg()
        self._mode = load_mode(mode)
        self._slots = {k: {_stem(l): n for n, l in enumerate(self._mode[k], 1)} for k in PASSES}
        self._items = []            # TimelineItem objects; Resolve thread only
        self._auto_loaded = False
        self._status = {"connected": False, "message": "Connecting to Resolve..."}
        self._loading = {"active": False, "done": 0, "total": 0, "error": None}
        self._clips = []
        self._generation = 0
        self._loaded_timeline = None   # (timeline uid, clip count) at load time
        self._frame_locks = {}
        self._crop = {"active": False, "result": None, "error": None}
        self._boot = int(time.time())   # lets the UI tell this run's frames from a cached earlier run's
        self._submit(PRIO_POLL, self._poll)
        threading.Thread(target=self._resolve_loop, daemon=True, name="resolve").start()

    # ---------- called from any thread ----------

    def state(self):
        with self._lock:
            return {
                "status": dict(self._status),
                "loading": dict(self._loading),
                "mode": {"name": self._mode["name"], "look": [_stem(l) for l in self._mode["look"]],
                         "color": [_stem(l) for l in self._mode["color"]]},
                "boot": self._boot,
                "crop": dict(self._crop),
                "generation": self._generation,
                "clips": [dict(c) for c in self._clips],
            }

    def request_load(self):
        with self._lock:
            if self._loading["active"]:
                return False
            self._loading = {"active": True, "done": 0, "total": 0, "error": None}
        self._submit(PRIO_LOAD, self._load_start)
        return True

    def request_zoom(self, zoom):
        """Queue 'set every clip in the timeline to this zoom' (the Crop tab's one click)."""
        zoom = float(zoom)
        if not 0.1 <= zoom <= 10:
            raise ValueError("Zoom must be between 0.1 and 10.")
        with self._lock:
            if self._crop["active"]:
                return False
            self._crop = {"active": True, "result": None, "error": None}
        self._submit(PRIO_APPLY, lambda: self._zoom(zoom))
        return True

    def request_apply(self, index, kind, slot, generation):
        """Queue 'set LUT slot (1-8) of pass `kind` on clip index'; slot 0 removes that LUT."""
        if kind not in PASSES or not 0 <= slot <= 8 or (slot and not self._mode[kind]):
            raise ValueError("bad pass or slot")
        with self._lock:
            if generation != self._generation or not 0 <= index < len(self._clips):
                raise ValueError("Clip list is out of date. Load clips again.")
            self._clips[index]["pending"] = True
            self._clips[index]["error"] = None
        self._submit(PRIO_APPLY, lambda: self._apply(index, kind, slot, generation))

    def frame(self, generation, index, color, look):
        """Path of the preview of clip `index` with color LUT `color` and look LUT `look` (0 = none).

        Rendered on first request and cached. Returns None if the clip's still isn't there yet.
        """
        folder = os.path.join(CACHE, str(generation))
        still = os.path.join(folder, f"{index:04d}_still.png")
        out = os.path.join(folder, f"{index:04d}_c{color}_l{look}.jpg")
        if os.path.exists(out):
            return out
        if not os.path.exists(still) or not self._ffmpeg or (color and not self._mode["color"]):
            return None
        with self._lock:
            lock = self._frame_locks.setdefault(out, threading.Lock())
        with lock:
            if not os.path.exists(out):
                chain = []
                if color:
                    chain.append(f"lut3d={self._mode['color'][color - 1]}")   # same order as the nodes: color, then look
                if look:
                    chain.append(f"lut3d={self._mode['look'][look - 1]}")
                chain.append(f"scale={PREVIEW_WIDTH}:-2")
                tmp = out + ".tmp.jpg"
                # cwd=LUTS so the filter can name LUT files without path escaping
                subprocess.run([self._ffmpeg, "-v", "error", "-y", "-i", still, "-vf", ",".join(chain), "-q:v", "3", tmp],
                               cwd=LUTS, check=True, capture_output=True, text=True, timeout=60)
                os.replace(tmp, out)
        return out

    # ---------- Resolve thread ----------

    def _submit(self, prio, fn):
        self._jobs.put((prio, next(self._seq), fn))

    def _resolve_loop(self):
        while True:
            try:
                _, _, job = self._jobs.get(timeout=POLL_SECONDS)
            except queue.Empty:
                job = self._poll
            try:
                job()
            except Exception as e:  # keep the thread alive whatever happens
                with self._lock:
                    self._status["message"] = f"Error: {e}"

    def _session(self):
        resolve = get_resolve()
        project = resolve.GetProjectManager().GetCurrentProject()
        if project is None:
            raise ResolveError("No project is open in Resolve.")
        timeline = project.GetCurrentTimeline()
        if timeline is None:
            raise ResolveError("Open a timeline in Resolve.")
        return resolve, project, timeline

    def _poll(self):
        try:
            resolve, project, timeline = self._session()
        except ResolveError as e:
            connected = "No project" in str(e) or "timeline" in str(e)
            with self._lock:
                self._status = {"connected": connected, "message": str(e)}
            return
        count = sum(1 for _ in video_items(timeline))
        key = (timeline.GetUniqueId(), count)
        with self._lock:
            self._status = {
                "connected": True, "message": "",
                "product": resolve.GetProductName(),
                "version": ".".join(resolve.GetVersionString().split(".")[:3]),
                "project": project.GetName(), "timeline": timeline.GetName(), "clip_count": count,
                "stale": self._loaded_timeline is not None and key != self._loaded_timeline,
            }
            auto = not self._auto_loaded and not self._loading["active"]
        if auto:
            self._auto_loaded = True
            self.request_load()

    def _read_clip(self, item):
        """What's on a clip now: which look/color slot its node-1 LUT holds, and other grading."""
        graph = item.GetNodeGraph()
        nodes = graph.GetNumNodes() if graph else 0
        lut = clip_luts.get_clip_lut(item, 1) if nodes else ""
        a, b = split_name(lut)                       # layered: (look, color); single: (stem, "")
        look, color = self._slots["look"].get(a), self._slots["color"].get(b)
        if not b and not look:
            color = self._slots["color"].get(a)      # a color LUT on its own
        known = bool(look or color) and (not b or bool(look and color))
        return {
            "nodes": nodes, "look": look, "color": color,
            "other_lut": "" if (known or not lut) else _stem(lut),
            "graded": any(clip_luts.node_tools(item, n) for n in range(1, nodes + 1)) or nodes > 1,
        }

    def _load_start(self):
        """Read the clip list, then grab stills one clip per job so applies can cut in."""
        try:
            resolve, project, timeline = self._session()
            if not self._ffmpeg:
                raise ResolveError("ffmpeg was not found. Install it (brew install ffmpeg) and retry.")
            items = [it for _, it in sorted(video_items(timeline), key=lambda ti: (ti[1].GetStart(), ti[0]))]
            if not items:
                raise ResolveError("The timeline has no video clips.")
            fps = float(timeline.GetSetting("timelineFrameRate"))
            drop = str(timeline.GetSetting("timelineDropFrameTimecode")) == "1"

            clips = []
            for i, it in enumerate(items):
                clips.append({"index": i, "name": it.GetName(), "seconds": round(it.GetDuration() / fps, 2),
                              **self._read_clip(it), "still": False, "pending": False, "error": None})

            with self._lock:
                self._generation += 1
                gen = self._generation
                self._items = items
                self._clips = clips
                self._frame_locks = {}
                self._loading.update(total=len(items), done=0)
                self._loaded_timeline = (timeline.GetUniqueId(), len(items))
                self._status["stale"] = False
            shutil.rmtree(CACHE, ignore_errors=True)
            os.makedirs(os.path.join(CACHE, str(gen)), exist_ok=True)

            ctx = {"gen": gen, "project": project, "timeline": timeline, "resolve": resolve, "fps": fps, "drop": drop,
                   "page": resolve.GetCurrentPage(), "tc": timeline.GetCurrentTimecode()}
            self._submit(PRIO_LOAD, lambda: self._load_step(ctx, 0))
        except Exception as e:
            with self._lock:
                self._loading.update(active=False, error=str(e))

    def _load_step(self, ctx, i):
        gen = ctx["gen"]
        if i >= len(self._items):
            ctx["timeline"].SetCurrentTimecode(ctx["tc"])          # put the playhead back
            if ctx["page"] and ctx["resolve"].GetCurrentPage() != ctx["page"]:
                ctx["resolve"].OpenPage(ctx["page"])
            with self._lock:
                self._loading["active"] = False
            return
        still = os.path.join(CACHE, str(gen), f"{i:04d}_still.png")
        try:
            clip_luts.grab_still(ctx["project"], ctx["timeline"], self._items[i], still + ".tmp.png", ctx["fps"], ctx["drop"])
            os.replace(still + ".tmp.png", still)
            with self._lock:
                self._clips[i]["still"] = True
                color = self._clips[i]["color"] or 0
            for look in range(9):                                  # warm the first-pass previews
                self._pool.submit(self._warm, gen, i, color, look)
        except Exception as e:
            with self._lock:
                self._clips[i]["error"] = str(e)
        with self._lock:
            self._loading["done"] = i + 1
        self._submit(PRIO_LOAD, lambda: self._load_step(ctx, i + 1))

    def _warm(self, gen, index, color, look):
        try:
            self.frame(gen, index, color, look)
        except Exception as e:
            msg = (getattr(e, "stderr", "") or str(e)).strip()[:200]
            with self._lock:
                if gen == self._generation:
                    self._clips[index]["error"] = f"Preview failed: {msg}"

    def _zoom(self, zoom):
        try:
            _, project, timeline = self._session()
            rows = zoom_clips(zoom=zoom, timeline=timeline)
            count = lambda status: sum(r["status"] == status for r in rows)
            result = {"zoom": zoom, "total": len(rows), "changed": count("changed"),
                      "unchanged": count("unchanged"), "failed": count("failed")}
            os.makedirs(HISTORY, exist_ok=True)
            with open(os.path.join(HISTORY, "crop_log.jsonl"), "a") as f:
                f.write(json.dumps({
                    "time": time.strftime("%Y-%m-%d %H:%M:%S"), "project": project.GetName(), "timeline": timeline.GetName(),
                    "zoom": zoom, "clips": [{"clip": r["clip"], "track": r["track"], "before": r["before"][0],
                                             "after": r["after"][0], "status": r["status"]} for r in rows],
                }) + "\n")
            with self._lock:
                self._crop = {"active": False, "result": result, "error": None}
            if result["changed"]:
                self.request_load()      # the Color tab's frames show the old framing; grab them again
        except Exception as e:
            with self._lock:
                self._crop = {"active": False, "result": None, "error": str(e)}

    def _lut_for(self, project, look, color):
        """The LUT file inside Resolve's folder for a look/color choice ('' for neither)."""
        look_file = os.path.join(LUTS, self._mode["look"][look - 1]) if look else ""
        color_file = os.path.join(LUTS, self._mode["color"][color - 1]) if color else ""
        if look and color:
            layered = layered_lut(color_file, look_file, os.path.join(LUTS, "combined"))   # color first, look on top
            return clip_luts.resolve_copy(project, layered, COMBINED)
        if look or color:
            return clip_luts.resolve_copy(project, look_file or color_file)
        return ""

    def _apply(self, index, kind, slot, generation):
        try:
            if generation != self._generation:
                raise ResolveError("Clip list is out of date. Load clips again.")
            _, project, timeline = self._session()
            item = self._items[index]
            now = self._read_clip(item)                      # the other pass's choice comes from the clip itself
            look = slot if kind == "look" else (now["look"] or 0)
            color = slot if kind == "color" else (now["color"] or 0)
            before = clip_luts.get_clip_lut(item, 1)
            after = self._lut_for(project, look, color)
            clip_luts.set_clip_lut(item, after, 1)
            with self._lock:
                self._clips[index].update(self._read_clip(item), pending=False, error=None)
            os.makedirs(HISTORY, exist_ok=True)
            with open(os.path.join(HISTORY, "color_log.jsonl"), "a") as f:
                f.write(json.dumps({
                    "time": time.strftime("%Y-%m-%d %H:%M:%S"), "project": project.GetName(), "timeline": timeline.GetName(),
                    "clip": item.GetName(), "clip_id": item.GetUniqueId(), "pass": kind, "look": look, "color": color, "node": 1,
                    "before": before, "after": os.path.relpath(after, clip_luts.RESOLVE_LUT_ROOT) if after else "",
                }) + "\n")
        except Exception as e:
            with self._lock:
                if index < len(self._clips):
                    self._clips[index].update(pending=False, error=str(e))
