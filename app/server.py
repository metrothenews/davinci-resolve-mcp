"""Local-only HTTP server between the UI and the engine.

Bound to 127.0.0.1. Requests must come from the app's own page: the Host
header has to be ours, and POSTs need the X-LA header (which browsers won't
send cross-origin without a preflight we never answer).
"""

import json
import mimetypes
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui")
HOST = "127.0.0.1"
FRAME = re.compile(r"^/frame/(\d+)/(\d+)/([0-8])/([0-8])\.jpg$")   # /frame/<generation>/<clip>/<color>/<look>.jpg


def make_server(engine, port):
    allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, code, body, ctype="application/json", cache="no-store"):
            if isinstance(body, (dict, list)):
                body = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", cache)
            self.end_headers()
            self.wfile.write(body)

        def _ok_host(self):
            if self.headers.get("Host") in allowed_hosts:
                return True
            self._send(403, {"error": "forbidden"})
            return False

        def do_GET(self):
            if not self._ok_host():
                return
            path = self.path.split("?")[0]
            if path == "/api/state":
                return self._send(200, engine.state())
            m = FRAME.match(path)
            if m:
                try:
                    f = engine.frame(int(m[1]), int(m[2]), int(m[3]), int(m[4]))
                except Exception as e:
                    return self._send(500, {"error": str(e)[:300]})
                if f:
                    with open(f, "rb") as fh:
                        return self._send(200, fh.read(), "image/jpeg", "max-age=3600")
                return self._send(404, {"error": "not ready"})
            name = "index.html" if path == "/" else path.lstrip("/")
            f = os.path.normpath(os.path.join(UI, name))
            if f.startswith(UI + os.sep) and os.path.isfile(f):
                with open(f, "rb") as fh:
                    return self._send(200, fh.read(), mimetypes.guess_type(f)[0] or "application/octet-stream")
            self._send(404, {"error": "not found"})

        def do_POST(self):
            if not self._ok_host():
                return
            if self.headers.get("X-LA") != "1":
                return self._send(403, {"error": "forbidden"})
            try:
                length = int(self.headers.get("Content-Length") or 0)
                data = json.loads(self.rfile.read(length) or b"{}")
                if self.path == "/api/load":
                    return self._send(200, {"started": engine.request_load()})
                if self.path == "/api/zoom":
                    return self._send(200, {"started": engine.request_zoom(data["zoom"])})
                if self.path == "/api/apply":
                    engine.request_apply(int(data["index"]), str(data["pass"]), int(data["slot"]), int(data["generation"]))
                    return self._send(200, {"ok": True})
                self._send(404, {"error": "not found"})
            except (ValueError, KeyError, TypeError) as e:
                self._send(400, {"error": str(e)})

    return ThreadingHTTPServer((HOST, port), Handler)
