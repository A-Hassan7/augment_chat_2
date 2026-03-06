"""
Renders the index.html template by substituting data markers.

Uses simple {{MARKER}} replacement (not string.Template) so there is no
conflict with CSS variables, JS template literals, or any other '$' usage
inside the HTML/JS/CSS files.
"""

from __future__ import annotations

import html
import json
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Any

TEMPLATE_PATH = Path(__file__).parent / "templates" / "index.html"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _esc(value: Any) -> str:
    """HTML-escape a string value; return empty string for None."""
    if value is None:
        return ""
    return html.escape(str(value))


def _json_attr(value: Any) -> str:
    """Serialise value to compact JSON suitable for an HTML data-* attribute."""
    if value is None:
        return ""
    try:
        return html.escape(json.dumps(value, default=str), quote=True)
    except (TypeError, ValueError):
        return html.escape(str(value), quote=True)


def _fmt_timestamp(ts: Any) -> str:
    if ts is None:
        return ""
    if isinstance(ts, datetime):
        return ts.strftime("%Y-%m-%d %H:%M:%S")
    return str(ts)


# ---------------------------------------------------------------------------
# Row / header builders
# ---------------------------------------------------------------------------


def _build_headers(visible_cols: list[dict]) -> str:
    cells = "".join(
        f'<th data-key="{_esc(c["key"])}">{_esc(c["label"])}</th>'
        for c in visible_cols
        if c["visible"]
    )
    return cells


def _cell_value(row: dict, key: str) -> str:
    if key == "timestamp":
        return _fmt_timestamp(row.get("timestamp"))
    if key == "query_params":
        v = row.get("query_params")
        if v:
            return json.dumps(v, default=str)
        return ""
    return str(row.get(key) or "")


def _build_rows(rows: list[dict], visible_cols: list[dict]) -> str:
    cols = [c for c in visible_cols if c["visible"]]
    parts: list[str] = []
    for row in rows:
        sc = row.get("status_code")
        if sc is None:
            css_class = "row-unknown"
        elif int(sc) < 400:
            css_class = "row-success"
        else:
            css_class = "row-fail"

        raw_in = _json_attr(row.get("raw_incoming_request"))
        raw_out = _json_attr(row.get("raw_outgoing_request"))
        resp = _json_attr(row.get("response_body"))
        req_id = _esc(row.get("request_id", ""))

        cells = "".join(f"<td>{_esc(_cell_value(row, c['key']))}</td>" for c in cols)
        parts.append(
            f'<tr class="{css_class}" '
            f'data-request-id="{req_id}" '
            f'data-raw-in="{raw_in}" '
            f'data-raw-out="{raw_out}" '
            f'data-response="{resp}">'
            f"{cells}"
            f"</tr>"
        )
    return (
        "\n".join(parts)
        if parts
        else '<tr><td colspan="99" class="no-rows">No results found.</td></tr>'
    )


# ---------------------------------------------------------------------------
# Filter options
# ---------------------------------------------------------------------------


def _bridge_options(bridges: list[dict], selected: str) -> str:
    opts = ['<option value="">All bridges</option>']
    for b in bridges:
        sel = "selected" if str(b["id"]) == selected else ""
        opts.append(f'<option value="{b["id"]}" {sel}>{_esc(b["name"])}</option>')
    return "\n".join(opts)


def _status_options(codes: list[int], selected: str) -> str:
    opts = ['<option value="">All statuses</option>']
    for code in codes:
        sel = "selected" if str(code) == selected else ""
        opts.append(f'<option value="{code}" {sel}>{code}</option>')
    return "\n".join(opts)


def _source_options(selected: str) -> str:
    opts = ['<option value="">All sources</option>']
    for s in ("homeserver", "bridge"):
        sel = "selected" if s == selected else ""
        opts.append(f'<option value="{s}" {sel}>{s}</option>')
    return "\n".join(opts)


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


