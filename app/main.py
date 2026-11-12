"""latest avenue resolve: desktop app for a keyboard-driven first pass of color.

Run from the project root:
    .venv/bin/python -m app.main              # opens the app window
    .venv/bin/python -m app.main --no-window  # server only, UI at http://127.0.0.1:8791
"""

import argparse
import sys
import threading

from app.engine import Engine
from app.server import HOST, make_server

PORT = 8791


def main(argv=None):
    p = argparse.ArgumentParser(description="latest avenue resolve")
    p.add_argument("--no-window", action="store_true", help="Run the server only (open the UI in a browser)")
    p.add_argument("--port", type=int, default=PORT)
    args = p.parse_args(argv)

    try:
        server = make_server(Engine(), args.port)
    except OSError as e:
        print(f"Could not start on port {args.port}: {e}. Is the app already running?", file=sys.stderr)
        return 1
    url = f"http://{HOST}:{args.port}/"

    if args.no_window:
        print(f"UI at {url}  (Ctrl+C to quit)")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        return 0

    import webview
    threading.Thread(target=server.serve_forever, daemon=True, name="http").start()
    webview.create_window("latest avenue resolve", url, width=1280, height=880, min_size=(1000, 700),
                          background_color="#0a0a0a")
    webview.start()
    return 0


if __name__ == "__main__":
    sys.exit(main())
