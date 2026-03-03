"""
Bridge Registry - High-level bridge management interface.

Provides:
- Bridge CRUD operations
- Caching for performance
- Homeserver management
- Bridge listing and filtering
- Health checks
"""

import logging
from typing import List, Optional, Dict
from datetime import datetime, timezone

from bridge_manager.database.repositories import (
    BridgeRepository,
    HomeserverRepository,
    BridgeManagerWorkerRepository,
    RoomBridgeMappingRepository,
    TransactionMappingRepository,
)
from bridge_manager.database.models import Bridge, Homeserver, BridgeManagerWorker
from bridge_manager.errors import BridgeNotFoundError, HomeserverNotFoundError

logger = logging.getLogger(__name__)


class BridgeRegistry:
    """
    High-level interface for bridge management operations.

    Provides caching and convenience methods for common operations.
    """

    def __init__(self):
        self.bridge_repo = BridgeRepository()
        self.homeserver_repo = HomeserverRepository()
        self.worker_repo = BridgeManagerWorkerRepository()
        self.room_mapping_repo = RoomBridgeMappingRepository()
        self.transaction_mapping_repo = TransactionMappingRepository()

        # In-memory cache for frequently accessed bridges
        # Cache invalidated on updates
        self._bridge_cache: Dict[int, Bridge] = {}
        self._as_token_cache: Dict[str, Bridge] = {}

    # ========================================
    # Bridge Operations
    # ========================================

    def register_bridge(
        self,
        orchestrator_id: str,
        bridge_type: str,
        container_id: str,
        container_name: str,
        volume_name: str,
        host: str,
        port: int,
        as_token: str,
        hs_token: str,
        homeserver_id: str,
        bridge_manager_id: str,
        matrix_bot_username: str,
        owner_matrix_username: str,
        bridge_management_room_id: Optional[str] = None,
    ) -> Bridge:
        """
        Register a new bridge in the database.

        Called by orchestrator after creating bridge container.

        Returns:
            Created Bridge model
        """
        logger.info(f"Registering bridge: {bridge_type} for {owner_matrix_username}")

        bridge = self.bridge_repo.create(
            orchestrator_id=orchestrator_id,
            bridge_type=bridge_type,
            container_id=container_id,
            container_name=container_name,
            volume_name=volume_name,
            host=host,
            port=port,
            as_token=as_token,
            hs_token=hs_token,
            homeserver_id=homeserver_id,
            bridge_manager_id=bridge_manager_id,
            matrix_bot_username=matrix_bot_username,
            owner_matrix_username=owner_matrix_username,
            bridge_management_room_id=bridge_management_room_id,
        )

        # Cache the new bridge
        self._cache_bridge(bridge)

        logger.info(f"Bridge registered successfully: {bridge.id}")
        return bridge

    def get_bridge(self, bridge_id: int) -> Bridge:
        """
        Get bridge by ID.

        Uses cache when possible.

        Raises:
            BridgeNotFoundError: If bridge doesn't exist
        """
        # Check cache first
        if bridge_id in self._bridge_cache:
            return self._bridge_cache[bridge_id]

        # Look up in database
        bridge = self.bridge_repo.get_by_id(bridge_id)
        if not bridge:
            raise BridgeNotFoundError(f"Bridge {bridge_id} not found")

        # Cache it
        self._cache_bridge(bridge)
        return bridge

    def get_bridge_by_as_token(self, as_token: str) -> Optional[Bridge]:
        """
        Get bridge by AS token.

        Uses cache when possible.
        """
        # Check cache first
        if as_token in self._as_token_cache:
            return self._as_token_cache[as_token]

        # Look up in database
        bridge = self.bridge_repo.get_by_as_token(as_token)
        if bridge:
            self._cache_bridge(bridge)

        return bridge

    def get_bridge_by_orchestrator_id(self, orchestrator_id: str) -> Optional[Bridge]:
        """Get bridge by orchestrator ID."""
        return self.bridge_repo.get_by_orchestrator_id(orchestrator_id)

    def get_bridge_by_port(self, port: int) -> Optional[Bridge]:
        """
        Get bridge by its port number.

        Args:
            port: Port number the bridge is listening on

        Returns:
            Bridge model if found, None otherwise
        """
        return self.bridge_repo.get_by_port(port)

    def list_bridges_by_owner(self, owner_matrix_username: str) -> List[Bridge]:
        """
        List all active bridges owned by a user.

        Args:
            owner_matrix_username: Matrix user ID

        Returns:
            List of Bridge models
        """
        bridges = self.bridge_repo.list_by_owner(owner_matrix_username)

        # Cache all bridges
        for bridge in bridges:
            self._cache_bridge(bridge)

        return bridges

    def list_bridges_by_homeserver(self, homeserver_id: str) -> List[Bridge]:
        """
        List all active bridges for a homeserver.

        Args:
            homeserver_id: Homeserver ID

        Returns:
            List of Bridge models
        """
        bridges = self.bridge_repo.list_by_homeserver(homeserver_id)

        # Cache all bridges
        for bridge in bridges:
            self._cache_bridge(bridge)

        return bridges

    def update_bridge_status(self, bridge_id: int, status: str) -> bool:
        """
        Update bridge status.

        Args:
            bridge_id: Bridge ID
            status: New status (active, inactive, provisioning, error)

        Returns:
            True if updated successfully
        """
        success = self.bridge_repo.update_status(bridge_id, status)

        if success:
            # Invalidate cache
            self._invalidate_bridge_cache(bridge_id)
            logger.info(f"Bridge {bridge_id} status updated to {status}")

        return success

    def delete_bridge(self, bridge_id: int) -> bool:
        """
        Soft delete a bridge.

        Marks as deleted but keeps in database for audit trail.

        Args:
            bridge_id: Bridge ID

        Returns:
            True if deleted successfully
        """
        success = self.bridge_repo.soft_delete(bridge_id)

        if success:
            # Invalidate cache
            self._invalidate_bridge_cache(bridge_id)
            logger.info(f"Bridge {bridge_id} deleted")

        return success

    # ========================================
    # Room and Transaction Mapping
    # ========================================

    def get_bridge_by_room_id(self, room_id: str) -> Optional[Bridge]:
        """
        Get bridge associated with a room.

        Args:
            room_id: Matrix room ID

        Returns:
            Bridge model if mapping exists
        """
        return self.room_mapping_repo.get_bridge_by_room_id(room_id)

    def get_bridge_by_transaction_id(self, transaction_id: str) -> Optional[Bridge]:
        """
        Get bridge associated with a transaction.

        Args:
            transaction_id: Transaction ID

        Returns:
            Bridge model if mapping exists
        """
        return self.transaction_mapping_repo.get_bridge_by_transaction_id(
            transaction_id
        )

    def cache_room_mapping(self, room_id: str, bridge_id: int):
        """
        Create room→bridge mapping for fast lookups.

        Args:
            room_id: Matrix room ID
            bridge_id: Bridge ID
        """
        try:
            self.room_mapping_repo.create(room_id, bridge_id)
            logger.debug(f"Cached room mapping: {room_id} → bridge {bridge_id}")
        except Exception as e:
            logger.warning(f"Failed to cache room mapping: {e}")

    def cache_transaction_mapping(self, transaction_id: str, bridge_id: int):
        """
        Create transaction→bridge mapping for fast lookups.

        Args:
            transaction_id: Transaction ID
            bridge_id: Bridge ID
        """
        try:
            self.transaction_mapping_repo.create(transaction_id, bridge_id)
            logger.debug(
                f"Cached transaction mapping: {transaction_id} → bridge {bridge_id}"
            )
        except Exception as e:
            logger.warning(f"Failed to cache transaction mapping: {e}")

    def delete_room_mapping(self, room_id: str) -> bool:
        """
        Delete room→bridge mapping.

        Args:
            room_id: Matrix room ID

        Returns:
            True if deleted successfully
        """
        return self.room_mapping_repo.delete_by_room_id(room_id)

    # ========================================
    # Homeserver Operations
    # ========================================

    def register_homeserver(
        self,
        id: str,
        name: str,
        url: str,
        hs_token: str,
    ) -> Homeserver:
        """
        Register a homeserver.

        Args:
            id: Homeserver ID (e.g., "hs-001")
            name: Homeserver domain (e.g., "matrix.example.com")
            url: Homeserver URL (e.g., "http://localhost:8008")
            hs_token: HS token for authentication

        Returns:
            Created Homeserver model
        """
        logger.info(f"Registering homeserver: {id} ({name})")
        return self.homeserver_repo.create(
            id=id,
            name=name,
            url=url,
            hs_token=hs_token,
        )

    def get_homeserver(self, homeserver_id: str) -> Homeserver:
        """
        Get homeserver by ID.

        Args:
            homeserver_id: Homeserver ID

        Returns:
            Homeserver model

        Raises:
            HomeserverNotFoundError: If homeserver doesn't exist
        """
        homeserver = self.homeserver_repo.get_by_id(homeserver_id)
        if not homeserver:
            raise HomeserverNotFoundError(f"Homeserver {homeserver_id} not found")
        return homeserver

    def get_homeserver_by_hs_token(self, hs_token: str) -> Optional[Homeserver]:
        """Get homeserver by HS token."""
        return self.homeserver_repo.get_by_hs_token(hs_token)

    def list_homeservers(self) -> List[Homeserver]:
        """List all registered homeservers."""
        return self.homeserver_repo.list_all()

    # ========================================
    # Bridge Manager Worker Operations
    # ========================================

    def register_worker(
        self,
        instance_id: str,
        host: str,
        port: int,
        homeserver_id: str,
    ) -> BridgeManagerWorker:
        """
        Register a bridge manager worker instance.

        Args:
            instance_id: Worker instance ID (e.g., "bm-001")
            host: Worker host
            port: Worker port
            homeserver_id: Associated homeserver

        Returns:
            Created worker model
        """
        logger.info(f"Registering bridge manager worker: {instance_id}")
        return self.worker_repo.create(
            instance_id=instance_id,
            host=host,
            port=port,
            homeserver_id=homeserver_id,
        )

    def update_worker_heartbeat(self, instance_id: str) -> bool:
        """
        Update worker heartbeat timestamp.

        Should be called periodically by each worker.

        Args:
            instance_id: Worker instance ID

        Returns:
            True if updated successfully
        """
        return self.worker_repo.update_heartbeat(instance_id)

    def list_workers_by_homeserver(
        self, homeserver_id: str
    ) -> List[BridgeManagerWorker]:
        """
        List all workers for a homeserver.

        Args:
            homeserver_id: Homeserver ID

        Returns:
            List of worker models
        """
        return self.worker_repo.list_by_homeserver(homeserver_id)

    # ========================================
    # Cache Management
    # ========================================

    def _cache_bridge(self, bridge: Bridge):
        """Add bridge to cache."""
        self._bridge_cache[bridge.id] = bridge
        self._as_token_cache[bridge.as_token] = bridge

    def _invalidate_bridge_cache(self, bridge_id: int):
        """Remove bridge from cache."""
        if bridge_id in self._bridge_cache:
            bridge = self._bridge_cache[bridge_id]
            # Remove from both caches
            del self._bridge_cache[bridge_id]
            if bridge.as_token in self._as_token_cache:
                del self._as_token_cache[bridge.as_token]

    def clear_cache(self):
        """Clear all caches."""
        self._bridge_cache.clear()
        self._as_token_cache.clear()
        logger.debug("Bridge cache cleared")

    # ========================================
    # Health Check
    # ========================================

    def get_bridge_health_summary(self, homeserver_id: Optional[str] = None) -> Dict:
        """
        Get health summary of bridges.

        Args:
            homeserver_id: Optional filter by homeserver

        Returns:
            Dict with bridge counts by status
        """
        if homeserver_id:
            bridges = self.list_bridges_by_homeserver(homeserver_id)
        else:
            # Get all bridges (would need a new repo method)
            bridges = []
            for hs in self.list_homeservers():
                bridges.extend(self.list_bridges_by_homeserver(hs.id))

        # Count by status
        status_counts = {}
        for bridge in bridges:
            status = bridge.status
            status_counts[status] = status_counts.get(status, 0) + 1

        return {
            "total": len(bridges),
            "by_status": status_counts,
            "homeserver_id": homeserver_id,
        }
