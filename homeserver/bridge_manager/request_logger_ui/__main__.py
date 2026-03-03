"""
Entry point: python3 -m bridge_manager.request_logger_ui

Reads config from the shared .env file (same as the rest of the project).
"""

from __future__ import annotations

import http.server
import os
from pathlib import Path

# Load .env from the homeserver root before anything else
from dotenv import load_dotenv

_HOMESERVER_DIR = Path(__file__).parent.parent.parent
load_dotenv(dotenv_path=_HOMESERVER_DIR / ".env")

from .server import LogInspectorHandler  # noqa: E402  (import after dotenv)


def main():
    port = int(os.environ.get("INSPECTOR_PORT", 5002))
    host = os.environ.get("INSPECTOR_HOST", "127.0.0.1")

    server = http.server.HTTPServer((host, port), LogInspectorHandler)
    print(f"Bridge Manager — Request Logger UI")
    print(f"  http://{host}:{port}/")
    print(f"  Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping.")
        server.server_close()


if __name__ == "__main__":
    main()
