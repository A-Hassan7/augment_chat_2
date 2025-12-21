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
from .bridge_resolver import BridgeResolver, BridgeResolutionMethod, BridgeNotFoundError

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
        bridge_discovery_method: Optional[BridgeResolutionMethod] = None,
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

        # Request ID will be set by log_inbound_request() when called from create()
        self.request_id = None

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

        # Initialize with None - will be populated if discovery succeeds
        bridge = None
        bridge_discovery_method = None
        homeserver = None
        discovery_error = None

        # Try to discover bridge - don't fail if it's not found, just log it
        try:
            resolver = BridgeResolver(bridge_manager_config)
            bridge, bridge_discovery_method = resolver.resolve(
                source=source_enum,
                headers=headers,
                path=path,
                body_json=body_json,
                query_params=query_params,
            )
        except Exception as e:
            discovery_error = f"Bridge discovery failed: {str(e)}"

        # Try to discover homeserver - don't fail if it's not found, just log it
        try:
            homeserver = cls.discover_homeserver(
                headers=headers, source_enum=source_enum
            )
        except Exception as e:
            if discovery_error:
                discovery_error += f" | Homeserver discovery failed: {str(e)}"
            else:
                discovery_error = f"Homeserver discovery failed: {str(e)}"

        # create instance of the request context
        inst = cls(
            request=request,
            source=source_enum,
            bridge_manager_config=bridge_manager_config,
            bridge=bridge,
            bridge_discovery_method=bridge_discovery_method,
            homeserver=homeserver,
            body_json=body_json,
            headers=headers,
            query_params=query_params,
        )

        # Log the inbound request - this MUST happen for all requests
        request_model = inst.log_inbound_request(discovery_error=discovery_error)
        inst.request_id = request_model.id

        # Now raise the error if discovery failed (after logging)
        if discovery_error:
            if bridge is None:
                raise BridgeNotFoundError(discovery_error)
            elif homeserver is None:
                raise ValueError(discovery_error)

        return inst

    def log_inbound_request(self, discovery_error: Optional[str] = None):
        """
        Serialize request to be stored in the database. Only keeping the important bits to keep lean.

        This method logs ALL requests, even if bridge or homeserver discovery fails.
        Bridge and homeserver IDs are optional and only logged if discovery succeeded.

        Args:
            discovery_error: Optional error message if bridge/homeserver discovery failed
        """
        requests_repo = RequestsRepository()

        # Build request data (discovery error is now a separate column)
        request_data = {
            "method": self.request.method,
            "url": self.request.url._url,
            "path": self.request.path_params.get("path", ""),
            "query_params": self.query_params,
            "headers": self.headers,
            "body_json": self.body_json,
        }

        data = json.dumps(request_data)

        # create a request record in the database
        # bridge_id, homeserver_id, bridge_discovery_method, and discovery_error are optional
        request_model = requests_repo.create(
            inbound_at=datetime.now(timezone.utc),
            source=self.source.value,
            bridge_id=self.bridge.bridge_id if self.bridge else None,
            homeserver_id=self.homeserver.id if self.homeserver else None,
            bridge_discovery_method=(
                self.bridge_discovery_method.value
                if self.bridge_discovery_method
                else None
            ),
            discovery_error=discovery_error,
            method=self.request.method,
            path=self.request.path_params.get("path", ""),
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
                "query_params": request.url.query.decode("utf-8"),
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
        """
        Log the response from either homeserver or bridge.

        Supports both httpx.Response and FastAPI Response objects.
        """
        requests_repo = RequestsRepository()

        # Handle different response types
        if hasattr(response, "content"):
            # httpx.Response
            content = (
                response.content.decode("utf-8")
                if isinstance(response.content, bytes)
                else response.content
            )
        elif hasattr(response, "body"):
            # FastAPI Response
            content = (
                response.body.decode("utf-8")
                if isinstance(response.body, bytes)
                else response.body
            )
        else:
            content = str(response)

        try:
            content_json = json.loads(content) if content else None
        except (json.JSONDecodeError, TypeError):
            # If not JSON, store as string
            content_json = content

        data = json.dumps(content_json)

        requests_repo.update(
            id_=self.request_id, response=data, response_status=response.status_code
        )

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
                        obj[k] = replace(v, to)

                return obj

            elif isinstance(obj, list):
                return [replace(i, to) for i in obj]

            else:
                return obj

        return replace(self.body_json.copy(), to)
