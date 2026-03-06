"""
Request handler classes for the bridge manager appservice.

These handlers sit in the proxy pipeline and allow path-specific transformations
to be applied to requests before they are forwarded to their destination.

  handlers/
  ├── base.py                  — ProxyContext, PathRouter, RequestHandlerBase
  ├── bridge_handler.py        — BridgeRequestHandler     (Bridge → HS, generic)
  ├── homeserver_handler.py    — HomeserverRequestHandler (HS → Bridge, generic)
  ├── bridge_types/
  │   ├── __init__.py          — BridgeHandlerRegistry
  │   └── whatsapp.py          — WhatsAppBridgeRequestHandler
  └── homeserver_types/
      └── __init__.py          — HomeserverHandlerRegistry

Usage in appservice.py:

    from bridge_manager.appservice.handlers import (
        ProxyContext,
        BridgeHandlerRegistry,
        HomeserverHandlerRegistry,
    )

    # Bridge → Homeserver
    handler = BridgeHandlerRegistry.get_handler(bridge.bridge_type)
    context = await handler.handle(context)

    # Homeserver → Bridge
    handler = HomeserverHandlerRegistry.get_handler(bridge.bridge_type)
    context = await handler.handle(context)
"""

from .base import ProxyContext, PathRouter, RequestHandlerBase
from .bridge_handler import BridgeRequestHandler
from .homeserver_handler import HomeserverRequestHandler
from .bridge_types import BridgeHandlerRegistry
from .homeserver_types import HomeserverHandlerRegistry

__all__ = [
    "ProxyContext",
    "PathRouter",
    "RequestHandlerBase",
    "BridgeRequestHandler",
    "HomeserverRequestHandler",
    "BridgeHandlerRegistry",
    "HomeserverHandlerRegistry",
]
