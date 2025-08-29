import re

from fastapi import Request
from pydantic import BaseModel

from ..config import BridgeManagerConfig
from .bridge_service import BridgeService
from .bridge_registry import BridgeRegistry


class Bridge:
    # match database model
    pass


class Homeserver:
    # match database model
    pass


# as the request comes in I need to handle common requirements in the helper class
# recognise bridge/homeserver
# adjust path/params/body by changing the username
# go from the start now and create the database models first. Design up.

"""

Request

RequestHelper (helps recognise homserver/bridge the request is from/to)

Homeserver/Bridge service

Homeserver/Bridge service handles request

"""


class RequestHelperModel(BaseModel):
    """
    For each request I need to know where it's from (homeserver/bridge) and be able to identify:
        1. the bridge it is from / intended to go to
            a. homeserver id
            b. ip/port
            c. as_token
            d. type
        2. the homeserver it's from / intended to go to

    Args:
        BaseModel (_type_): _description_

    Raises:
        ValueError: _description_
        ValueError: _description_
    """

    model_config = {"arbitrary_types_allowed": True}

    request: Request
    bridge_manager_config: BridgeManagerConfig
    # can either be "homeserver" or "bridge"
    source: str

    bridge_type: str = None
    bridge_id: str = None
    bridge_username: str = None
    bridge_instance: BridgeService = None

    homeserver_name: str = None
    homeserver_username: str = None

    def model_post_init(self, __context) -> None:

        if self.source not in ("homeserver", "bridge"):
            raise ValueError("source must be either 'homeserver' or 'bridge'")

        if self.source == "homeserver":
            self.handle_from_homeserver()

        if self.source == "bridge":
            self.handle_from_bridge()

    def handle_from_homeserver(self):

        # parse the path to get user_id etc
        path = self.request.path_params["path"]

        username_pattern = rf".*/@{self.bridge_manager_config.NAMESPACE}(?P<bridge_type>[^_]+)_(?P<bridge_id>[^_]+)__(?P<bridge_username>[^:]+):(?P<homeserver>[^\s/]+)"
        match = re.match(username_pattern, path)

        if not match:
            raise ValueError("Invalid path format for extracting user info")

        self.bridge_type = match.group("bridge_type")
        self.bridge_id = match.group("bridge_id")
        self.bridge_username = match.group("bridge_username")
        self.homeserver_name = match.group("homeserver")
        self.homeserver_username = f"@{self.bridge_manager_config.NAMESPACE}{self.bridge_type}_{self.bridge_id}__{self.bridge_username}:{self.homeserver}"

        # TODO: get bridge service based on bridge type and id
        registry = BridgeRegistry(self.bridge_manager_config)
        self.bridge = registry.get_bridge(
            bridge_type=self.bridge_type, bridge_id=self.bridge_id
        )
