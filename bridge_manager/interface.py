import asyncio
from typing import Dict, List, Any

from .config import BridgeManagerConfig
from .orchestrator.orchestrator import BridgeOrchestrator
from .bridge_clients.whatsapp_bridge_client import WhatsappBridgeClient
from .bridge_registry import BridgeRegistry
from .database.models import Bridges


class BridgeManagerInterface:
    """
    Interface for managing bridges between Matrix and external platforms.
    Handles bridge creation, login, and registry operations.
    """

    def __init__(self):
        self.bridge_orchestrator = BridgeOrchestrator(BridgeManagerConfig())
        self.bridge_registry = BridgeRegistry(BridgeManagerConfig())

    def create_bridge(self, matrix_username: str, service: str) -> Bridges:
        """
        Create a new bridge for a Matrix user.

        Args:
            matrix_username: Matrix user ID (e.g., @user:homeserver.com)
            service: Bridge service type (whatsapp, discord, etc.)

        Returns:
            Bridges: Created bridge model
        """
        bridge_model = self.bridge_orchestrator.create_bridge(
            bridge=service, owner_matrix_username=matrix_username
        )
        return bridge_model

    def login(self, bridge: Bridges, phone_number: str) -> str:
        """
        Login to a bridge with phone number.

        Args:
            bridge: Bridge model object
            phone_number: Phone number in international format

        Returns:
            Dict with login_code, phone_number, and bridge_id

        Raises:
            ValueError: If bridge service is not supported
        """
        bridge_mapper = {"whatsapp": WhatsappBridgeClient}

        bridge_client_cls = bridge_mapper.get(bridge.bridge_service)

        # Validate bridge service type
        if not bridge_client_cls:
            raise ValueError(f"Unsupported bridge service: {bridge.bridge_service}")

        bridge_client = bridge_client_cls(bridge)

        try:
            asyncio.run(bridge_client.register())
        except Exception:
            # Bridge already registered, continue with login
            pass

        login_code = asyncio.run(bridge_client.login(phone_number))

        return login_code

    def list_bridges_by_owner(self, matrix_username: str) -> List[Bridges]:
        """
        List all bridges owned by a Matrix user.

        Args:
            matrix_username: Matrix user ID

        Returns:
            List of Bridges models
        """
        return self.bridge_registry.list_bridges_by_owner(matrix_username)
