from __future__ import annotations
from abc import ABC, abstractmethod
import json
import httpx
from typing import TYPE_CHECKING

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from ..config import BridgeManagerConfig
from ..database.repositories import (
    BridgesRepository,
    TransactionMappingsRepository,
    HomeserversRepository,
)

if TYPE_CHECKING:
    from .models import RequestContext

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

            response = await client.request(
                method=method,
                url=url,
                params=query_params,
                headers=headers,
                content=content,
                json=json,
                data=data,
            )

        return JSONResponse(content=response.json(), status_code=response.status_code)

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
    Request Flow:

    1. WA -> HS: _matrix/client/versions - checks matrix homeserver version
       WA <- HS: response


    2. WA -> HS: _matrix/client/v3/account/whoami
        WA <- HS: {'user_id': '@whatsappbot:matrix.localhost.me', 'is_guest': False}

    3. WA -> HS: _matrix/client/v3/register - tries to register the whatsapp user. I need to append the _bridge_manager__ prefix before the whatsapp bridge id (need a custom id). This is going to the user on the homeserver and will be the prefix for the users. This is how I'm going to know which bridge the user belogs to on the homeserver.
       WA <- HS:
    """

    async def handle_request(self, request_ctx: RequestContext) -> Response:
        """Handle an incoming bridge request; `request_ctx` is a RequestContext built by the appservice catchall."""
        path = request_ctx.request.path_params.get("path")
        path_mapper = {
            "_matrix/client/versions": self.matrix_version,
            "_matrix/client/v3/account/whoami": self.whoami,
            "_matrix/client/v1/appservice/whatsapp/ping": self.ping,
            "_matrix/client/v1/media/config": self.media_config,
            f"_matrix/client/v3/profile/@whatsappbot:{self.homeserver_name}/avatar_url": self.avatar_url,
            f"_matrix/client/v3/profile/@whatsappbot:{self.homeserver_name}/displayname": self.displayname,
            "_matrix/client/v3/register": self.register,
        }

        handler_func = path_mapper.get(path)
        if not handler_func:
            raise NotImplementedError(f"Path '{path}' is not handled")

        return await handler_func(request_ctx)

    async def matrix_version(self, request_ctx: RequestContext) -> Response:
        # Forward using helper values
        return await self.homeserver.send_request(
            request_ctx=request_ctx,
            method=request_ctx.request.method,
            path=request_ctx.request.path_params["path"],
            headers=(
                request_ctx.headers
                if request_ctx and request_ctx.headers is not None
                else dict(request_ctx.request.headers)
            ),
            # content=(request_ctx.body_bytes if request_ctx else None),
        )

    async def whoami(self, request_ctx: RequestContext) -> Response:
        response = await self.homeserver.send_request(
            request_ctx=request_ctx,
            method=request_ctx.request.method,
            path=request_ctx.request.path_params["path"],
            headers=(
                request_ctx.headers
                if request_ctx and request_ctx.headers is not None
                else dict(request_ctx.request.headers)
            ),
        )
        response_body = json.loads(response.body)
        response_body["user_id"] = f"@whatsappbot:{self.homeserver_name}"
        return JSONResponse(content=response_body, status_code=response.status_code)

    async def ping(self, request_ctx: RequestContext) -> Response:
        body_json = request_ctx.body_json if request_ctx else None
        if not body_json:
            raise ValueError("Missing or invalid JSON body")

        transaction_id = body_json.get("transaction_id")
        if not transaction_id:
            raise ValueError("Transaction ID missing")

        body = json.dumps(body_json)

        path = request_ctx.request.path_params.get("path")
        path = path.replace("whatsapp", self.bridge_manager_config.ID)

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

    async def media_config(self, request_ctx: RequestContext) -> Response:
        response = await self.homeserver.send_request(
            request_ctx=request_ctx,
            method=request_ctx.request.method,
            path=request_ctx.request.path_params["path"],
            headers=(
                request_ctx.headers
                if request_ctx and request_ctx.headers is not None
                else dict(request_ctx.request.headers)
            ),
        )
        return response

    async def avatar_url(self, request_ctx: RequestContext) -> Response:
        bridge_manager_full_username = (
            f"@{self.bridge_manager_config.ID}:{self.homeserver_name}"
        )

        path_username = (
            request_ctx.translate_username(
                bridge_manager_full_username, to="homeserver"
            )
            if request_ctx
            else request_ctx.request.path_params.get("path")
        )
        path = f"/_matrix/client/v3/profile/{path_username}/avatar_url"

        # query_params = (
        #     request_ctx.query_params.copy()
        #     if request_ctx and request_ctx.query_params is not None
        #     else dict(request_ctx.request.query_params)
        # )
        # query_params["user_id"] = bridge_manager_full_username

        response = await self.homeserver.send_request(
            request_ctx=request_ctx,
            method=request_ctx.request.method,
            path=path,
            headers=(
                request_ctx.headers
                if request_ctx and request_ctx.headers is not None
                else dict(request_ctx.request.headers)
            ),
            # query_params=query_params,
        )
        return response

    async def displayname(self, request_ctx: RequestContext) -> Response:

        bridge_manager_full_username = (
            f"@{self.bridge_manager_config.ID}:{self.homeserver_name}"
        )

        path = (
            request_ctx.translate_username(
                bridge_manager_full_username, to="homeserver"
            )
            if request_ctx
            else request_ctx.request.path_params.get("path")
        )

        query_params = (
            request_ctx.query_params.copy()
            if request_ctx and request_ctx.query_params is not None
            else dict(request_ctx.request.query_params)
        )
        query_params["user_id"] = bridge_manager_full_username

        response = await self.homeserver.send_request(
            request_ctx=request_ctx,
            method=request_ctx.request.method,
            path=path,
            headers=(
                request_ctx.headers
                if request_ctx and request_ctx.headers is not None
                else dict(request_ctx.request.headers)
            ),
            query_params=query_params,
        )
        return response

    async def register(self, request_ctx: RequestContext) -> Response:

        # query_string
        # b'user_id=%40whatsappbot%3Amatrix.localhost.me'
        # @whatsappbot:matrix.localhost.me -> @_bridge_manager__whatsapp_7__whatsappbot:matrix.localhost.me
        request_ctx.query_params["user_id"] = request_ctx.translate_username(
            request_ctx.query_params["user_id"], to="homeserver"
        )

        # body
        # '{"username":"whatsappbot","inhibit_login":true,"type":"m.login.application_service"}'
        request_ctx.body_json["username"] = request_ctx.translate_username(
            f'@{request_ctx.body_json["username"]}:random', to="homeserver"
        )
        request_ctx.body_json["username"] = (
            request_ctx.body_json["username"].replace("@", "").split(":")[0]
        )

        headers = (
            request_ctx.headers.copy()
            if request_ctx and request_ctx.headers is not None
            else dict(request_ctx.request.headers)
        )
        headers.pop("content-length", None)

        return await self.homeserver.send_request(
            request_ctx=request_ctx,
            method=request_ctx.request.method,
            path=request_ctx.request.path_params["path"],
            headers=headers,
            query_params=request_ctx.query_params,
            json=request_ctx.body_json,
        )
