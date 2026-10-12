"""CLI.

    python -m acqtracker fetch            # fetch all feeds, update web/data/deals.json
    python -m acqtracker serve [--port N] # local server with a "Refresh now" button
"""

import argparse
import functools
import http.server
import json
import os
import sys
import threading

from . import store
from .fetch import fetch_all

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_DIR = os.path.join(ROOT, "web")
DATA_PATH = os.path.join(WEB_DIR, "data", "deals.json")


def cmd_fetch(path: str) -> int:
    print("Fetching feeds...", file=sys.stderr)
    records, status = fetch_all()
    ok = sum(s["ok"] for s in status)
    total = store.update(path, records, status)
    print(f"{len(records)} items from {ok}/{len(status)} feeds; {total} deals stored in {path}", file=sys.stderr)
    return 0 if ok else 1


def cmd_serve(port: int, path: str) -> None:
    lock = threading.Lock()

    class Handler(http.server.SimpleHTTPRequestHandler):
        def do_POST(self):
            if self.path != "/api/refresh":
                self.send_error(404)
                return
            with lock:
                records, status = fetch_all()
                total = store.update(path, records, status)
            body = json.dumps({"ok": True, "count": total}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    handler = functools.partial(Handler, directory=WEB_DIR)
    srv = http.server.ThreadingHTTPServer(("0.0.0.0", port), handler)
    print(f"Serving on http://localhost:{port}", file=sys.stderr)
    srv.serve_forever()


def main() -> None:
    p = argparse.ArgumentParser(prog="acqtracker")
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("--out", default=DATA_PATH)
    s = sub.add_parser("serve")
    s.add_argument("--port", type=int, default=8000)
    s.add_argument("--out", default=DATA_PATH)
    a = p.parse_args()
    if a.cmd == "fetch":
        sys.exit(cmd_fetch(a.out))
    cmd_serve(a.port, a.out)


if __name__ == "__main__":
    main()
