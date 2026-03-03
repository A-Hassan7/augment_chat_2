"""
Load and save the column layout config (inspector_layout.json).
"""

from __future__ import annotations

import json
from pathlib import Path

LAYOUT_PATH = Path(__file__).parent / "inspector_layout.json"


def load_layout() -> list[dict]:
    """Return the list of column dicts from inspector_layout.json."""
    with open(LAYOUT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["columns"]


def save_layout(columns: list[dict]) -> None:
    """Persist a new column list to inspector_layout.json."""
    with open(LAYOUT_PATH, "w", encoding="utf-8") as f:
        json.dump({"columns": columns}, f, indent=2)
