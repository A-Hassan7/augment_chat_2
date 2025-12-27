from __future__ import annotations

from typing import TYPE_CHECKING
import json
import httpx
import re
from fastapi import Response

from fastapi.responses import JSONResponse

from ..bridge_registry import BridgeRegistry
from ..database.repositories import TransactionMappingsRepository
from .route_registry import RouteRegistry, RouteNotFoundError
from logger import Logger

if TYPE_CHECKING:
    from .models import RequestContext

logger = Logger().get_logger(__name__)


class HomeserverService:

    def __init__(self, bridge_manager_config):
        self.bridge_registry = BridgeRegistry(bridge_manager_config)
        self.bridge_manager_config = bridge_manager_config

        # Initialize route registry
        self.routes = RouteRegistry(fallback_handler=self.unhandled_endpoint)
        self._register_routes()

    def _register_routes(self) -> None:
        """Register Application Service API endpoints"""
        # Exact match for ping
        self.routes.add_exact(
            "_matrix/app/v1/ping", self.ping, "Appservice ping from homeserver"
        )

        # Prefix matches for user queries and transactions
        self.routes.add_prefix(
            "_matrix/app/v1/users/", self.users, "User query endpoint"
        )
        self.routes.add_prefix(
            "_matrix/app/v1/transactions/",
            self.transactions,
            "Event transactions from homeserver",
        )

    async def handle_request(self, request_ctx: "RequestContext") -> Response:
        """
        Routes requests to the correct handler based on the request path.

        Args:
            request_ctx: Request context with bridge/homeserver info

        Returns:
            Response from the matched handler

        Raises:
            RouteNotFoundError: If no route matches
        """
        path = request_ctx.request.path_params.get("path")
        logger.info(f"Handling homeserver request to {path}")

        try:
            handler = self.routes.match_or_fallback(path)
            return await handler(request_ctx)
        except RouteNotFoundError as e:
            logger.error(f"No handler for homeserver path '{path}': {e}")
            return JSONResponse(
                content={"error": f"Endpoint not implemented: {path}"}, status_code=501
            )

    async def unhandled_endpoint(self, request_ctx: "RequestContext") -> Response:
        """
        Default fallback handler for unmatched homeserver endpoints.
        """
        path = request_ctx.request.path_params.get("path")
        logger.warning(f"Unhandled homeserver endpoint: {path}")
        return JSONResponse(
            content={
                "error": "Endpoint not implemented",
                "path": path,
                "service": "homeserver",
            },
            status_code=501,
        )

    async def ping(self, request_ctx: "RequestContext") -> Response:
        """
        Handle ping requests from the homeserver.

        The ping endpoint is a health check. The homeserver sends this
        to verify the application service is reachable. We respond
        immediately with 200 OK and an empty JSON object.

        This is NOT forwarded to individual bridges - it's answered
        directly by the bridge manager as per Matrix AS API spec.

        Flow:
        1. Bridge → Homeserver: POST /_matrix/client/v1/appservice/{id}/ping
        2. Homeserver → Bridge Manager: POST /_matrix/app/v1/ping
        3. Bridge Manager → Homeserver: 200 OK {} (this response)
        4. Homeserver → Bridge: 200 OK {"duration_ms": 123}
        """
        logger.info("Received ping from homeserver")

        # Validate request body contains transaction_id (optional but good practice)
        body_json = request_ctx.body_json if request_ctx else None
        if body_json and "transaction_id" in body_json:
            transaction_id = body_json["transaction_id"]
            logger.info(f"Ping transaction_id: {transaction_id}")

        # Return 200 OK with empty JSON (per Matrix AS API spec)
        return JSONResponse(content={}, status_code=200)

    async def users(self, request_ctx: "RequestContext") -> Response:

        path = request_ctx.request.path_params.get("path", "")
        m = re.match(
            rf"(?P<endpoint>.*)/@{self.bridge_manager_config.NAMESPACE}(?P<bridge_type>[^_]+)_(?P<bridge_id>[^_]+)__(?P<bridge_username>[^:]+):(?P<homeserver>[^\\s/]+)",
            path,
        )
        if not m:
            return JSONResponse(
                content={"error": "Invalid encoded username"}, status_code=400
            )

        endpoint = m.group("endpoint")
        bridge_username = m.group("bridge_username")
        homeserver_name = m.group("homeserver")

        import urllib.parse

        plain_username = f"@{bridge_username}:{request_ctx.homeserver.name}"
        encoded_username = urllib.parse.quote(plain_username, safe="")
        new_path = f"{endpoint}/{encoded_username}"

        headers = (
            request_ctx.headers
            if request_ctx and request_ctx.headers is not None
            else dict(request_ctx.request.headers)
        )

        # b'{"errcode":"M_NOT_FOUND","error":"User not found"}'

        return await request_ctx.bridge.send_request(
            method=request_ctx.request.method,
            path=new_path,
            headers=headers,
        )

    async def send_request(
        self,
        request_ctx: RequestContext,
        method,
        path,
        query_params=None,
        headers=None,
        content=None,
        data=None,
        json=None,
        timeout: float = 20,  # Default timeout in seconds
    ) -> Response:

        headers["authorization"] = f"Bearer {self.bridge_manager_config.AS_TOKEN}"
        url = f"{request_ctx.homeserver.url}/{path}"

        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                request = client.build_request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=query_params,
                    content=content,
                    json=json,
                    data=data,
                )

                # log the outgoing request
                request_ctx.log_outbound_request(request)

                response = await client.send(request)

                # log response
                request_ctx.log_response(response)

            except httpx.TimeoutException:
                return JSONResponse(
                    content={"error": "Request timed out"}, status_code=504
                )

        if not response.is_success:
            try:
                error_content = response.json()
            except Exception:
                error_content = response.text
            raise Exception(
                f"Request failed with status {response.status_code}: {error_content}"
            )

        return JSONResponse(content=response.json(), status_code=response.status_code)

    async def transactions(self, request_ctx: "RequestContext") -> Response:

        # the request context model will parse the response and find the bridge based on the transaction id if available
        bridge_service = request_ctx.bridge

        body_json = request_ctx.body_json if request_ctx else None
        if body_json is None:
            return JSONResponse(content={"error": "Invalid JSON body"}, status_code=400)

        # rewritten = request_ctx.rewrite_usernames_in_body(to="bridge")
        # if rewritten is not None:
        # body_json = rewritten

        headers = (
            request_ctx.headers
            if request_ctx and request_ctx.headers is not None
            else dict(request_ctx.request.headers)
        )
        headers.pop("content-length", None)

        response = await bridge_service.send_request(
            request_ctx=request_ctx,
            method=request_ctx.request.method,
            path=request_ctx.request.path_params["path"],
            headers=headers,
            json=body_json,
        )
        return response
