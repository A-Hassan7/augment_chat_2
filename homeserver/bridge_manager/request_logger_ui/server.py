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
import os
import traceback
import urllib.error
import urllib.parse
import urllib.request
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
        path = urllib.parse.urlparse(self.path).path
        if path == "/layout":
            self._handle_save_layout()
        elif path == "/replay":
            self._handle_replay()
        else:
            self._json_respond(
                404,
                {
                    "error": f"Not found: {path}",
                    "status_code": None,
                    "response_body": None,
                    "response_headers": {},
                },
            )

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

    # ── Replay ───────────────────────────────────────────────────

    def _handle_replay(self):
        """
        POST /replay — resend the raw outgoing request (possibly edited) to its
        original destination and return the live response.

        Body JSON:
            request_id       – identifies the original log row
            request_override – fully-edited outgoing request object (optional)
            auth_override    – explicit Bearer token; omit/null = auto-inject

        Response JSON (always JSON, even on server error):
            status_code, response_body, response_headers, error
        """
        try:
            self._do_replay()
        except Exception as exc:
            self._json_respond(
                500,
                {
                    "status_code": None,
                    "response_body": None,
                    "response_headers": {},
                    "error": f"Inspector error: {exc}",
                },
            )

    def _do_replay(self):
        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length)
        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError as e:
            self._json_respond(
                400,
                {
                    "error": f"Invalid JSON: {e}",
                    "status_code": None,
                    "response_body": None,
                    "response_headers": {},
                },
            )
            return

        request_id = (payload.get("request_id") or "").strip()
        req_override = payload.get("request_override")
        auth_override = (payload.get("auth_override") or "").strip()

        if not request_id:
            self._json_respond(
                400,
                {
                    "error": "request_id is required",
                    "status_code": None,
                    "response_body": None,
                    "response_headers": {},
                },
            )
            return

        log_row = db.fetch_log_by_request_id(request_id)
        if log_row is None:
            self._json_respond(
                404,
                {
                    "error": f"No log entry for request_id={request_id!r}",
                    "status_code": None,
                    "response_body": None,
                    "response_headers": {},
                },
            )
            return

        outgoing = (
            req_override
            if req_override is not None
            else (log_row.get("raw_outgoing_request") or {})
        )
        target_url = (outgoing.get("url") or "").strip()
        if not target_url:
            self._json_respond(
                400,
                {
                    "error": "Outgoing request has no 'url'. Cannot replay.",
                    "status_code": None,
                    "response_body": None,
                    "response_headers": {},
                },
            )
            return

        # Determine auth token to inject
        if auth_override:
            auth_token = auth_override
        elif log_row.get("source") == "homeserver":
            # HS → bridge: outgoing auth was bridge.as_token
            auth_token = log_row.get("bridge_as_token") or ""
        else:
            # bridge → HS: outgoing auth was the appservice AS_TOKEN
            auth_token = os.environ.get("BRIDGE_MANAGER_AS_TOKEN", "")

        method = (outgoing.get("method") or "GET").upper()

        # Rebuild headers: strip stale auth, inject fresh token
        headers = {
            k: v
            for k, v in (outgoing.get("headers") or {}).items()
            if k.lower() != "authorization"
        }
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        # Append query params
        qp = outgoing.get("query_params") or {}
        if qp:
            sep = "&" if "?" in target_url else "?"
            target_url = target_url + sep + urllib.parse.urlencode(qp)

        # Serialize body
        body_data = outgoing.get("body")
        req_bytes = (
            json.dumps(body_data).encode("utf-8") if body_data is not None else None
        )
        if req_bytes is not None and not any(
            k.lower() == "content-type" for k in headers
        ):
            headers["Content-Type"] = "application/json"

        str_headers = {str(k): str(v) for k, v in headers.items()}

        try:
            req = urllib.request.Request(
                target_url, data=req_bytes, headers=str_headers, method=method
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                status_code = resp.status
                resp_bytes = resp.read()
                resp_hdrs = dict(resp.headers)
        except urllib.error.HTTPError as exc:
            status_code = exc.code
            resp_bytes = exc.read()
            resp_hdrs = dict(exc.headers) if exc.headers else {}
        except Exception as exc:
            self._json_respond(
                200,
                {
                    "status_code": None,
                    "response_body": None,
                    "response_headers": {},
                    "error": str(exc),
                },
            )
            return

        try:
            resp_parsed = json.loads(resp_bytes.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            resp_parsed = resp_bytes.decode("utf-8", errors="replace")

        self._json_respond(
            200,
            {
                "status_code": status_code,
                "response_body": resp_parsed,
                "response_headers": resp_hdrs,
                "error": None,
            },
        )

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

    def _json_respond(self, status: int, data: dict):
        body = json.dumps(data, default=str).encode("utf-8")
        self._respond(status, "application/json; charset=utf-8", body)

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
