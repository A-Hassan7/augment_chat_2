from __future__ import annotations
from abc import ABC, abstractmethod
import re
import json
import httpx
import logging
from typing import TYPE_CHECKING

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from ..config import BridgeManagerConfig
from ..database.repositories import (
    BridgesRepository,
    TransactionMappingsRepository,
    HomeserversRepository,
)
from .route_registry import RouteRegistry, RouteNotFoundError
from .common_handlers import MatrixClientAPIHandlers, AppserviceAPIHandlers

if TYPE_CHECKING:
    from .models import RequestContext

logger = logging.getLogger(__name__)

# the homeserver needs to create a user for each specific service
# the username will have to be part of the namespace i.e. _bridge_manager__whatsapp_1__


class BridgeService(ABC):

    def __init__(
        self,
        as_token: str,
        bridge_manager_config: BridgeManagerConfig,
    ):

        from .homeserver_service import HomeserverService
        from ..bridge_registry import BridgeRegistry

        self.bridge_manager_config = bridge_manager_config
        self.homeserver = HomeserverService(bridge_manager_config=bridge_manager_config)

        # get the bridge model from the database
        bridges_repo = BridgesRepository()
        bridge = bridges_repo.get_by_as_token(as_token=as_token)

        # get the homeserver this bridge is registered to
        homeserver_repo = HomeserversRepository()
        homeserver = homeserver_repo.get_by_hs_token(bridge.hs_token)

        self.homeserver_name = homeserver.name
        self.as_token = as_token
        self.bridge_type = bridge.bridge_service
        self.bridge_id = bridge.id
        self.bridge_url = f"http://{bridge.ip}:{bridge.port}"

        # Initialize route registry
        self.routes = RouteRegistry(fallback_handler=self.unhandled_endpoint)
        self.register_routes()

    async def send_request(
        self,
        request_ctx,
        method,
        path,
        query_params=None,
        headers=None,
        content=None,
        data=None,
        json=None,
    ) -> Response:

        headers["authorization"] = f"Bearer {request_ctx.homeserver.hs_token}"

        url = f"{self.bridge_url}/{path}"

        async with httpx.AsyncClient() as client:

            request = client.build_request(
                method=method,
                url=url,
                params=query_params,
                headers=headers,
                content=content,
                json=json,
                data=data,
            )

            # log the outgoing request
            request_ctx.log_outbound_request(request)

            response = await client.send(request)

            # log response
            request_ctx.log_response(response)

        return JSONResponse(content=response.json(), status_code=response.status_code)

    @abstractmethod
    def register_routes(self) -> None:
        """
        Register endpoint routes for this bridge service.

        Subclasses should override this to register their specific endpoints.
        Use self.routes.add_exact() or self.routes.add_regex() to register.
        """
        pass

    async def handle_request(self, request_ctx: RequestContext) -> Response:
        """
        Handle an incoming request by routing to the appropriate handler.

        Args:
            request_ctx: Request context with bridge/homeserver info

        Returns:
            Response from the matched handler

        Raises:
            RouteNotFoundError: If no route matches and no fallback is set
        """
        path = request_ctx.request.path_params.get("path")
        logger.info(f"Handling {self.bridge_type} bridge request to {path}")

        try:
            handler = self.routes.match_or_fallback(path)
            return await handler(request_ctx)
        except RouteNotFoundError as e:
            logger.error(f"No handler for path '{path}': {e}")
            return JSONResponse(
                content={"error": f"Endpoint not implemented: {path}"}, status_code=501
            )

    async def unhandled_endpoint(self, request_ctx: RequestContext) -> Response:
        """
        Default fallback handler for unmatched endpoints.

        Can be overridden by subclasses to provide custom behavior.
        """
        path = request_ctx.request.path_params.get("path")
        logger.warning(f"Unhandled endpoint for {self.bridge_type}: {path}")
        return JSONResponse(
            content={
                "error": "Endpoint not implemented",
                "path": path,
                "bridge_type": self.bridge_type,
            },
            status_code=501,
        )

    @property
    def username(self):
        """
        Creates the username for the bot like @_bridge_manager__whatsapp_1:matrix.localhost.me
        """
        return f"@{self.bridge_manager_config.NAMESPACE}{self.bridge_type}_{self.bridge_id}:{self.homeserver_name}"

    @staticmethod
    async def extract_request_details(request: Request) -> dict:
        """
        Extracts all important details from request.scope and returns a dict suitable for JSON serialization.
        Prefers using RequestContext stored on request.state to avoid consuming the ASGI body multiple times.
        """
        scope = request.scope

        body = None
        headers = dict(request.headers)
        query_string = dict(request.query_params)

        request_ctx = getattr(request.state, "request_context", None)
        if request_ctx:
            body = request_ctx.body_json if request_ctx.body_json is not None else None
            headers = (
                request_ctx.headers
                if request_ctx.headers is not None
                else dict(request.headers)
            )
            query_string = (
                request_ctx.query_params
                if request_ctx.query_params is not None
                else dict(request.query_params)
            )
        else:
            body = await request.body()
            try:
                body = json.loads(body)
            except Exception:
                body = None

        details = {
            "method": scope.get("method"),
            "path": scope["path_params"].get("path"),
            "query_string": query_string,
            "headers": headers,
            "body": body,
        }
        return details


