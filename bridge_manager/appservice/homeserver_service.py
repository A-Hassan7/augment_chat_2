import json
import httpx
import re
from fastapi import Request, Response

from fastapi.responses import JSONResponse

from .bridge_registry import BridgeRegistry
from .models import RequestHelperModel
from ..config import TRANSACTION_ID_TO_BRIDGE_MAPPER


class HomeserverService:

    def __init__(self, bridge_manager_config):
        self.bridge_registry = BridgeRegistry(bridge_manager_config)
        self.bridge_manager_config = bridge_manager_config

        # Pattern for @_bridge_manager__{bridge_service}_{bridge_id}__{username}:{homeserver}
        # Example: @_bridge_manager__whatsapp_1__whatsappbot:matrix.localhost.me
        self.username_regex = rf"@{self.bridge_manager_config.NAMESPACE}(?P<bridge_type>[^_]+)_(?P<bridge_id>[^_]+)__(?P<bridge_username>[^:]+):(?P<homeserver>[^\s/]+)"

    async def handle_request(self, request: Request) -> Response:
        """
        Each endpoint is handled by a dedicated function.
        For example, requests to _matrix/app/v1/ping are processed by the ping function.

        Some endpoints include usernames in their paths, which are matched using regular expressions.
        For instance, _matrix/app/v1/users/@_bridge_manager__whatsapp_1__bot is handled accordingly.

        There are two mechanisms to determine the target bridge for a request:

            1. Transaction ID in the payload: When a request includes a transaction ID, it is mapped to the corresponding bridge and used to route responses.
            2. Username in the path: The username segment encodes the bridge service and bridge ID (e.g., @_bridge_manager__whatsapp_1__+4476334...), allowing identification of the intended bridge.

        """

        path = request.path_params.get("path")
        path_mapper = {
            "_matrix/app/v1/ping": self.ping,
            rf"_matrix/app/v1/users/{self.username_regex}": self.users,
            rf"_matrix/app/transactions/\d+": self.transactions,  # TODO: IMPLEMENT THISSSSS!!!!!
        }

        # Add dynamic users path mapping using regex
        for path_regex, handler_func in path_mapper.items():
            if re.match(path_regex, path):
                return await handler_func(request)

        raise NotImplementedError(f"Path '{path}' is not handled")

    async def ping(self, request: Request) -> Response:

        body = await request.body()
        body = json.loads(body)

        # TODO: need to store the transaction ids in a table
        transaction_id = body.get("transaction_id")
        bridge_as_token = TRANSACTION_ID_TO_BRIDGE_MAPPER[transaction_id]

        bridge_service = self.bridge_registry.get_bridge(bridge_as_token)

        body = json.dumps(body)

        headers = dict(request._headers)
        headers["authorization"] = f"Bearer {self.bridge_manager_config.HS_TOKEN}"
        headers.pop("content-length", None)

        return await bridge_service.send_request(
            method=request.method,
            path=request.path_params["path"],
            headers=headers,
            data=body,
        )

    async def users(self, request: Request) -> Response:

        path = request.path_params["path"]
        match = re.match("(?P<endpoint>.*)/" + self.username_regex, path)
        if not match:
            return JSONResponse(
                content={"error": "Invalid path format"}, status_code=400
            )

        endpoint = match.group("endpoint")
        bridge_type = match.group("bridge_type")
        bridge_id = match.group("bridge_id")
        bridge_username = match.group("bridge_username")
        homeserver_name = match.group("homeserver")

        bridge = self.bridge_registry.get_bridge(bridge_id=int(bridge_id))

        # The bridge just needs the username
        # Example: @_bridge_manager__whatsapp_1__whatsappbot:matrix.localhost.me -> @whatsappbot:matrix.localhost.me

        # If the path contains the full MXID, replace it with just the username
        # Find and replace the full MXID with username_only
        # Extract the full MXID from the path and replace it with just the username
        new_path = f"{endpoint}/@{bridge_username}:{homeserver_name}"

        return await bridge.send_request(
            method=request.method,
            path=new_path,
            headers=dict(request._headers),
        )

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
        """
        Send request to the homeserver.

        This will always put the right authorization token in the header

        Args:
            method (_type_): _description_
            path (_type_): _description_
            query_params (_type_, optional): _description_. Defaults to None.
            headers (_type_, optional): _description_. Defaults to None.
            content (_type_, optional): _description_. Defaults to None.
            data (_type_, optional): _description_. Defaults to None.
            json (_type_, optional): _description_. Defaults to None.

        Returns:
            Response: _description_
        """

        headers["authorization"] = f"Bearer {self.bridge_manager_config.HS_TOKEN}"

        url = f"{self.bridge_manager_config.HS_URL}/{path}"

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

    async def transactions(self, request: Request) -> Response:
        """
        Handles PUT /_matrix/app/v1/transactions/{txnId} requests, rewriting all bridge usernames in the request body.
        """

        # Determine the bridge from the transaction ID in the path
        txn_id_match = re.match(
            r"_matrix/app/transactions/(?P<txn_id>\d+)", request.path_params["path"]
        )
        if not txn_id_match:
            return JSONResponse(
                content={"error": "Invalid transaction path"}, status_code=400
            )
        txn_id = txn_id_match.group("txn_id")

        bridge_as_token = TRANSACTION_ID_TO_BRIDGE_MAPPER.get(txn_id)
        if not bridge_as_token:
            return JSONResponse(
                content={"error": "Unknown transaction ID"}, status_code=404
            )

        bridge_service = self.bridge_registry.get_bridge(as_token=bridge_as_token)

        # Parse body
        body = await request.body()
        try:
            body_json = json.loads(body)
        except Exception:
            return JSONResponse(content={"error": "Invalid JSON body"}, status_code=400)

        # Recursively replace all bridge usernames in the body
        def replace_usernames(obj):

            if isinstance(obj, dict):

                for k, v in obj.items():

                    if isinstance(v, str):

                        if username_match := re.match(self.username_regex, v):
                            # Rewrite to just the username part: @bridge_username:homeserver
                            bridge_username = username_match.group("bridge_username")
                            homeserver_name = username_match.group("homeserver")
                            obj[k] = f"@{bridge_username}:{homeserver_name}"

                    else:
                        obj[k] = replace_usernames(v)

            elif isinstance(obj, list):
                return [replace_usernames(i) for i in obj]

            return obj

        body_json = replace_usernames(body_json)

        response = await bridge_service.send_request(
            method=request.method,
            path=request.path_params["path"],
            headers=dict(request._headers),
            json=body_json,
        )
        return response
