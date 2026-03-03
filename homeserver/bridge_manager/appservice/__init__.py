"""
Bridge Manager Appservice - Proxy layer for Matrix bridges.

The appservice handles:
- Request routing between homeserver and bridge instances
- Token management and authentication
- Bridge discovery and registry
- Request/response logging

This is separate from the orchestrator which manages bridge container lifecycle.
"""

from .registry import BridgeRegistry
from .router import BridgeRouter
from .token_manager import TokenManager

__all__ = [
    "BridgeRegistry",
    "BridgeRouter",
    "TokenManager",
]
