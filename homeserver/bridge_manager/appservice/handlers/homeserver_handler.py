"""
Handler for requests that originated from the homeserver and are being
forwarded to a bridge.

Direction:  Homeserver → Bridge Manager Appservice → Bridge

The handler uses the same two-level route registration pattern as
BridgeRequestHandler:

  _register_routes()
    └─ _register_type_specific_routes()   ← override in subclasses (runs first)
    └─ _register_generic_routes()         ← always runs, acts as a fallback

Bridge-type-specific subclasses can override _register_type_specific_routes()
to handle paths differently per bridge type.
"""

from .base import RequestHandlerBase


class HomeserverRequestHandler(RequestHandlerBase):
    """
    Generic handler for homeserver-originating requests.

    Applies path-specific transformations common to all bridge types.
    Bridge-type-specific subclasses override _register_type_specific_routes()
    to add or override behaviour for individual paths.
    """

    def _register_routes(self) -> None:
        # Type-specific routes are registered first so they take priority.
        self._register_type_specific_routes()
        # Generic routes run second; they only match paths not claimed above.
        self._register_generic_routes()

    def _register_type_specific_routes(self) -> None:
        """
        Hook for bridge-type-specific route registration.

        Override this in a subclass to register path handlers that should run
        before — and therefore shadow — the generic routes.  The base
        implementation does nothing.
        """

    def _register_generic_routes(self) -> None:
        """Register path transforms that apply to every bridge type."""
        # No generic homeserver-to-bridge transforms required yet.
        # Example:
        #   self.router.register(r"app/v1/transactions/", self._handle_transactions)
