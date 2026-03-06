"""
Request handler classes for the bridge manager appservice.

These handlers sit in the proxy pipeline and allow path-specific transformations
to be applied to requests before they are forwarded to their destination.

  handlers/
  ├── base.py               — ProxyContext, PathRouter, RequestHandlerBase
  ├── homeserver_handler.py — HomeserverRequestHandler (HS → Bridge transforms)
  └── bridge_handler.py     — BridgeRequestHandler     (Bridge → HS transforms)
"""

from .base import ProxyContext, PathRouter, RequestHandlerBase
from .homeserver_handler import HomeserverRequestHandler
from .bridge_handler import BridgeRequestHandler

__all__ = [
    "ProxyContext",
    "PathRouter",
    "RequestHandlerBase",
    "HomeserverRequestHandler",
    "BridgeRequestHandler",
]
