from __future__ import annotations

from typing import TYPE_CHECKING
import json
import httpx
import re
from fastapi import Response

from fastapi.responses import JSONResponse

from ..bridge_registry import BridgeRegistry
from ..database.repositories import TransactionMappingsRepository

if TYPE_CHECKING:
    from .models import RequestContext


class HomeserverService:

    def __init__(self, bridge_manager_config):
        self.bridge_registry = BridgeRegistry(bridge_manager_config)
        self.bridge_manager_config = bridge_manager_config

    async def handle_request(self, request_ctx: "RequestContext") -> Response:
        """
        Routes requests to the correct handler based on the request path
        """

        path = request_ctx.request.path_params.get("path")
        if path == "_matrix/app/v1/ping":
            return await self.ping(request_ctx)
        if path.startswith("_matrix/app/v1/users/"):
            return await self.users(request_ctx)
        if path.startswith("_matrix/app/v1/transactions/"):
            return await self.transactions(request_ctx)

        raise NotImplementedError(f"Path '{path}' is not handled")

    async def ping(self, request_ctx: "RequestContext") -> Response:
        """
        Handle ping requests from the homeserver.

        Validates the transaction ID, looks up the associated bridge,
        and forwards the ping request to that bridge.
        """

        # Extract and validate the request body
        body_json = request_ctx.body_json if request_ctx else None
        if not body_json:
            return JSONResponse(
                content={"error": "Missing or invalid JSON body"}, status_code=400
            )

        # Extract transaction ID from the body
        transaction_id = body_json.get("transaction_id")
        if not transaction_id:
            return JSONResponse(
                content={"error": "Transaction ID missing"}, status_code=400
            )

        # Look up which bridge this transaction belongs to
        mapping = TransactionMappingsRepository().get_bridge_by_transaction(
            transaction_id
        )
        bridge_as_token = mapping.bridge_as_token if mapping else None

        if not bridge_as_token:
            return JSONResponse(
                content={"error": "Unknown transaction ID"}, status_code=404
            )

        # Get the bridge service instance
        bridge_service = self.bridge_registry.get_bridge(bridge_as_token)

        # Prepare headers for forwarding to the bridge
        headers = (
            request_ctx.headers.copy()
            if request_ctx and request_ctx.headers is not None
            else {}
        )
        headers.pop("content-length", None)  # Remove to let httpx recalculate

        # Forward the ping request to the appropriate bridge
        body = json.dumps(body_json)
        return await bridge_service.send_request(
            request_ctx=request_ctx,
            method=request_ctx.request.method,
            path=request_ctx.request.path_params["path"],
            headers=headers,
            data=body,
        )

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

        rewritten = request_ctx.rewrite_usernames_in_body(to="bridge")
        if rewritten is not None:
            body_json = rewritten

        headers = (
            request_ctx.headers
            if request_ctx and request_ctx.headers is not None
            else dict(request_ctx.request.headers)
        )

        response = await bridge_service.send_request(
            method=request_ctx.request.method,
            path=request_ctx.request.path_params["path"],
            headers=headers,
            json=body_json,
        )
        return response
