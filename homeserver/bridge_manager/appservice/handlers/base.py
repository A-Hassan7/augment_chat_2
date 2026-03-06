"""
Base primitives for the bridge manager request handler pipeline.

Three building blocks:

  ProxyContext       — immutable-friendly dataclass carrying all mutable
                       request data (method, path, headers, query params,
                       body, target URL) plus a ``handler_name`` field that
                       records which handler method processed the request.
                       Use dataclasses.replace() to produce a modified copy
                       without mutating in place.

  PathRouter         — maps compiled regex patterns to handler callables.
                       Patterns are matched against the request path in
                       registration order; the first match wins.

  RequestHandlerBase — abstract base for HomeserverRequestHandler and
                       BridgeRequestHandler.  Subclasses declare their
                       routes in _register_routes() and receive a
                       ProxyContext from handle(); they return a
                       (possibly modified) ProxyContext which appservice.py
                       uses for the actual HTTP forward.  handle() always
                       sets handler_name on the returned context so callers
                       can record which handler (or "passthrough") was used.
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, replace
from typing import Callable, Dict, List, Optional, Tuple


@dataclass
class ProxyContext:
    """
    Carries all mutable data for a request that is being proxied.

    Populated by the appservice endpoint after authentication, bridge/homeserver
    lookup, and token swap.  Handlers may return a modified copy via
    dataclasses.replace(); appservice.py uses the final context to forward the
    request.

    Attributes:
        method:       HTTP method (GET, POST, …)
        path:         Request path, e.g. "client/versions"
        headers:      Request headers (already token-swapped by the endpoint)
        query_params: Query string parameters
        body:         Raw request body bytes
        target_url:   Full URL to forward the request to
        handler_name: Set by RequestHandlerBase.handle() after dispatch.
                      Format: "<ClassName>.<method_name>" for a matched route,
                      or "<ClassName>.passthrough" when no route matched.
                      None until handle() has been called.
    """

    method: str
    path: str
    headers: Dict[str, str]
    query_params: Dict[str, str]
    body: bytes
    target_url: str
    handler_name: Optional[str] = None


class PathRouter:
    """
    Maps regex path patterns to handler callables.

    Patterns are tested against the request path in registration order.
    The first match wins.  If no pattern matches, match() returns None and
    the caller should fall through to a default (pass-through) action.

    Usage::

        router = PathRouter()
        router.register(r"client/versions$", my_handler)
        handler = router.match("client/versions")  # → my_handler
        handler = router.match("client/profile")   # → None
    """

    def __init__(self) -> None:
        self._routes: List[Tuple[re.Pattern, Callable]] = []

    def register(self, pattern: str, handler: Callable) -> None:
        """
        Register a handler for paths matching pattern.

        Args:
            pattern: Regex pattern tested against the request path.
            handler: Async callable ``(ProxyContext) -> ProxyContext``.
        """
        self._routes.append((re.compile(pattern), handler))

    def match(self, path: str) -> Optional[Callable]:
        """
        Return the handler for the first pattern that matches path.

        Args:
            path: Request path to match.

        Returns:
            The registered handler callable, or None if no pattern matches.
        """
        for pattern, handler in self._routes:
            if pattern.search(path):
                return handler
        return None


class RequestHandlerBase(ABC):
    """
    Abstract base class for path-specific request handlers.

    Subclasses implement _register_routes() to associate regex patterns with
    handler methods.  The appservice endpoints call handle() with a fully
    populated ProxyContext; the method returns a (possibly modified) context.

    If no route matches the request path the context is returned unchanged,
    giving a transparent pass-through for all unregistered paths.
    """

    def __init__(self) -> None:
        self.router = PathRouter()
        self._register_routes()

    @abstractmethod
    def _register_routes(self) -> None:
        """Register path patterns and their handler methods with self.router."""

    async def handle(self, context: ProxyContext) -> ProxyContext:
        """
        Dispatch context to a path-specific handler, or pass it through.

        Always sets ``handler_name`` on the returned context:
        - ``"<ClassName>.<method_name>"`` when a registered route matched.
        - ``"<ClassName>.passthrough"`` when no route matched and the context
          is forwarded unchanged.

        Args:
            context: Populated ProxyContext from the appservice endpoint.

        Returns:
            The original context (or a modified copy), with ``handler_name``
            set to reflect how the request was processed.
        """
        handler = self.router.match(context.path)
        class_name = type(self).__name__
        if handler:
            result = await handler(context)
            return replace(result, handler_name=f"{class_name}.{handler.__name__}")
        return replace(context, handler_name=f"{class_name}.passthrough")
