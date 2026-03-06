"""
Handler for requests that originated from the homeserver and are being
forwarded to a bridge.

Direction:  Homeserver → Bridge Manager Appservice → Bridge

Register path-specific transformations in _register_routes().
Any path that does not match a registered route is forwarded unchanged.
"""

from .base import RequestHandlerBase


class HomeserverRequestHandler(RequestHandlerBase):
    """
    Applies path-specific transformations to homeserver-originating requests
    before they are forwarded to the target bridge.

    Add a handler method and register it in _register_routes() for any path
    that requires modification.
    """

    def _register_routes(self) -> None:
        # No homeserver-specific transforms required yet.
        # Example:
        #   self.router.register(r"app/v1/transactions/", self._handle_transactions)
        pass
