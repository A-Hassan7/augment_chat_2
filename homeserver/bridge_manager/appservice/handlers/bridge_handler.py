"""
Handler for requests that originated from a bridge and are being forwarded
to the homeserver.

Direction:  Bridge → Bridge Manager Appservice → Homeserver

The handler uses a two-level route registration pattern so that bridge-type-
specific transforms take priority over generic ones:

  _register_routes()               ← called once at construction
    └─ _register_type_specific_routes()   ← override in subclasses (runs first)
    └─ _register_generic_routes()         ← always runs, acts as a fallback

Bridge-type-specific subclasses (e.g. WhatsAppBridgeRequestHandler) override
_register_type_specific_routes() to register path handlers that run *before*
the generic ones, giving them priority while still inheriting all generic
transforms for any paths they don't register.
"""

from dataclasses import replace

from .base import ProxyContext, RequestHandlerBase


class BridgeRequestHandler(RequestHandlerBase):
    """
    Generic handler for bridge-originating requests.

    Applies path-specific transformations that are common to all bridge types.
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

        Override this in a subclass (e.g. WhatsAppBridgeRequestHandler) to
        register path handlers that should run before — and therefore shadow —
        the generic routes.  The base implementation does nothing.
        """

    def _register_generic_routes(self) -> None:
        """Register path transforms that apply to every bridge type."""
        self.router.register(r"client/versions$", self._handle_client_versions)

    # ------------------------------------------------------------------
    # Generic handlers
    # ------------------------------------------------------------------

    async def _handle_client_versions(self, context: ProxyContext) -> ProxyContext:
        """
        Strip the ``user_id`` query parameter before forwarding to the homeserver.

        Bridges append ``?user_id=@...`` to ``/_matrix/client/versions`` but the
        homeserver's versions endpoint does not accept that parameter.
        """
        filtered_params = {
            k: v for k, v in context.query_params.items() if k != "user_id"
        }
        return replace(context, query_params=filtered_params)
