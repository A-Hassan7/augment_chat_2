"""
Route registration system for bridge services.

Provides a clean way to map Matrix API endpoints to handler functions,
with support for exact matches, regex patterns, and fallback handlers.
"""

from __future__ import annotations
import re
import logging
from typing import Callable, Optional, List, Tuple, Dict, Any, TYPE_CHECKING
from dataclasses import dataclass
from enum import Enum

if TYPE_CHECKING:
    from .models import RequestContext
    from fastapi import Response

logger = logging.getLogger(__name__)


class RouteMatchType(Enum):
    """Type of route pattern matching"""

    EXACT = "exact"
    REGEX = "regex"
    PREFIX = "prefix"


class RouteNotFoundError(Exception):
    """Raised when no route matches the request path"""

    pass


@dataclass
class Route:
    """
    Represents a single route registration.

    Attributes:
        pattern: String or regex pattern to match against request paths
        handler: Async function to call when route matches
        match_type: How to match the pattern (exact, regex, prefix)
        description: Optional description for documentation/debugging
    """

    pattern: str
    handler: Callable
    match_type: RouteMatchType
    description: Optional[str] = None

    def matches(self, path: str) -> bool:
        """Check if this route matches the given path"""
        if self.match_type == RouteMatchType.EXACT:
            return path == self.pattern
        elif self.match_type == RouteMatchType.REGEX:
            return re.match(self.pattern, path) is not None
        elif self.match_type == RouteMatchType.PREFIX:
            return path.startswith(self.pattern)
        return False

    def __repr__(self):
        desc = f" ({self.description})" if self.description else ""
        return f"Route({self.match_type.value}: {self.pattern!r}{desc})"


