"""
Bridge Router - Advanced bridge identification system.

Implements 8 discovery methods to identify which bridge a request belongs to:
1. AUTH_TOKEN: Extract AS token from Authorization header
2. QUERY_USER_ID: Parse user_id from query parameters
3. PATH_USERNAME: Extract username from request path
4. TRANSACTION_ID: Look up cached transaction→bridge mapping
5. TRANSACTION_EVENTS: Parse events in transaction body and cache mapping
6. ROOM_ID: Look up room→bridge mapping
7. BODY_USERNAME: Search for usernames in request body
8. OWNER_USERNAME: Find bridges owned by user (last resort)

Strategies are tried in order of reliability.
"""

import re
import logging
from typing import Optional, Tuple, Dict, Any, List

from config import BRIDGE_MANAGER_CONFIG
from bridge_manager.appservice.models import BridgeDiscoveryMethod, RequestSource
from bridge_manager.database.models import Bridge
from bridge_manager.database.repositories import (
    BridgeRepository,
    RoomBridgeMappingRepository,
    TransactionMappingRepository,
)
from bridge_manager.errors import BridgeNotFoundError

logger = logging.getLogger(__name__)


class BridgeRouter:
    """
    Routes requests to appropriate bridges using multiple identification strategies.

    The router tries each strategy in order until one successfully identifies a bridge.
    Caches transaction and room mappings for improved performance.
    """

    def __init__(self):
        self.bridge_repo = BridgeRepository()
        self.room_mapping_repo = RoomBridgeMappingRepository()
        self.transaction_mapping_repo = TransactionMappingRepository()

        # Compile username pattern regex once
        self.username_pattern = re.compile(BRIDGE_MANAGER_CONFIG.username_pattern)

        # Resolution strategies in priority order (most reliable first)
        self._resolvers = [
            (self._from_auth_token, BridgeDiscoveryMethod.AUTH_TOKEN),
            (self._from_query_user_id, BridgeDiscoveryMethod.QUERY_USER_ID),
            (self._from_path_username, BridgeDiscoveryMethod.PATH_USERNAME),
            (self._from_transaction_id, BridgeDiscoveryMethod.TRANSACTION_ID),
            (self._from_transaction_events, BridgeDiscoveryMethod.TRANSACTION_EVENTS),
            (self._from_room_id, BridgeDiscoveryMethod.ROOM_ID),
            (self._from_body_username, BridgeDiscoveryMethod.BODY_USERNAME),
            (self._from_owner_username, BridgeDiscoveryMethod.OWNER_USERNAME),
        ]

    def identify_bridge(
        self,
        source: RequestSource,
        headers: Dict[str, str],
        path: str,
        body: Optional[Dict[str, Any]] = None,
        query_params: Optional[Dict[str, str]] = None,
    ) -> Tuple[Bridge, BridgeDiscoveryMethod]:
        """
        Attempt to identify which bridge a request belongs to.

        Tries each resolution strategy in order until one succeeds.

        Args:
            source: Whether request is from homeserver or bridge
            headers: Request headers (may contain auth token)
            path: Request path (may contain username or transaction ID)
            body: Request body (may contain username, room_id, events)
            query_params: Query parameters (may contain user_id)

        Returns:
            Tuple of (Bridge model, discovery method used)

        Raises:
            BridgeNotFoundError: If no strategy successfully identifies a bridge
        """
        logger.debug(f"Attempting to identify bridge for {source} request to {path}")

        # Try each resolver in order
        for resolver, method in self._resolvers:
            try:
                bridge = resolver(headers, path, body, query_params)
                if bridge:
                    logger.info(
                        f"Bridge identified using {method.value}: {bridge.id} ({bridge.bridge_type})"
                    )
                    return bridge, method
            except Exception as e:
                logger.debug(f"Resolver {method.value} failed: {e}")
                continue

        # No resolver succeeded
        logger.error(f"Failed to identify bridge for request to {path}")
        raise BridgeNotFoundError(
            f"Could not identify bridge for {source} request to {path}"
        )

    def _from_auth_token(
        self,
        headers: Dict[str, str],
        path: str,
        body: Optional[Dict[str, Any]],
        query_params: Optional[Dict[str, str]],
    ) -> Optional[Bridge]:
        """
        Extract AS token from Authorization header and find matching bridge.

        Most reliable for bridge→homeserver requests.

        ALI NOTE: I don't think this will ever work because the homeserver sends requests using the appservices AS token. The HS is not aware of the bridges.
        """
        auth = headers.get("authorization", "")
        if not auth.startswith("Bearer "):
            return None

        token = auth[7:]  # Remove "Bearer " prefix

        # Look up bridge by AS token
        bridge = self.bridge_repo.get_by_as_token(token)
        return bridge

    def _from_query_user_id(
        self,
        headers: Dict[str, str],
        path: str,
        body: Optional[Dict[str, Any]],
        query_params: Optional[Dict[str, str]],
    ) -> Optional[Bridge]:
        """
        Parse user_id from query parameters.

        Used for AS user queries: /_matrix/app/v1/users/{userId}?user_id=@...
        """
        if not query_params or "user_id" not in query_params:
            return None

        username = query_params["user_id"]
        return self._extract_bridge_from_username(username)

    def _from_path_username(
        self,
        headers: Dict[str, str],
        path: str,
        body: Optional[Dict[str, Any]],
        query_params: Optional[Dict[str, str]],
    ) -> Optional[Bridge]:
        """
        Extract username from request path.

        Example: /_matrix/app/v1/users/@_bm_whatsapp_abc123_user:matrix.org
        """
        match = self.username_pattern.search(path)
        if not match:
            return None

        bridge_id = match.group("bridge_id")
        return self.bridge_repo.get_by_orchestrator_id(bridge_id)

    def _from_transaction_id(
        self,
        headers: Dict[str, str],
        path: str,
        body: Optional[Dict[str, Any]],
        query_params: Optional[Dict[str, str]],
    ) -> Optional[Bridge]:
        """
        Look up cached transaction→bridge mapping.

        Used for transaction endpoints: /_matrix/app/v1/transactions/{txnId}
        """
        if "_matrix/app/v1/transactions/" not in path:
            return None

        # Extract transaction ID from path
        parts = path.split("/")
        if len(parts) < 5:
            return None

        txn_id = parts[-1]

        # Look up cached mapping
        return self.transaction_mapping_repo.get_bridge_by_transaction_id(txn_id)

    def _from_transaction_events(
        self,
        headers: Dict[str, str],
        path: str,
        body: Optional[Dict[str, Any]],
        query_params: Optional[Dict[str, str]],
    ) -> Optional[Bridge]:
        """
        Parse events in transaction body to extract room_id or sender.

        Also caches the transaction→bridge mapping for future requests.
        Used when transaction is first seen.
        """
        if not body or "events" not in body:
            return None

        events = body.get("events", [])
        if not events:
            return None

        # Get first event
        event = events[0]
        bridge = None

        # Try room_id first (most reliable)
        if "room_id" in event:
            room_id = event["room_id"]
            bridge = self.room_mapping_repo.get_bridge_by_room_id(room_id)

        # Fall back to sender username
        if not bridge and "sender" in event:
            sender = event["sender"]
            bridge = self._extract_bridge_from_username(sender)

        # Cache transaction mapping if we found a bridge
        if bridge and "_matrix/app/v1/transactions/" in path:
            try:
                parts = path.split("/")
                if len(parts) >= 5:
                    txn_id = parts[-1]
                    self.transaction_mapping_repo.create(txn_id, bridge.id)
                    logger.debug(
                        f"Cached transaction mapping: {txn_id} → bridge {bridge.id}"
                    )
            except Exception as e:
                logger.warning(f"Failed to cache transaction mapping: {e}")

        return bridge

    def _from_room_id(
        self,
        headers: Dict[str, str],
        path: str,
        body: Optional[Dict[str, Any]],
        query_params: Optional[Dict[str, str]],
    ) -> Optional[Bridge]:
        """
        Look up room→bridge mapping from database.

        Fast lookup for requests that include room_id in body.
        """
        if not body or "room_id" not in body:
            return None

        room_id = body["room_id"]
        return self.room_mapping_repo.get_bridge_by_room_id(room_id)

    def _from_body_username(
        self,
        headers: Dict[str, str],
        path: str,
        body: Optional[Dict[str, Any]],
        query_params: Optional[Dict[str, str]],
    ) -> Optional[Bridge]:
        """
        Search for usernames in common body fields.

        Checks fields like user_id, sender, state_key, creator, etc.
        """
        if not body:
            return None

        # Common fields that might contain usernames
        username_fields = [
            "user_id",
            "sender",
            "state_key",
            "creator",
            "target",
            "inviter",
        ]

        for field in username_fields:
            if field in body:
                value = body[field]
                if isinstance(value, str) and value.startswith("@"):
                    bridge = self._extract_bridge_from_username(value)
                    if bridge:
                        return bridge

        return None

    def _from_owner_username(
        self,
        headers: Dict[str, str],
        path: str,
        body: Optional[Dict[str, Any]],
        query_params: Optional[Dict[str, str]],
    ) -> Optional[Bridge]:
        """
        Last resort: find bridges owned by a user.

        This is unreliable if user has multiple bridges of same type.
        Returns first active bridge found.
        """
        if not body or "user_id" not in body:
            return None

        owner = body["user_id"]
        bridges = self.bridge_repo.list_by_owner(owner)

        if bridges:
            # Return first active bridge
            active_bridges = [b for b in bridges if b.status == "active"]
            if active_bridges:
                logger.warning(
                    f"Using owner_username fallback for {owner}: "
                    f"found {len(active_bridges)} bridges, using first one"
                )
                return active_bridges[0]

        return None

    def _extract_bridge_from_username(self, username: str) -> Optional[Bridge]:
        """
        Parse username pattern to extract bridge ID and look up bridge.

        Pattern: @_bm_<bridge_type>_<bridge_id>_<username>:<homeserver>
        Example: @_bm_whatsapp_abc123_user:matrix.org

        Args:
            username: Matrix username to parse

        Returns:
            Bridge model if found, None otherwise
        """
        match = self.username_pattern.match(username)
        if not match:
            return None

        bridge_id = match.group("bridge_id")
        return self.bridge_repo.get_by_orchestrator_id(bridge_id)

    def cache_room_mapping(self, room_id: str, bridge_id: int):
        """
        Cache room→bridge mapping for fast future lookups.

        Should be called when a new room is created or discovered.

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
        Cache transaction→bridge mapping for fast future lookups.

        Should be called when a transaction is successfully routed.

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

    def get_bridge_by_id(self, bridge_id: int) -> Optional[Bridge]:
        """
        Direct lookup by bridge ID.

        Args:
            bridge_id: Bridge ID

        Returns:
            Bridge model if found
        """
        return self.bridge_repo.get_by_id(bridge_id)

    def get_bridge_by_orchestrator_id(self, orchestrator_id: str) -> Optional[Bridge]:
        """
        Direct lookup by orchestrator ID.

        Args:
            orchestrator_id: Orchestrator-assigned bridge ID

        Returns:
            Bridge model if found
        """
        return self.bridge_repo.get_by_orchestrator_id(orchestrator_id)

    def validate_username_pattern(self, username: str) -> bool:
        """
        Check if username matches bridge manager pattern.

        Args:
            username: Matrix username

        Returns:
            True if matches pattern, False otherwise
        """
        return self.username_pattern.match(username) is not None

    def extract_bridge_info_from_username(
        self, username: str
    ) -> Optional[Dict[str, str]]:
        """
        Parse username and extract all components.

        Args:
            username: Matrix username

        Returns:
            Dict with bridge_type, bridge_id, username, homeserver or None
        """
        match = self.username_pattern.match(username)
        if not match:
            return None

        return {
            "bridge_type": match.group("bridge_type"),
            "bridge_id": match.group("bridge_id"),
            "username": match.group("username"),
            "homeserver": match.group("homeserver"),
        }
