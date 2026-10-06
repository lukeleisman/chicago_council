"""Local helper for measuring label boxes in the browser: accepts POST /<name> from the dashboard
served at http://localhost:8765 and writes the body to OUT_DIR/<name>. Used with
scripts/measure_label_boxes.js (2026-10-05). Listens on 127.0.0.1:8766 only.

Usage:
  python scripts/label_measure_receiver.py <out_dir>
"""

import re
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

PORT = 8766
PAGE_ORIGIN = "http://localhost:8765"
OUT_DIR = Path(sys.argv[1])


class Handler(BaseHTTPRequestHandler):
    def cors(self):
        self.send_header("Access-Control-Allow-Origin", PAGE_ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self.cors()
        self.end_headers()

    def do_POST(self):
        # File name from the path, letters/digits/._- only.
        name = re.sub(r"[^A-Za-z0-9_.-]", "", self.path.strip("/")) or "post.json"
        body = self.rfile.read(int(self.headers["Content-Length"]))
        (OUT_DIR / name).write_bytes(body)
        self.send_response(200)
        self.cors()
        self.end_headers()
        self.wfile.write(b"saved")


HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
