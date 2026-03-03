"""
Minimal HTTP server for the Bridge Manager Request Logger UI.

Handles:
  GET  /            — render the log table (HTML, server-side)
  GET  /static/*    — serve CSS / JS assets
  POST /layout      — persist column layout to inspector_layout.json

No framework, no API endpoints — data is baked into the rendered HTML via
raw psycopg2 queries.
"""

from __future__ import annotations

import http.server
import json
import mimetypes
import traceback
import urllib.parse
from pathlib import Path

from . import db, layout, renderer

STATIC_DIR = Path(__file__).parent / "static"


class LogInspectorHandler(http.server.BaseHTTPRequestHandler):

    # ── Routing ──────────────────────────────────────────────────

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = parsed.query

        if path == "/" or path == "":
            self._serve_index(qs)
        elif path.startswith("/static/"):
            self._serve_static(path[len("/static/") :])
        else:
            self._respond(404, "text/plain", b"Not found")

    def do_POST(self):
        if self.path == "/layout":
            self._handle_save_layout()
        else:
            self._respond(404, "text/plain", b"Not found")

    # ── Index ────────────────────────────────────────────────────

    def _serve_index(self, query_string: str):
        params = urllib.parse.parse_qs(query_string, keep_blank_values=False)

        def first(key: str, default: str = "") -> str:
            return params.get(key, [default])[0].strip()

        filters = {
            "bridge_id": first("bridge_id"),
            "path_filter": first("path_filter"),
            "status_code": first("status_code"),
            "from_dt": first("from_dt"),
            "to_dt": first("to_dt"),
            "source": first("source"),
        }

        try:
            page = max(1, int(first("page", "1")))
        except ValueError:
            page = 1

        try:
            result = db.fetch_logs(
                **{k: v or None for k, v in filters.items()}, page=page
            )
            filter_options = db.fetch_filter_options()
            col_layout = layout.load_layout()
            theme = self._get_theme()
            html_body = renderer.render(
                result=result,
                filter_options=filter_options,
                layout=col_layout,
                filters=filters,
                theme=theme,
                query_str=query_string,
            )
            self._respond(200, "text/html; charset=utf-8", html_body.encode("utf-8"))

        except Exception:
            tb = traceback.format_exc()
            self._respond(
                500,
                "text/plain; charset=utf-8",
                f"Internal error:\n\n{tb}".encode("utf-8"),
            )

    # ── Static files ─────────────────────────────────────────────

    def _serve_static(self, filename: str):
        # Prevent path traversal
        filepath = (STATIC_DIR / filename).resolve()
        if not str(filepath).startswith(str(STATIC_DIR.resolve())):
            self._respond(403, "text/plain", b"Forbidden")
            return
        if not filepath.is_file():
            self._respond(404, "text/plain", b"Not found")
            return

        mime, _ = mimetypes.guess_type(str(filepath))
        mime = mime or "application/octet-stream"
        data = filepath.read_bytes()
        self._respond(200, mime, data)

    # ── Layout POST ──────────────────────────────────────────────

    def _handle_save_layout(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            data = json.loads(body)
            columns = data.get("columns", [])
            if not isinstance(columns, list):
                raise ValueError("columns must be a list")
            layout.save_layout(columns)
            self._respond(204, "text/plain", b"")
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            self._respond(400, "text/plain", str(e).encode())
        except Exception:
            tb = traceback.format_exc()
            self._respond(500, "text/plain", tb.encode())

    # ── Helpers ──────────────────────────────────────────────────

    def _get_theme(self) -> str:
        """Read theme from Cookie header (set by JS); default to 'light'."""
        cookie_hdr = self.headers.get("Cookie", "")
        for cookie in cookie_hdr.split(";"):
            if cookie.strip().startswith("bm_inspector_theme="):
                val = cookie.strip()[len("bm_inspector_theme=") :]
                val = val.strip().strip('"')
                if val in ("light", "dark"):
                    return val
        return "light"

    def _respond(self, status: int, content_type: str, body: bytes):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def log_message(self, fmt, *args):
        # Use a simpler single-line format instead of the default stderr dump
        print(f"  {self.address_string()} {fmt % args}")