class RouteRegistry:
    """
    Registry for managing route → handler mappings.

    Allows bridge services to register endpoints with exact strings or regex patterns.
    Routes are matched in registration order, allowing explicit prioritization.

    Example:
        registry = RouteRegistry()
        registry.add_exact("_matrix/client/versions", handle_versions)
        registry.add_regex(r"_matrix/client/v3/profile/@.+/avatar_url", handle_avatar)
        registry.set_fallback(handle_unknown)

        handler = registry.match("_matrix/client/versions")
        response = await handler(request_ctx)
    """

    def __init__(self, fallback_handler: Optional[Callable] = None):
        """
        Initialize route registry.

        Args:
            fallback_handler: Optional handler to call when no routes match
        """
        self._routes: List[Route] = []
        self._fallback_handler = fallback_handler

    def add_exact(
        self, path: str, handler: Callable, description: Optional[str] = None
    ) -> None:
        """
        Register a handler for an exact path match.

        Args:
            path: Exact path string to match (e.g., "_matrix/client/versions")
            handler: Async function to handle requests
            description: Optional description for debugging
        """
        route = Route(
            pattern=path,
            handler=handler,
            match_type=RouteMatchType.EXACT,
            description=description,
        )
        self._routes.append(route)
        logger.debug(f"Registered exact route: {path}")

    def add_regex(
        self, pattern: str, handler: Callable, description: Optional[str] = None
    ) -> None:
        """
        Register a handler for a regex pattern match.

        Args:
            pattern: Regex pattern (e.g., r"_matrix/client/v3/profile/@.+/avatar_url")
            handler: Async function to handle requests
            description: Optional description for debugging

        Raises:
            ValueError: If pattern is not a valid regex
        """
        # Validate regex pattern
        try:
            re.compile(pattern)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern '{pattern}': {e}")

        route = Route(
            pattern=pattern,
            handler=handler,
            match_type=RouteMatchType.REGEX,
            description=description,
        )
        self._routes.append(route)
        logger.debug(f"Registered regex route: {pattern}")

    def add_prefix(
        self, prefix: str, handler: Callable, description: Optional[str] = None
    ) -> None:
        """
        Register a handler for paths starting with a prefix.

        Args:
            prefix: Path prefix to match (e.g., "_matrix/client/v3/")
            handler: Async function to handle requests
            description: Optional description for debugging
        """
        route = Route(
            pattern=prefix,
            handler=handler,
            match_type=RouteMatchType.PREFIX,
            description=description,
        )
        self._routes.append(route)
        logger.debug(f"Registered prefix route: {prefix}")

    def set_fallback(self, handler: Callable) -> None:
        """
        Set a fallback handler for when no routes match.

        Args:
            handler: Async function to handle unmatched requests
        """
        self._fallback_handler = handler
        logger.debug("Set fallback handler")

    def match(self, path: str) -> Optional[Callable]:
        """
        Find the first handler that matches the given path.

        Routes are checked in registration order, so register more specific
        routes before more general ones.

        Args:
            path: Request path to match

        Returns:
            Handler function if a route matches, None otherwise
        """
        for route in self._routes:
            if route.matches(path):
                logger.debug(f"Path '{path}' matched {route}")
                return route.handler

        logger.debug(f"No route matched path '{path}'")
        return None

    def match_or_fallback(self, path: str) -> Optional[Callable]:
        """
        Find a matching handler or return the fallback handler.

        Args:
            path: Request path to match

        Returns:
            Handler function or fallback handler

        Raises:
            RouteNotFoundError: If no match and no fallback is configured
        """
        handler = self.match(path)
        if handler:
            return handler

        if self._fallback_handler:
            logger.debug(f"Using fallback handler for path '{path}'")
            return self._fallback_handler

        raise RouteNotFoundError(f"No route or fallback handler for path: {path}")

    def get_routes(self) -> List[Route]:
        """Get all registered routes (useful for debugging/documentation)"""
        return self._routes.copy()

    def clear(self) -> None:
        """Remove all registered routes"""
        self._routes.clear()
        logger.debug("Cleared all routes")

    def remove_pattern(self, pattern: str) -> bool:
        """
        Remove a route by its pattern.

        Args:
            pattern: The pattern string to remove

        Returns:
            True if a route was removed, False otherwise
        """
        original_len = len(self._routes)
        self._routes = [r for r in self._routes if r.pattern != pattern]
        removed = len(self._routes) < original_len

        if removed:
            logger.debug(f"Removed route with pattern '{pattern}'")

        return removed

    def __len__(self) -> int:
        """Return number of registered routes"""
        return len(self._routes)

    def __repr__(self):
        return f"RouteRegistry({len(self._routes)} routes, fallback={'set' if self._fallback_handler else 'not set'})"


class RouteBuilder:
    """
    Fluent interface for building route registries.

    Example:
        routes = (RouteBuilder()
            .exact("_matrix/client/versions", handle_versions, "Client versions")
            .regex(r"_matrix/client/v3/profile/@.+/avatar", handle_avatar)
            .fallback(handle_unknown)
            .build())
    """

    def __init__(self):
        self._registry = RouteRegistry()

    def exact(
        self, path: str, handler: Callable, description: Optional[str] = None
    ) -> RouteBuilder:
        """Add exact match route (chainable)"""
        self._registry.add_exact(path, handler, description)
        return self

    def regex(
        self, pattern: str, handler: Callable, description: Optional[str] = None
    ) -> RouteBuilder:
        """Add regex match route (chainable)"""
        self._registry.add_regex(pattern, handler, description)
        return self

    def prefix(
        self, prefix: str, handler: Callable, description: Optional[str] = None
    ) -> RouteBuilder:
        """Add prefix match route (chainable)"""
        self._registry.add_prefix(prefix, handler, description)
        return self

    def fallback(self, handler: Callable) -> RouteBuilder:
        """Set fallback handler (chainable)"""
        self._registry.set_fallback(handler)
        return self

    def build(self) -> RouteRegistry:
        """Return the built registry"""
        return self._registry