class WhatsappBridgeService(BridgeService):
    """
    WhatsApp Bridge Service implementation.

    Request Flow:
    1. WA -> HS: _matrix/client/versions - checks matrix homeserver version
    2. WA -> HS: _matrix/client/v3/account/whoami - verifies bot identity
    3. WA -> HS: _matrix/client/v3/register - registers whatsapp users
    """

    def register_routes(self) -> None:
        """Register WhatsApp-specific Matrix Client API endpoints"""
        # Use common handlers for standard endpoints
        self.routes.add_exact(
            "_matrix/client/versions",
            lambda ctx: MatrixClientAPIHandlers.versions(ctx, self.homeserver),
            "Matrix client API versions",
        )
        self.routes.add_exact(
            "_matrix/client/v3/account/whoami",
            self.whoami,  # Keep custom implementation for username translation
            "Check bot identity",
        )
        self.routes.add_exact(
            "_matrix/client/v1/media/config",
            lambda ctx: MatrixClientAPIHandlers.media_config(ctx, self.homeserver),
            "Media configuration",
        )
        self.routes.add_exact(
            "_matrix/client/v3/register",
            lambda ctx: MatrixClientAPIHandlers.register(ctx, self.homeserver),
            "User registration",
        )

        # Regex patterns for dynamic paths
        self.routes.add_regex(
            r"_matrix/client/v1/appservice/\w+/ping",
            self.ping,  # Keep custom implementation for transaction mapping
            "Appservice ping",
        )
        self.routes.add_regex(
            rf"_matrix/client/v3/profile/@\w+:{re.escape(self.homeserver_name)}/avatar_url",
            lambda ctx: MatrixClientAPIHandlers.profile_avatar_url(
                ctx, self.homeserver
            ),
            "User avatar URL",
        )
        self.routes.add_regex(
            rf"_matrix/client/v3/profile/@\w+:{re.escape(self.homeserver_name)}/displayname",
            lambda ctx: MatrixClientAPIHandlers.profile_displayname(
                ctx, self.homeserver
            ),
            "User display name",
        )

        # Media endpoints
        self.routes.add_regex(
            r"^_matrix/client/v1/media/download/[^/]+/.+",
            lambda ctx: MatrixClientAPIHandlers.media_download(ctx, self.homeserver),
            "Media download endpoint",
        )
        self.routes.add_exact(
            "_matrix/client/v1/media/upload",
            lambda ctx: MatrixClientAPIHandlers.media_upload(ctx, self.homeserver),
            "Media upload endpoint",
        )

        # Room membership endpoints
        self.routes.add_regex(
            r"_matrix/client/v3/rooms/[^/]+/join",
            lambda ctx: MatrixClientAPIHandlers.room_join(ctx, self.homeserver),
            "Room join endpoint",
        )

        # Room state endpoints
        self.routes.add_regex(
            r"_matrix/client/v3/rooms/[^/]+/state$",
            lambda ctx: MatrixClientAPIHandlers.room_state_all(ctx, self.homeserver),
            "Room state retrieval",
        )
        self.routes.add_regex(
            r"_matrix/client/v3/rooms/[^/]+/members",
            lambda ctx: MatrixClientAPIHandlers.room_members(ctx, self.homeserver),
            "Room members list",
        )

        # Room event sending endpoints
        self.routes.add_regex(
            r"_matrix/client/v3/rooms/[^/]+/send/[^/]+/.+",
            lambda ctx: MatrixClientAPIHandlers.room_send_event(ctx, self.homeserver),
            "Send room event (messages, reactions, etc.)",
        )

    async def whoami(self, request_ctx: RequestContext) -> Response:
        """
        Bridge checking who it is on the homserver and making sure it's username matches with the homserver.
        However, when i send this request as the bridge manager I will always get back the bridge managers username as the whoami.
        I need to translate the outbound request

        Args:
            request_ctx (RequestContext): _description_

        Returns:
            Response: _description_
        """

        response = await self.homeserver.send_request(
            request_ctx=request_ctx,
            method=request_ctx.request.method,
            path=request_ctx.request.path_params["path"],
            headers=(
                request_ctx.headers
                if request_ctx and request_ctx.headers is not None
                else dict(request_ctx.request.headers)
            ),
            query_params=request_ctx.query_params,
        )
        response_body = json.loads(response.body)
        return JSONResponse(content=response_body, status_code=response.status_code)

    async def ping(self, request_ctx: RequestContext) -> Response:

        body_json = request_ctx.body_json if request_ctx else None
        if not body_json:
            raise ValueError("Missing or invalid JSON body")

        transaction_id = body_json.get("transaction_id")
        if not transaction_id:
            raise ValueError("Transaction ID missing")

        body = json.dumps(body_json)

        # Replace bridge-specific appservice ID with bridge_manager ID
        path = request_ctx.request.path_params.get("path")
        path = re.sub(
            r"(_bridge_manager__)[^/]+", rf"{self.bridge_manager_config.ID}", path
        )

        headers = (
            request_ctx.headers.copy()
            if request_ctx and request_ctx.headers is not None
            else dict(request_ctx.request.headers)
        )
        headers.pop("content-length", None)

        TransactionMappingsRepository().upsert(
            transaction_id, bridge_as_token=self.as_token, bridge_id=self.bridge_id
        )

        return await self.homeserver.send_request(
            request_ctx=request_ctx,
            method=request_ctx.request.method,
            path=path,
            headers=headers,
            data=body,
        )