def _pagination(page: int, page_count: int, query_str: str) -> str:
    """Build prev/page-numbers/next links."""

    def page_url(p: int) -> str:
        params = dict(urllib.parse.parse_qsl(query_str))
        params["page"] = str(p)
        return "/?" + urllib.parse.urlencode(params)

    parts: list[str] = []
    if page > 1:
        parts.append(
            f'<a class="page-link" href="{page_url(page - 1)}">&#8592; Prev</a>'
        )

    # Show at most 7 page numbers centered on current page
    lo = max(1, page - 3)
    hi = min(page_count, page + 3)
    if lo > 1:
        parts.append(f'<a class="page-link" href="{page_url(1)}">1</a>')
        if lo > 2:
            parts.append('<span class="page-gap">…</span>')
    for p in range(lo, hi + 1):
        cls = "page-link page-current" if p == page else "page-link"
        parts.append(f'<a class="{cls}" href="{page_url(p)}">{p}</a>')
    if hi < page_count:
        if hi < page_count - 1:
            parts.append('<span class="page-gap">…</span>')
        parts.append(
            f'<a class="page-link" href="{page_url(page_count)}">{page_count}</a>'
        )

    if page < page_count:
        parts.append(
            f'<a class="page-link" href="{page_url(page + 1)}">Next &#8594;</a>'
        )

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Column manager
# ---------------------------------------------------------------------------


def _column_manager_items(all_cols: list[dict]) -> str:
    items: list[str] = []
    for col in all_cols:
        checked = "checked" if col["visible"] else ""
        items.append(
            f'<li class="col-item" data-key="{_esc(col["key"])}">'
            f'  <span class="drag-handle">⠿</span>'
            f"  <label>"
            f'    <input type="checkbox" {checked} data-key="{_esc(col["key"])}">'
            f'    {_esc(col["label"])}'
            f"  </label>"
            f"</li>"
        )
    return "\n".join(items)


# ---------------------------------------------------------------------------
# Main render entry point
# ---------------------------------------------------------------------------


def render(
    result: dict,
    filter_options: dict,
    layout: list[dict],
    filters: dict,
    theme: str,
    query_str: str,
) -> str:
    """
    Render the full HTML page.

    Args:
        result:         dict from db.fetch_logs()
        filter_options: dict from db.fetch_filter_options()
        layout:         list of column dicts from layout.load_layout()
        filters:        raw filter dict (bridge_id, path, status_code, from_dt, to_dt, source)
        theme:          "light" or "dark"
        query_str:      current URL query string (for pagination links)
    """
    template = TEMPLATE_PATH.read_text(encoding="utf-8")

    visible_cols = [c for c in layout if c["visible"]]

    substitutions = {
        "{{THEME}}": theme,
        "{{BRIDGE_OPTIONS}}": _bridge_options(
            filter_options["bridges"], filters.get("bridge_id", "")
        ),
        "{{STATUS_OPTIONS}}": _status_options(
            filter_options["status_codes"], filters.get("status_code", "")
        ),
        "{{SOURCE_OPTIONS}}": _source_options(filters.get("source", "")),
        "{{FILTER_PATH}}": _esc(filters.get("path_filter", "")),
        "{{FILTER_FROM}}": _esc(filters.get("from_dt", "")),
        "{{FILTER_TO}}": _esc(filters.get("to_dt", "")),
        "{{TABLE_HEADERS}}": _build_headers(layout),
        "{{TABLE_ROWS}}": _build_rows(result["rows"], layout),
        "{{TOTAL}}": str(result["total"]),
        "{{TOTAL_PLURAL}}": "" if result["total"] == 1 else "s",
        "{{PAGE}}": str(result["page"]),
        "{{PAGE_COUNT}}": str(result["page_count"]),
        "{{PAGINATION}}": _pagination(result["page"], result["page_count"], query_str),
        "{{COLUMN_MANAGER_ITEMS}}": _column_manager_items(layout),
    }

    output = template
    for marker, value in substitutions.items():
        output = output.replace(marker, value)
    return output
