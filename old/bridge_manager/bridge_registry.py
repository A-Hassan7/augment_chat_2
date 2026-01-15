from datetime import datetime, timezone

from .config import BridgeManagerConfig
from .database.repositories import (
    BridgesRepository,
    RequestsRepository,
    TransactionMappingsRepository,
    RoomBridgeMappingRepository,
)
from .database.models import Bridges


class BridgeRegistry:
    """Registry for managing bridge instances with caching for performance."""

    def __init__(self, bridge_manager_config: BridgeManagerConfig):
        self.bridge_manager_config = bridge_manager_config
        self.bridges_repository = BridgesRepository()
        # Cache to avoid repeated DB lookups
        self._bridge_cache = {}

    # TODO: Register bridge (the orchestrator will register the bridge instance)
    def register_bridge(
        self,
        orchestrator_id,
        bridge_service,
        container_id,
        volume_name,
        matrix_bot_username,
        as_token,
        hs_token,
        ip,
        port,
        owner_matrix_username,
    ):
        # register the bridge in the database
        return self.bridges_repository.create(
            orchestrator_id=orchestrator_id,
            bridge_service=bridge_service,
            container_id=container_id,
            volume_name=volume_name,
            matrix_bot_username=matrix_bot_username,
            as_token=as_token,
            hs_token=hs_token,
            ip=ip,
            port=port,
            owner_matrix_username=owner_matrix_username,
        )

    def get_bridge(
        self,
        as_token: str = None,
        bridge_id: int = None,
        orchestrator_id: str = None,
        owner_username: str = None,
        service: str = None,
    ):
        bridge = None

        if as_token:
            bridge = self.bridges_repository.get_by_as_token(as_token)
        elif orchestrator_id:
            bridge = self.bridges_repository.get_by_orchestrator_id(orchestrator_id)
        elif bridge_id:
            bridge = self.bridges_repository.get_by_id(bridge_id)
        elif owner_username and service:
            bridge = self.bridges_repository.get_by_owner_username_and_service(
                owner_matrix_username=owner_username, bridge_service=service
            )
        else:
            return None

        if not bridge:
            raise ValueError("Bridge bot not found.")

        if bridge.bridge_service == "whatsapp":

            from .appservice.bridge_service import WhatsappBridgeService

            return WhatsappBridgeService(
                as_token=as_token or bridge.as_token,
                bridge_manager_config=self.bridge_manager_config,
            )

        return None

    def list_bridges_by_owner(self, matrix_username):

        bridges = self.bridges_repository.get_by_owner_username(matrix_username)

        return bridges

    def soft_delete_bridge(self, bridge_id):
        """
        Soft delete a bridge by setting deleted_at timestamp.
        Also hard deletes related records from requests, transaction mappings, and room mappings.

        Args:
            bridge_id: The database ID of the bridge to delete
        """

        # Soft delete the bridge
        self.bridges_repository.update(
            id_=bridge_id, deleted_at=datetime.now(timezone.utc)
        )

        # Hard delete related records using repository methods
        requests_repo = RequestsRepository()
        transactions_repo = TransactionMappingsRepository()
        room_mappings_repo = RoomBridgeMappingRepository()

        requests_repo.delete_by_bridge_id(bridge_id)
        transactions_repo.delete_by_bridge_id(bridge_id)
        room_mappings_repo.delete_by_bridge_id(bridge_id)
