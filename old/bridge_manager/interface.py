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
        Create a new bridge for a Matrix user and register the management room.

        Args:
            matrix_username: Matrix user ID (e.g., @user:homeserver.com)
            service: Bridge service type (whatsapp, discord, etc.)

        Returns:
            Bridges: Created bridge model
        """
        bridge_model = self.bridge_orchestrator.create_bridge(
            bridge=service, owner_matrix_username=matrix_username
        )

        bridge_client = self._get_bridge_client(bridge_model)
        asyncio.run(bridge_client.register())

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

        # Validate bridge service type

        bridge_client = self._get_bridge_client(bridge)
        login_code = asyncio.run(bridge_client.login(phone_number))

        return {'data': login_code}

    def delete_bridge(self, bridge: Bridges):
        self.bridge_orchestrator.delete_bridge(bridge_model=bridge)

    def list_bridges_by_owner(self, matrix_username: str) -> List[Bridges]:
        """
        List all bridges owned by a Matrix user.

        Args:
            matrix_username: Matrix user ID

        Returns:
            List of Bridges models
        """
        bridges = self.bridge_registry.list_bridges_by_owner(matrix_username)
        bridges = [bridge for bridge in bridges if bridge.deleted_at is None]
        return bridges

    def _get_bridge_client(self, bridge):

        bridge_mapper = {"whatsapp": WhatsappBridgeClient}
        bridge_client_cls = bridge_mapper.get(bridge.bridge_service)

        if not bridge_client_cls:
            raise ValueError(f"Unsupported bridge service: {bridge.bridge_service}")

        bridge_client = bridge_client_cls(bridge)
        return bridge_client
