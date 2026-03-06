"""
Handler for requests that originated from a bridge and are being forwarded
to the homeserver.

Direction:  Bridge → Bridge Manager Appservice → Homeserver

Register path-specific transformations in _register_routes().
Any path that does not match a registered route is forwarded unchanged.
"""

from dataclasses import replace

from .base import ProxyContext, RequestHandlerBase


class BridgeRequestHandler(RequestHandlerBase):
    """
    Applies path-specific transformations to bridge-originating requests
    before they are forwarded to the homeserver.

    Add a handler method and register it in _register_routes() for any path
    that requires modification.
    """

    def _register_routes(self) -> None:
        self.router.register(r"client/versions$", self._handle_client_versions)

    async def _handle_client_versions(self, context: ProxyContext) -> ProxyContext:
        """
        Strip the ``user_id`` query parameter before forwarding to the homeserver.

        The bridge appends ``?user_id=@...`` to the ``/_matrix/client/versions``
        request, but the homeserver's versions endpoint does not accept that
        parameter and returns an error when it is present.
        """
        filtered_params = {
            k: v for k, v in context.query_params.items() if k != "user_id"
        }
        return replace(context, query_params=filtered_params)
