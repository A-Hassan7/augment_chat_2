from abc import ABC, abstractmethod
import json
import httpx

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from ..config import BridgeManagerConfig, TRANSACTION_ID_TO_BRIDGE_MAPPER
from ..database.repositories import BridgeBotsRepository


# the homeserver needs to create a user for each specific service
# the username will have to be part of the namespace i.e. _bridge_manager__whatsapp_1__


class BridgeService(ABC):

    def __init__(self, as_token: str, bridge_manager_config: BridgeManagerConfig):

        from .homeserver_service import HomeserverService
        from .bridge_registry import BridgeRegistry

        self.bridge_manager_config = bridge_manager_config
        self.homeserver = HomeserverService(bridge_manager_config=bridge_manager_config)

        bridge_bots_repo = BridgeBotsRepository()
        bridge = bridge_bots_repo.get_by_as_token(as_token=as_token)

        self.as_token = as_token
        self.bridge_type = bridge.bridge_service
        self.bridge_id = bridge.id
        self.hs_token = bridge.hs_token
        self.bridge_url = f"http://{bridge.ip}:{bridge.port}"

    async def send_request(
        self,
        method,
        path,
        query_params=None,
        headers=None,
        content=None,
        data=None,
        json=None,
    ) -> Response:

        headers["authorization"] = f"Bearer {self.hs_token}"

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
        return f"@{self.bridge_manager_config.NAMESPACE}{self.bridge_type}_{self.bridge_id}:{self.bridge_manager_config.HS_NAME}"

    @staticmethod
    async def extract_request_details(request: Request) -> dict:
        """
        Extracts all important details from request.scope and returns a dict suitable for JSON serialization.
        """
        scope = request.scope
        body = await request.body()
        try:
            body = json.loads(body)
        except Exception:
            body = None

        details = {
            "method": scope.get("method"),
            "path": scope["path_params"].get("path"),
            "query_string": dict(request.query_params),
            "headers": dict(request._headers),
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

    async def handle_request(self, request: Request) -> Response:

        path = request.path_params.get("path")
        path_mapper = {
            "_matrix/client/versions": self.matrix_version,
            "_matrix/client/v3/account/whoami": self.whoami,
            "_matrix/client/v1/appservice/whatsapp/ping": self.ping,
            "_matrix/client/v1/media/config": self.media_config,
            f"_matrix/client/v3/profile/@whatsappbot:{self.bridge_manager_config.HS_NAME}/avatar_url": self.avatar_url,
            f"_matrix/client/v3/profile/@whatsappbot:{self.bridge_manager_config.HS_NAME}/displayname": self.displayname,
        }

        handler_func = path_mapper.get(path)
        if not handler_func:
            raise NotImplementedError(f"Path '{path}' is not handled")

        return await handler_func(request)

    async def matrix_version(self, request: Request) -> Response:
        # Implement the actual logic here

        body = await request.body()

        return await self.homeserver.send_request(
            method=request.method,
            path=request.path_params["path"],
            headers=dict(request._headers),
            content=body,
        )

    async def whoami(self, request: Request) -> Response:
        # Implement the actual logic here

        response = await self.homeserver.send_request(
            method=request.method,
            path=request.path_params["path"],
            headers=dict(request._headers),
        )
        response_body = json.loads(response.body)
        response_body["user_id"] = f"@whatsappbot:{self.bridge_manager_config.HS_NAME}"
        return JSONResponse(content=response_body, status_code=response.status_code)

    async def ping(self, request: Request) -> Response:

        body = await request.body()
        body = json.loads(body)

        transaction_id = body.get("transaction_id")
        if not transaction_id:
            raise ValueError("Transaction ID missing")

        body = json.dumps(body)

        path = request.path_params["path"]
        path = path.replace("whatsapp", self.bridge_manager_config.ID)

        # Remove Content-Length header if present to let httpx set it correctly
        headers = dict(request._headers)
        headers.pop("content-length", None)

        # need to keep track of the transaction ID because there's no other way to know which bridge the ping reply belongs to from the application service

        TRANSACTION_ID_TO_BRIDGE_MAPPER[transaction_id] = self.as_token

        return await self.homeserver.send_request(
            method=request.method,
            path=path,
            headers=headers,
            data=body,
        )

    async def media_config(self, request: Request) -> Response:
        # Forward the request to the homeserver and return its response
        response = await self.homeserver.send_request(
            method=request.method,
            path=request.path_params["path"],
            headers=dict(request._headers),
        )
        return response

    async def avatar_url(self, request: Request) -> Response:
        # Substitute the username and homeserver name in the path and query string

        bridge_manager_full_username = (
            f"@{self.bridge_manager_config.id}:{self.bridge_manger_config.hs_name}"
        )

        path = request["path_params"].get("path")
        path.replace(
            f"@whatsappbot:{self.bridge_manager_config.hs_name}",
            bridge_manager_full_username,
        )

        query_params = request.query_params
        query_params["user_id"] = bridge_manager_full_username
        # ensure query_params is a dict and encode values if necessary
        # query_params = {k: v.encode("utf-8") if isinstance(v, str) and not v.isascii() else v for k, v in query_params.items()}

        response = await self.homeserver.send_request(
            method=request.method,
            path=path,
            headers=dict(request._headers),
            query_params=query_params,
        )
        return response

    async def displayname(self, request: Request) -> Response:

        bridge_manager_full_username = (
            f"@{self.bridge_manager_config.id}:{self.bridge_manger_config.hs_name}"
        )

        path = request["path_params"].get("path")
        path.replace(
            f"@whatsappbot:{self.bridge_manager_config.hs_name}",
            bridge_manager_full_username,
        )

        query_params = request.query_params
        query_params["user_id"] = bridge_manager_full_username
        # ensure query_params is a dict and encode values if necessary
        # query_params = {k: v.encode("utf-8") if isinstance(v, str) and not v.isascii() else v for k, v in query_params.items()}

        response = await self.homeserver.send_request(
            method=request.method,
            path=path,
            headers=dict(request._headers),
            query_params=query_params,
        )
        return response
