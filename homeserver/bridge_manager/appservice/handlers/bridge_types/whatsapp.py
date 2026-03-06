"""
WhatsApp-specific bridge request handler.

Direction:  WhatsApp Bridge → Bridge Manager Appservice → Homeserver

Override _register_type_specific_routes() with any transforms that are unique
to the WhatsApp bridge.  These routes are registered *before* the generic
BridgeRequestHandler routes, so they take priority for the paths they match.

Paths not registered here fall through to the generic handlers defined in
BridgeRequestHandler._register_generic_routes().
"""

from ..bridge_handler import BridgeRequestHandler


class WhatsAppBridgeRequestHandler(BridgeRequestHandler):
    """
    Bridge request handler for the WhatsApp bridge.

    Inherits all generic transforms from BridgeRequestHandler and adds
    WhatsApp-specific path handling on top.
    """

    def _register_type_specific_routes(self) -> None:
        # Register WhatsApp-specific path transforms here.
        #
        # Example:
        #   self.router.register(
        #       r"client/v3/account/whoami$",
        #       self._handle_whoami,
        #   )
        pass
