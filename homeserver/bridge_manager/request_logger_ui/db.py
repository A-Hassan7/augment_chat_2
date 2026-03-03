"""
Raw psycopg2 query functions for the request logger UI.

Reads BRIDGE_MANAGER_DATABASE_URL from the environment (loaded from .env by
__main__.py before this module is used).  The URL is a standard SQLAlchemy
postgresql DSN which psycopg2 can accept directly after stripping the
'postgresql+psycopg2://' or 'postgresql://' prefix into keyword args.
"""

from __future__ import annotations

import os
import json
import re
from typing import Any

import psycopg2
import psycopg2.extras  # RealDictCursor


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

def _parse_db_url(url: str) -> dict:
    """Convert a postgresql[+psycopg2]://user:pass@host:port/dbname URL to kwargs."""
    url = re.sub(r"^postgresql\+psycopg2://", "postgresql://", url)
    m = re.match(
        r"postgresql://(?P<user>[^:@]+)(?::(?P<password>[^@]*))?@"
        r"(?P<host>[^:/]+)(?::(?P<port>\d+))?/(?P<dbname>[^?]+)",
        url,
    )
    if not m:
        raise ValueError(f"Cannot parse DATABASE_URL: {url!r}")
    kwargs: dict[str, Any] = {
        "dbname": m.group("dbname"),
        "user": m.group("user"),
        "host": m.group("host"),
    }
    if m.group("password"):
        kwargs["password"] = m.group("password")
    if m.group("port"):
        kwargs["port"] = int(m.group("port"))
    return kwargs


def get_connection():
    url = os.environ["BRIDGE_MANAGER_DATABASE_URL"]
    return psycopg2.connect(**_parse_db_url(url))


# ---------------------------------------------------------------------------
# Filter options (populate dropdowns)
# ---------------------------------------------------------------------------

def fetch_filter_options() -> dict:
    """
    Returns:
        {
            "bridges":      [{"id": int, "name": str}, ...],
            "status_codes": [200, 400, ...],
        }
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, orchestrator_id AS name
                FROM   bridge_manager.bridges
                ORDER  BY id
                """
            )
            bridges = [dict(r) for r in cur.fetchall()]

            cur.execute(
                """
                SELECT DISTINCT status_code
                FROM   bridge_manager.request_logs
                WHERE  status_code IS NOT NULL
                ORDER  BY status_code
                """
            )
            status_codes = [r["status_code"] for r in cur.fetchall()]

    return {"bridges": bridges, "status_codes": status_codes}


# ---------------------------------------------------------------------------
# Main log query
# ---------------------------------------------------------------------------

_PAGE_SIZE = 50


def fetch_logs(
    bridge_id: str | None = None,
    path_filter: str | None = None,
    status_code: str | None = None,
    from_dt: str | None = None,
    to_dt: str | None = None,
    source: str | None = None,
    page: int = 1,
) -> dict:
    """
    Returns:
        {
            "rows":       [dict, ...],   # each row is a flat dict
            "total":      int,
            "page":       int,
            "page_size":  int,
            "page_count": int,
        }

    The special synthetic column "bridge_name" is resolved via LEFT JOIN on
    bridge_manager.bridges.
    """
    conditions: list[str] = []
    params: list[Any] = []

    if bridge_id:
        conditions.append("rl.bridge_id = %s")
        params.append(int(bridge_id))

    if path_filter:
        conditions.append("rl.path ILIKE %s")
        params.append(f"%{path_filter}%")

    if status_code:
        # support e.g. "2xx" shorthand
        if status_code.endswith("xx"):
            prefix = status_code[0]
            conditions.append("rl.status_code::text LIKE %s")
            params.append(f"{prefix}__")
        else:
            conditions.append("rl.status_code = %s")
            params.append(int(status_code))

    if from_dt:
        conditions.append("rl.timestamp >= %s")
        params.append(from_dt)

    if to_dt:
        conditions.append("rl.timestamp <= %s")
        params.append(to_dt)

    if source:
        conditions.append("rl.source = %s")
        params.append(source)

    where_sql = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    offset = (page - 1) * _PAGE_SIZE

    select_sql = f"""
        SELECT
            rl.id,
            rl.request_id,
            rl.source,
            rl.direction,
            rl.bridge_id,
            COALESCE(b.orchestrator_id, '') AS bridge_name,
            rl.discovery_method,
            rl.method,
            rl.path,
            rl.query_params,
            rl.status_code,
            rl.duration_ms,
            rl.forwarded_to,
            rl.response_source,
            rl.error,
            rl.timestamp,
            rl.raw_incoming_request,
            rl.raw_outgoing_request,
            rl.response_body
        FROM bridge_manager.request_logs rl
        LEFT JOIN bridge_manager.bridges b ON b.id = rl.bridge_id
        {where_sql}
        ORDER BY rl.timestamp DESC
        LIMIT %s OFFSET %s
    """

    count_sql = f"""
        SELECT COUNT(*) AS total
        FROM bridge_manager.request_logs rl
        {where_sql}
    """

    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(count_sql, params)
            total = cur.fetchone()["total"]

            cur.execute(select_sql, params + [_PAGE_SIZE, offset])
            rows = []
            for r in cur.fetchall():
                row = dict(r)
                # JSON columns: ensure they are plain Python objects, not strings
                for col in ("query_params", "raw_incoming_request", "raw_outgoing_request", "response_body"):
                    if isinstance(row.get(col), str):
                        try:
                            row[col] = json.loads(row[col])
                        except (ValueError, TypeError):
                            pass
                rows.append(row)

    page_count = max(1, -(-total // _PAGE_SIZE))  # ceiling division

    return {
        "rows": rows,
        "total": total,
        "page": page,
        "page_size": _PAGE_SIZE,
        "page_count": page_count,
    }
