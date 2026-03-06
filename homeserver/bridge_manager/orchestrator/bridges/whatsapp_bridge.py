"""
WhatsApp Bridge configuration and initialization logic.
"""

import secrets
from dataclasses import dataclass, field
from typing import Dict, Optional

from config import BRIDGE_MANAGER_CONFIG


@dataclass
class WhatsAppBridge:
    """
    Configuration and initialization logic for WhatsApp bridge.

    Handles bridge-specific setup including generating tokens, IDs, and config parameters.
    """

    # Static bridge configuration
    SERVICE = "whatsapp"

    # Instance-specific fields
    bridge_id: str = None
    homeserver_id: str = None
    homeserver_name: str = None
    homeserver_address: str = None
    appservice_id: str = None
    bot_username: str = None
    as_token: str = None
    hs_token: str = None
    appservice_address: str = None
    appservice_hostname: str = None
    appservice_port: int = None
    docker_host: Optional[str] = None
    container_id: Optional[str] = None
    volume_name: Optional[str] = None
    matrix_bot_username: str = None
    owner_matrix_username: str = None
    config_params: Dict = field(default_factory=dict)

    def initialize(
        self,
        bridge_id: str,
        homeserver_id: str,
        homeserver_name: str,
        homeserver_address: str,
        owner_matrix_username: str,
        docker_host: Optional[str] = None,
    ) -> None:
        """
        Initialize bridge-specific configuration.

        Generates tokens, creates unique identifiers, and prepares config parameters
        for template rendering.

        Args:
            bridge_id: Unique bridge identifier
            homeserver_id: ID of the homeserver this bridge connects to
            homeserver_name: Domain name of the homeserver (e.g., matrix.example.com)
            homeserver_address: HTTP address of the homeserver (e.g., http://synapse:8008)
            owner_matrix_username: Matrix user ID that owns this bridge
            docker_host: Optional Docker host URI for remote deployment
        """
        self.bridge_id = bridge_id
        self.homeserver_id = homeserver_id
        self.homeserver_name = homeserver_name
        self.homeserver_address = homeserver_address
        self.owner_matrix_username = owner_matrix_username
        self.docker_host = docker_host

        # Generate unique appservice ID and bot username
        self.appservice_id = f"whatsapp_{bridge_id}"
        self.bot_username = f"{BRIDGE_MANAGER_CONFIG.NAMESPACE}whatsappbot_{bridge_id}"
        self.matrix_bot_username = f"@{self.bot_username}:{homeserver_name}"
        # Owner is required at creation time

        # Generate authentication tokens
        self.as_token = secrets.token_hex(32)
        self.hs_token = secrets.token_hex(32)

        # Generate volume name for persistent storage
        self.volume_name = f"bridge_whatsapp_{bridge_id}_data"

        # Build config parameters for Jinja2 template
        self.config_params = {
            "homeserver_name": homeserver_name,
            "homeserver_address": None,  # Will be set to appservice_address (bridge talks to bridge manager, not homeserver)
            "appservice_address": None,  # Will be set when port is allocated
            "appservice_hostname": "0.0.0.0",  # Listen on all interfaces in container
            "appservice_port": None,  # Will be set when port is allocated
            "appservice_id": self.appservice_id,
            "bot_username": self.bot_username,
            "namespace": BRIDGE_MANAGER_CONFIG.NAMESPACE,
            "appservice_as_token": self.as_token,
            "appservice_hs_token": self.hs_token,
        }
