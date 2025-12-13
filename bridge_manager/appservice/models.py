from __future__ import annotations

import re
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, TYPE_CHECKING
from enum import Enum

from fastapi import Request

from ..config import BridgeManagerConfig
from ..bridge_registry import BridgeRegistry
from ..database.repositories import BridgesRepository
from ..database.repositories import (
    TransactionMappingsRepository,
    HomeserversRepository,
    RequestsRepository,
)

if TYPE_CHECKING:
    from .bridge_service import BridgeService


class RequestSource(Enum):
    HOMESERVER = "homeserver"
    BRIDGE = "bridge"


class RequestContext:
    """
    For each request I need to know where it's from (homeserver/bridge) and be able to identify:
        1. the bridge it is from / intended to go to
            a. homeserver id
            b. ip/port
            c. as_token
            d. type
        2. the homeserver it's from / intended to go to

    This model also centralizes creation of a request log entry via an injected RequestLogger
    and provides convenience methods to mark forwarded/handled/unhandled and to attach responses.
    """

    def __init__(
        self,
        request: Request,
        source: RequestSource,
        bridge_manager_config: BridgeManagerConfig,
        # these need to be bridge and homserver classes
        bridge: Optional[Any] = None,
        bridge_discovery_method: Optional[str] = None,
        homeserver: Optional[Any] = None,
        body_json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, Any]] = None,
        query_params: Optional[Dict[str, Any]] = None,
        transaction_id: Optional[str] = None,
    ):

        self.request = request
        self.source = source
        self.bridge_manager_config = bridge_manager_config

        self.bridge = bridge
        self.bridge_discovery_method = bridge_discovery_method
        self.homeserver = homeserver

        self.body_json = body_json
        self.headers = headers
        self.query_params = query_params
        self.transaction_id = transaction_id

        request_model = self.log_inbound_request()
        self.request_id = request_model.id

    @classmethod
    async def create(
        cls,
        request: Request,
        bridge_manager_config: BridgeManagerConfig,
        source: str,
    ):

        # read body
        body = await request.body()
        body_json = json.loads(body) if body else None

        # read path, headers and query params
        path = request.path_params.get("path", "")
        headers = dict(request.headers)
        query_params = dict(request.query_params)

        # convert source string to RequestSource Enum
        try:
            source_enum = RequestSource(source)
        except ValueError:
            raise ValueError("source must be either 'homeserver' or 'bridge'")

        bridge = cls.discover_bridge(
            bridge_manager_config=bridge_manager_config,
            headers=headers,
            source_enum=source_enum,
            path=path,
            body_json=body_json,
            body=body,
        )
        homeserver = cls.discover_homeserver(headers=headers, source_enum=source_enum)

        # create instance of the request context
        inst = cls(
            request=request,
            source=source_enum,
            bridge_manager_config=bridge_manager_config,
            bridge=bridge,
            # bridge_discovery_method=bridge_discovery_method,
            homeserver=homeserver,
            body_json=body_json,
            headers=headers,
            query_params=query_params,
            # transaction_id=transaction_id,
        )

        return inst

    def log_inbound_request(self):
        """
        Serialize request to be stored in the database. Only keeping the important bits to keep lean.

        Keeps:
            -

        Args:
            request (Request): Original request
        """
        requests_repo = RequestsRepository()

        data = json.dumps(
            {
                "method": self.request.method,
                "url": self.request.url._url,
                "path": self.request.path_params.get("path", ""),
                "query_params": self.query_params,
                "headers": self.headers,
                "body_json": self.body_json,
            }
        )

        # create a request record in the database
        request_model = requests_repo.create(
            inbound_at=datetime.now(timezone.utc),
            source=self.source.value,
            bridge_id=self.bridge.bridge_id,
            homeserver_id=self.homeserver.id,
            method=self.request.method,
            inbound_request=data,
        )

        return request_model

    def log_outbound_request(self, request):
        """
        Log the request being sent to the destination

        Args:
            request (_type_): _description_
        """

        requests_repo = RequestsRepository()

        body = request.content.decode("utf-8")
        body_json = json.loads(body) if body else None
        data = json.dumps(
            {
                "method": request.method,
                "url": str(request.url),
                "path": request.url.path,
                "query_params": dict(request.url.query),
                "headers": dict(request.headers),
                "body_json": body_json,
            }
        )

        requests_repo.update(
            id_=self.request_id,
            outbound_at=datetime.now(timezone.utc),
            outbound_request=data,
        )

    def log_response(self, response):

        requests_repo = RequestsRepository()

        content = response.content.decode("utf-8")
        content = json.loads(content) if content else None
        data = json.dumps(content)

        requests_repo.update(
            id_=self.request_id, response=data, response_status=response.status_code
        )

    @classmethod
    def discover_bridge(
        cls, bridge_manager_config, headers, source_enum, path, body_json, body
    ):
        """
        Bridge Discovery Process
        ---

        I need to identify which bridge the request belongs to in order to forward requests to the appropriate bridge.

        If the request has originated from the bridge then I can get the bridge using the as_token.

        If the request originated from the homeserver I'll need to use either:
            a. username in the request path
            b. transaction id reference that's been saved from a previous request
            c. the bridges username in the body of the request
            d. the bridge owners username in the body of the request

        """
        # the bridge registry provides convenience to create the bridge instance
        registry = BridgeRegistry(bridge_manager_config)

        # if it's from the bridge that then I can get the bridge using the as_token
        if source_enum == RequestSource.BRIDGE:
            as_token = cls._extract_auth_token_from_headers(headers)
            if not as_token:
                raise ValueError(
                    "Bridge requests must include an as_token in the Authorization header."
                )

            bridge = registry.get_bridge(as_token=as_token)
            bridge_discovery_method = "as_token"

        # if the request originated from the server I'll have to find a username or a transaction id to identify a bridge
        if source_enum == RequestSource.HOMESERVER:

            bridge = None

            # a. try finding bridge from the username in the path
            username_pattern = rf".*/{bridge_manager_config.username_regex}"
            match = re.match(username_pattern, path)
            if match:
                try:
                    bridge_id = match.group("bridge_id")
                    bridge = registry.get_bridge(bridge_id=bridge_id)
                except Exception as e:
                    raise ValueError(
                        f"Failed to get bridge using the bridge ID found in the request path username: {e}"
                    )

            # b. try using a transaction id match which can be found in either the body or the path
            if not bridge:
                transactions_repo = TransactionMappingsRepository()

                # try finding the txn id in the path or the body
                txn_id_match = re.match(
                    r"_matrix/app/v1/transactions/(?P<txn_id>\d+)", path
                )
                txn_id_path = txn_id_match.group("txn_id") if txn_id_match else None
                txn_id_body = body_json.get("transaction_id") if body else None

                txn_id = txn_id_path or txn_id_body
                if txn_id:
                    bridge = transactions_repo.get_bridge_by_transaction(
                        transaction_id=txn_id
                    )

            # TODO: use a room_id mapping before resorting to searching for usernames in the body

            # c, d. try finding the username of either the bridge or the bridge owner in the body
            if not bridge:

                # iterate through all dicts and strings in the body to find a pattern match
                def find_username(obj, pattern):
                    if isinstance(obj, dict):
                        for v in obj.values():
                            if isinstance(v, str):
                                if re.match(pattern, v):
                                    return v
                            else:
                                result = find_username(v, pattern)
                                if result:
                                    return result
                    elif isinstance(obj, list):
                        for item in obj:
                            result = find_username(item, pattern)
                            if result:
                                return result
                    return None

                # try finding the bridge owners username in the body
                owner_username_pattern = (
                    rf"@(?P<homeserver_username>[^:]+):(?P<homeserver>[^\s/]+)"
                )
                owner_username_in_body = find_username(
                    body_json, owner_username_pattern
                )

                # try finding the bridges username in the body
                bridge_username_pattern = bridge_manager_config.username_regex
                bridge_username_in_body = find_username(
                    body_json, bridge_username_pattern
                )

                # not sure I understand why I need both the bridge username and the owner username
                # looks like I can't find the bridge service from the owner username?
                service = None
                if bridge_username_in_body:
                    match = re.match(bridge_username_pattern, bridge_username_in_body)
                    service = match.group("bridge_type")

                if owner_username_in_body and service:
                    bridge = registry.get_bridge(
                        owner_username=owner_username_in_body, service=service
                    )

            # Raise error if bridge is still not found
            if not bridge:
                raise ValueError("Bridge not found for the given request.")

        return bridge

    @classmethod
    def discover_homeserver(cls, headers, source_enum):
        """
        Homeserver discovery process
        ---

        I need to identify which homeserver the request is from. For there will likely only be one HS so this isn't totally necessary.

        If the request originates from the homeserver then I can just need to search for the HS token.

        If the request originates from a bridge then I have to search the bridge bots table to find the associated bridge.
        """

        homeserver_repo = HomeserversRepository()
        bridges_repo = BridgesRepository()

        homeserver = None

        if source_enum == RequestSource.HOMESERVER:
            hs_token = cls._extract_auth_token_from_headers(headers)
            homeserver = homeserver_repo.get_by_hs_token(hs_token)

        if source_enum == RequestSource.BRIDGE:
            # search the bridge register
            as_token = cls._extract_auth_token_from_headers(headers)
            bridge_model = bridges_repo.get_by_as_token(as_token)
            hs_token = bridge_model.hs_token
            homeserver = homeserver_repo.get_by_hs_token(hs_token)

        if not homeserver:
            raise ValueError("Homeserver not found for the given request.")

        return homeserver

    @staticmethod
    def _extract_auth_token_from_headers(headers: Optional[Dict[str, Any]]):
        if not headers:
            return None
        auth = headers.get("authorization") or headers.get("Authorization")
        if not auth:
            return None
        return auth.replace("Bearer ", "")

    def translate_username(self, username, to: str):
        """
        Translate between a homeserver username and a bridge username

        Args:
            username (_type_): _description_
            to (str): _description_

        Returns:
            _type_: _description_
        """

        if not to in ["bridge", "homeserver"]:
            raise ValueError("to can only be bridge or homeserver")

        if to == "homeserver":

            """
            Need to convert bridge username to homeserver username
            e.g. @_bridge_manager__whatsapp_1__whatsappbot:matrix.localhost.me -> @whatsappbot:matrix.localhost.me
            """

            username_pattern = rf"@(?P<username>[^:]+):(?P<homeserver>[^\s/]+)"
            if not (match := re.match(username_pattern, username)):
                raise ValueError("username pattern not recognised")

            namespace = self.bridge_manager_config.NAMESPACE
            bridge_type = self.bridge.bridge_type
            bridge_id = self.bridge.bridge_id
            bridge_username = match.group("username")
            homeserver = match.group("homeserver")

            return (
                f"@{namespace}{bridge_type}_{bridge_id}__{bridge_username}:{homeserver}"
            )

        if to == "bridge":

            """
            Need to convert homeserver username to bridge username
            e.g. @whatsappbot:matrix.localhost.me -> @_bridge_manager__whatsapp_1__whatsappbot:matrix.localhost.me
            """

            username_pattern = self.bridge_manager_config.username_regex

            if not (match := re.match(username_pattern, username)):
                raise ValueError("username pattern not recognised")

            bridge_username = match.group("bridge_username")
            homeserver = match.group("homeserver")

            return f"@{bridge_username}:{homeserver}"

    def rewrite_usernames_in_body(self, to: str) -> Optional[Dict[str, Any]]:
        """
        Searches through the body and replaces any string that resembles a username into the equivilent username for the homeserver/bridge

        Args:
            to (str): homeserver or bridge
        """

        if not to in ["bridge", "homeserver"]:
            raise ValueError("to can only be bridge or homeserver")

        if not self.body_json:
            return None

        homeserver_username_pattern = self.bridge_manager_config.username_regex
        bridge_username_pattern = r"@(?P<username>[^:]+):(?P<homeserver>[^\s/]+)"

        def replace(obj, to):

            if isinstance(obj, dict):

                for k, v in list(obj.items()):

                    if isinstance(v, str):

                        if re.match(homeserver_username_pattern, v) or re.match(
                            bridge_username_pattern, v
                        ):
                            obj[k] = self.translate_username(v, to=to)

                    else:
                        obj[k] = replace(v)

                return obj

            elif isinstance(obj, list):
                return [replace(i) for i in obj]

            else:
                return obj

        return replace(self.body_json.copy())
