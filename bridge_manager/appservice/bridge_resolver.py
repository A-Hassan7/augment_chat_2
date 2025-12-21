"""
Bridge resolution system for identifying which bridge a request belongs to.

Provides a clean, extensible architecture for discovering bridges through multiple
strategies (auth token, path username, transaction ID, body username, etc.).
"""

from __future__ import annotations
import re
import json
import logging
from typing import TYPE_CHECKING, Optional, Dict, Any
from enum import Enum

from ..config import BridgeManagerConfig
from ..bridge_registry import BridgeRegistry
from ..database.repositories import TransactionMappingsRepository

if TYPE_CHECKING:
    from .bridge_service import BridgeService
    from .models import RequestSource

logger = logging.getLogger(__name__)


class BridgeResolutionMethod(Enum):
    """Tracks which method successfully resolved a bridge"""

    AUTH_TOKEN = "auth_token"
    QUERY_USER_ID = "query_user_id"
    PATH_USERNAME = "path_username"
    TRANSACTION_ID = "transaction_id"
    TRANSACTION_EVENTS = "transaction_events"
    ROOM_ID = "room_id"
    BODY_USERNAME = "body_username"
    OWNER_USERNAME = "owner_username"
    UNKNOWN = "unknown"


class BridgeNotFoundError(ValueError):
    """Raised when no bridge can be resolved for a request"""

    pass


class BridgeResolver:
    """
    Resolves which bridge a request belongs to using multiple strategies.

    Resolution strategies are tried in order of reliability:
    1. Auth token from headers (most reliable for bridge→homeserver)
    2. Username in request path (reliable for homeserver→bridge)
    3. Transaction ID mapping (for ping/transaction endpoints)
    4. Username in request body (fallback)
    5. Owner username + service type (last resort)
    """

    def __init__(self, bridge_manager_config: BridgeManagerConfig):
        self.config = bridge_manager_config
        self.registry = BridgeRegistry(bridge_manager_config)

        # Order matters - most reliable methods first
        self._resolvers = [
            self._from_auth_token,
            self._from_query_user_id,
            self._from_path_username,
            self._from_transaction_id,
            self._from_transaction_events,
            self._from_room_id,
            self._from_body_username,
            self._from_owner_username,
        ]

    def resolve(
        self,
        source: RequestSource,
        headers: Dict[str, Any],
        path: str,
        body_json: Optional[Dict[str, Any]] = None,
        query_params: Optional[Dict[str, Any]] = None,
    ) -> tuple[Optional[BridgeService], BridgeResolutionMethod]:
        """
        Attempt to resolve a bridge using available strategies.

        Args:
            source: Whether request is from homeserver or bridge
            headers: Request headers (may contain auth token)
            path: Request path (may contain username)
            body_json: Request body (may contain username or transaction ID)
            query_params: Query parameters (may contain user_id for AS impersonation)

        Returns:
            Tuple of (bridge_service, resolution_method)

        Raises:
            BridgeNotFoundError: If no bridge can be resolved
        """
        from .models import RequestSource

        logger.debug(
            f"Attempting to resolve bridge for {source.value} request to {path}"
        )

        for resolver in self._resolvers:
            resolver_name = resolver.__name__
            logger.debug(f"Trying resolver: {resolver_name}")
            try:
                bridge = resolver(source, headers, path, body_json, query_params)
                if bridge:
                    method = self._get_method_name(resolver)
                    logger.info(
                        f"Bridge resolved via {method.value}: bridge_id={bridge.bridge_id}"
                    )
                    return bridge, method
                else:
                    logger.debug(f"{resolver_name} returned None")
            except Exception as e:
                logger.warning(f"{resolver_name} failed with exception: {e}")

        # No resolver succeeded
        logger.error(f"Failed to resolve bridge for {source.value} request to {path}")
        raise BridgeNotFoundError(
            f"Could not identify bridge for request. Source: {source.value}, Path: {path}"
        )

    def _from_auth_token(
        self,
        source: RequestSource,
        headers: Dict[str, Any],
        path: str,
        body_json: Optional[Dict[str, Any]],
        query_params: Optional[Dict[str, Any]] = None,
    ) -> Optional[BridgeService]:
        """
        Resolve bridge from Authorization header token.

        Most reliable for requests originating from bridges (bridge→homeserver flow).
        Each bridge has a unique as_token that identifies it.
        """
        from .models import RequestSource

        # Only applicable for bridge-originated requests
        if source != RequestSource.BRIDGE:
            return None

        as_token = self._extract_auth_token(headers)
        if not as_token:
            logger.debug("No auth token found in headers")
            return None

        try:
            bridge = self.registry.get_bridge(as_token=as_token)
            return bridge
        except ValueError as e:
            logger.debug(f"Bridge not found for as_token: {e}")
            return None

    def _from_query_user_id(
        self,
        source: RequestSource,
        headers: Dict[str, Any],
        path: str,
        body_json: Optional[Dict[str, Any]],
        query_params: Optional[Dict[str, Any]] = None,
    ) -> Optional[BridgeService]:
        """
        Resolve bridge from user_id query parameter.

        Bridges use ?user_id=@_bridge_manager__...__username:homeserver for AS impersonation.
        Extract bridge_id from the encoded username in the query parameter.
        """
        if not query_params or "user_id" not in query_params:
            logger.debug("No query_params or user_id not in query_params")
            return None

        user_id = query_params.get("user_id", "")
        if not user_id:
            logger.debug("user_id is empty")
            return None

        # Check if user_id matches the namespace pattern
        username_pattern = self.config.username_regex
        match = re.match(username_pattern, user_id)

        if not match:
            logger.debug(f"user_id query param doesn't match pattern: {user_id}")
            logger.debug(f"Expected pattern: {username_pattern}")
            return None

        try:
            orchestrator_id = match.group("bridge_id")
            logger.info(
                f"Extracted orchestrator_id from query user_id: {orchestrator_id}"
            )
            bridge = self.registry.get_bridge(orchestrator_id=orchestrator_id)
            logger.info(
                f"Resolved bridge from query user_id: {user_id} -> bridge_id={bridge.bridge_id}"
            )
            return bridge
        except (ValueError, KeyError) as e:
            logger.warning(
                f"Failed to resolve bridge from query user_id {user_id}: {e}"
            )
            return None

    def _from_path_username(
        self,
        source: RequestSource,
        headers: Dict[str, Any],
        path: str,
        body_json: Optional[Dict[str, Any]],
        query_params: Optional[Dict[str, Any]] = None,
    ) -> Optional[BridgeService]:
        """
        Resolve bridge from encoded username in request path.

        Usernames follow pattern: @_bridge_manager__whatsapp_1__username:homeserver
        Extract bridge_id from the encoded username.
        """
        from .models import RequestSource

        # Only applicable for homeserver-originated requests
        if source != RequestSource.HOMESERVER:
            return None

        username_pattern = rf".*/{self.config.username_regex}"
        match = re.match(username_pattern, path)

        if not match:
            logger.debug("No encoded username found in path")
            return None

        try:
            bridge_id = match.group("bridge_id")
            bridge = self.registry.get_bridge(bridge_id=bridge_id)
            return bridge
        except (ValueError, KeyError) as e:
            logger.debug(f"Failed to resolve bridge from path username: {e}")
            return None

    def _from_transaction_id(
        self,
        source: RequestSource,
        headers: Dict[str, Any],
        path: str,
        body_json: Optional[Dict[str, Any]],
        query_params: Optional[Dict[str, Any]] = None,
    ) -> Optional[BridgeService]:
        """
        Resolve bridge from transaction ID mapping.

        Transaction IDs are mapped to bridges when bridges send ping requests.
        Homeserver references these transaction IDs in subsequent requests.
        """
        from .models import RequestSource

        # Only applicable for homeserver-originated requests
        if source != RequestSource.HOMESERVER:
            return None

        # Try finding transaction ID in path (e.g., /_matrix/app/v1/transactions/123)
        txn_id_match = re.match(r"_matrix/app/v1/transactions/(?P<txn_id>\w+)", path)
        txn_id_from_path = txn_id_match.group("txn_id") if txn_id_match else None

        # Try finding transaction ID in body
        txn_id_from_body = body_json.get("transaction_id") if body_json else None

        txn_id = txn_id_from_path or txn_id_from_body

        if not txn_id:
            logger.debug("No transaction ID found in path or body")
            return None

        try:
            transactions_repo = TransactionMappingsRepository()
            mapping = transactions_repo.get_bridge_by_transaction(transaction_id=txn_id)

            if not mapping or not mapping.bridge_as_token:
                logger.debug(f"No bridge mapping found for transaction_id: {txn_id}")
                return None

            bridge = self.registry.get_bridge(as_token=mapping.bridge_as_token)
            return bridge
        except (ValueError, AttributeError) as e:
            logger.debug(f"Failed to resolve bridge from transaction ID: {e}")
            return None

    def _from_transaction_events(
        self,
        source: RequestSource,
        headers: Dict[str, Any],
        path: str,
        body_json: Optional[Dict[str, Any]],
        query_params: Optional[Dict[str, Any]] = None,
    ) -> Optional[BridgeService]:
        """
        Resolve bridge from transaction events by extracting bridge usernames.

        This method handles /_matrix/app/v1/transactions/{txnId} requests for ALL event types
        by analyzing the events array. It checks all possible paths where bridge usernames
        can appear according to Matrix AS API spec:

        Event-level paths (all event types):
        1. events[].sender - Most common: when bridge sends ANY event (messages, state, etc.)
        2. events[].state_key - For state events where bridge user is the target
        3. events[].user_id - Legacy/alternative user reference field

        Content-level paths (event-specific):
        4. events[].content.* - Recursively search for usernames in event content
           - m.room.message: mentions, replies
           - m.room.member: membership changes
           - m.call.*: VoIP events with user references

        Room state context:
        5. events[].invite_room_state[].state_key - Bridge users in room member list
        6. events[].unsigned.invite_room_state[].state_key - Same in unsigned field
        7. events[].unsigned.prev_content.* - Previous state content

        Per Matrix spec: "Events will be sent to the AS if this user is the target
        of the event, or is a joined member of the room where the event occurred."

        This covers:
        - m.room.message (bridge sends messages)
        - m.room.member (invites, joins, leaves, kicks)
        - m.room.power_levels (power level changes)
        - m.room.name, m.room.topic, m.room.avatar (room state changes)
        - m.call.* (VoIP events)
        - m.reaction (reactions to messages)
        - Any custom event types
        """
        from .models import RequestSource

        # Only applicable for homeserver-originated requests
        if source != RequestSource.HOMESERVER:
            return None

        # Only for transaction endpoints
        if not path.startswith("_matrix/app/v1/transactions/"):

            return None

        if not body_json or "events" not in body_json:
            logger.debug("No events array found in transaction body")
            return None

        events = body_json.get("events", [])
        if not events:
            return None

        # Extract all potential bridge usernames from events
        bridge_usernames = set()
        namespace_prefix = f"@{self.config.NAMESPACE}"

        for event in events:
            event_type = event.get("type", "unknown")

            # === PRIMARY PATHS (checked for all event types) ===

            # Path 1: sender - Most common, works for ALL events
            # When bridge sends messages, state changes, reactions, etc.
            sender = event.get("sender", "")
            if sender.startswith(namespace_prefix):
                bridge_usernames.add(sender)
                logger.debug(
                    f"Found bridge username in sender ({event_type}): {sender}"
                )

            # Path 2: state_key - For state events (m.room.member, m.room.power_levels, etc.)
            # When bridge user is the target of a state change
            state_key = event.get("state_key", "")
            if state_key.startswith(namespace_prefix):
                bridge_usernames.add(state_key)
                logger.debug(
                    f"Found bridge username in state_key ({event_type}): {state_key}"
                )

            # Path 3: user_id - Legacy/alternative field
            user_id = event.get("user_id", "")
            if user_id.startswith(namespace_prefix):
                bridge_usernames.add(user_id)
                logger.debug(
                    f"Found bridge username in user_id ({event_type}): {user_id}"
                )

            # === CONTENT-LEVEL PATHS (event-specific) ===

            # Path 4: Recursively search event content for usernames
            # Handles mentions, replies, custom fields, etc.
            content = event.get("content", {})
            if content:
                content_usernames = self._extract_usernames_from_content(
                    content, namespace_prefix, event_type
                )
                bridge_usernames.update(content_usernames)

            # === ROOM STATE CONTEXT PATHS ===

            # Path 5: invite_room_state members (for invites)
            invite_room_state = event.get("invite_room_state", [])
            for state_event in invite_room_state:
                # Check both state_key and sender in invite state
                member_state_key = state_event.get("state_key", "")
                if member_state_key.startswith(namespace_prefix):
                    bridge_usernames.add(member_state_key)
                    logger.debug(
                        f"Found bridge username in invite_room_state.state_key: {member_state_key}"
                    )

                member_sender = state_event.get("sender", "")
                if member_sender.startswith(namespace_prefix):
                    bridge_usernames.add(member_sender)
                    logger.debug(
                        f"Found bridge username in invite_room_state.sender: {member_sender}"
                    )

            # Path 6: unsigned.invite_room_state members
            unsigned = event.get("unsigned", {})
            unsigned_invite_state = unsigned.get("invite_room_state", [])
            for state_event in unsigned_invite_state:
                member_state_key = state_event.get("state_key", "")
                if member_state_key.startswith(namespace_prefix):
                    bridge_usernames.add(member_state_key)
                    logger.debug(
                        f"Found bridge username in unsigned.invite_room_state: {member_state_key}"
                    )

            # Path 7: unsigned.prev_content (previous state for state events)
            prev_content = unsigned.get("prev_content", {})
            if prev_content:
                prev_usernames = self._extract_usernames_from_content(
                    prev_content, namespace_prefix, f"{event_type}.prev_content"
                )
                bridge_usernames.update(prev_usernames)

        if not bridge_usernames:
            logger.debug("No bridge usernames found in transaction events")
            return None

        # Use the first found username to resolve the bridge
        username = list(bridge_usernames)[0]
        logger.info(
            f"Extracted {len(bridge_usernames)} bridge username(s) from transaction events, using: {username}"
        )

        try:
            # Extract orchestrator_id from encoded username
            username_pattern = self.config.username_regex
            match = re.match(username_pattern, username)
            if not match:
                logger.debug(f"Username doesn't match expected pattern: {username}")
                return None

            orchestrator_id = match.group(
                "bridge_id"
            )  # This is actually the orchestrator_id in the username
            bridge = self.registry.get_bridge(orchestrator_id=orchestrator_id)
            return bridge
        except (ValueError, KeyError) as e:
            logger.debug(f"Failed to resolve bridge from transaction events: {e}")
            return None

    def _from_room_id(
        self,
        source: RequestSource,
        headers: Dict[str, Any],
        path: str,
        body_json: Optional[Dict[str, Any]],
        query_params: Optional[Dict[str, Any]] = None,
    ) -> Optional[BridgeService]:
        """
        Resolve bridge from room_id in transaction events.

        This method handles /_matrix/app/v1/transactions/{txnId} requests where
        we don't find bridge usernames in the events, but we can look up which
        bridge is associated with a room based on previous interactions.

        This is useful for messages sent by regular users (not bridge users)
        in bridged rooms, where the only identifier is the room_id.
        """
        from ..database.repositories import RoomBridgeMappingRepository
        from .models import RequestSource

        # Only applicable for homeserver-originated requests
        if source != RequestSource.HOMESERVER:
            return None

        # Only for transaction endpoints
        if not path.startswith("_matrix/app/v1/transactions/"):
            return None

        if not body_json or "events" not in body_json:
            return None

        events = body_json.get("events", [])
        if not events:
            return None

        # Extract room_ids from events
        room_ids = set()
        for event in events:
            room_id = event.get("room_id")
            if room_id:
                room_ids.add(room_id)

        if not room_ids:
            logger.debug("No room_ids found in transaction events")
            return None

        # Try to find a bridge mapping for any of the room_ids
        room_bridge_repo = RoomBridgeMappingRepository()
        for room_id in room_ids:
            bridge_id = room_bridge_repo.get_bridge_by_room_id(room_id)
            if bridge_id:
                logger.info(
                    f"Resolved bridge from room_id mapping: room={room_id}, bridge_id={bridge_id}"
                )
                # Get the bridge from registry using bridge_id
                try:
                    bridge = self.registry.get_bridge(bridge_id=bridge_id)
                    logger.info(
                        f"Successfully retrieved bridge service for bridge_id={bridge_id}"
                    )
                    return bridge
                except Exception as e:
                    logger.error(
                        f"Failed to get bridge from registry for bridge_id={bridge_id}: {e}"
                    )
                    return None

        logger.debug(f"No bridge mapping found for room_ids: {room_ids}")
        return None

    def _extract_usernames_from_content(
        self, content: Dict[str, Any], namespace_prefix: str, context: str = ""
    ) -> set:
        """
        Recursively extract bridge usernames from event content.

        Handles various content structures:
        - Direct user_id fields
        - Mentions in formatted_body (HTML)
        - Reply references (m.relates_to)
        - Custom fields in any event type

        Args:
            content: Event content dictionary
            namespace_prefix: Bridge namespace to match (e.g., "@_bridge_manager__")
            context: Description of where we're searching (for logging)

        Returns:
            Set of found bridge usernames
        """
        usernames = set()

        # Common fields that might contain usernames
        direct_fields = ["user_id", "sender", "creator", "target", "kick", "ban"]

        for field in direct_fields:
            if field in content and isinstance(content[field], str):
                if content[field].startswith(namespace_prefix):
                    usernames.add(content[field])
                    logger.debug(
                        f"Found bridge username in content.{field} ({context}): {content[field]}"
                    )

        # Check for mentions in formatted_body (HTML content)
        formatted_body = content.get("formatted_body", "")
        if formatted_body and isinstance(formatted_body, str):
            # Extract usernames from HTML mentions: <a href="https://matrix.to/#/@user:server">
            mention_pattern = rf"https://matrix\.to/#/({namespace_prefix}[^\"'>]+)"
            mentions = re.findall(mention_pattern, formatted_body)
            for mention in mentions:
                usernames.add(mention)
                logger.debug(
                    f"Found bridge username in formatted_body mention ({context}): {mention}"
                )

        # Check for reply/thread references (m.relates_to)
        relates_to = content.get("m.relates_to", {})
        if relates_to and isinstance(relates_to, dict):
            # Check in_reply_to
            in_reply_to = relates_to.get("m.in_reply_to", {})
            if in_reply_to:
                reply_sender = in_reply_to.get("sender", "")
                if reply_sender.startswith(namespace_prefix):
                    usernames.add(reply_sender)
                    logger.debug(
                        f"Found bridge username in reply reference ({context}): {reply_sender}"
                    )

        # Recursively search nested dictionaries and lists
        for key, value in content.items():
            if isinstance(value, dict):
                nested_usernames = self._extract_usernames_from_content(
                    value, namespace_prefix, f"{context}.{key}" if context else key
                )
                usernames.update(nested_usernames)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        nested_usernames = self._extract_usernames_from_content(
                            item,
                            namespace_prefix,
                            f"{context}.{key}[]" if context else f"{key}[]",
                        )
                        usernames.update(nested_usernames)
                    elif isinstance(item, str) and item.startswith(namespace_prefix):
                        usernames.add(item)
                        logger.debug(
                            f"Found bridge username in content list ({context}.{key}): {item}"
                        )
            elif isinstance(value, str) and value.startswith(namespace_prefix):
                # Catch any string field we haven't explicitly checked
                if key not in direct_fields:  # Don't double-log
                    usernames.add(value)
                    logger.debug(
                        f"Found bridge username in content.{key} ({context}): {value}"
                    )

        return usernames

    def _from_body_username(
        self,
        source: RequestSource,
        headers: Dict[str, Any],
        path: str,
        body_json: Optional[Dict[str, Any]],
        query_params: Optional[Dict[str, Any]] = None,
    ) -> Optional[BridgeService]:
        """
        Resolve bridge from encoded username found anywhere in request body.

        Recursively searches through JSON body for encoded usernames.
        This is a fallback when path-based resolution fails.
        """
        from .models import RequestSource

        # Only applicable for homeserver-originated requests
        if source != RequestSource.HOMESERVER:
            return None

        if not body_json:
            return None

        # Search for encoded username pattern in body
        username_pattern = self.config.username_regex
        encoded_username = self._find_pattern_in_json(body_json, username_pattern)

        if not encoded_username:
            logger.debug("No encoded username found in body")
            return None

        try:
            match = re.match(username_pattern, encoded_username)
            if not match:
                return None

            bridge_id = match.group("bridge_id")
            bridge = self.registry.get_bridge(bridge_id=bridge_id)
            return bridge
        except (ValueError, KeyError) as e:
            logger.debug(f"Failed to resolve bridge from body username: {e}")
            return None

    def _from_owner_username(
        self,
        source: RequestSource,
        headers: Dict[str, Any],
        path: str,
        body_json: Optional[Dict[str, Any]],
        query_params: Optional[Dict[str, Any]] = None,
    ) -> Optional[BridgeService]:
        """
        Resolve bridge from owner's plain username + bridge type in body.

        Last resort fallback. Requires finding both:
        1. A plain Matrix username (bridge owner)
        2. Bridge type from an encoded username elsewhere in body

        NOTE: This method may be deprecated in favor of room_id mapping.
        """
        from .models import RequestSource

        # Only applicable for homeserver-originated requests
        if source != RequestSource.HOMESERVER:
            return None

        if not body_json:
            return None

        # Look for plain username pattern
        owner_pattern = r"@(?P<username>[^:]+):(?P<homeserver>[^\s/]+)"
        owner_username = self._find_pattern_in_json(body_json, owner_pattern)

        # Look for encoded username to extract bridge type
        bridge_pattern = self.config.username_regex
        bridge_username = self._find_pattern_in_json(body_json, bridge_pattern)

        if not owner_username or not bridge_username:
            logger.debug("Missing owner username or bridge username in body")
            return None

        try:
            match = re.match(bridge_pattern, bridge_username)
            if not match:
                return None

            service = match.group("bridge_type")
            bridge = self.registry.get_bridge(
                owner_username=owner_username, service=service
            )
            return bridge
        except (ValueError, KeyError) as e:
            logger.debug(f"Failed to resolve bridge from owner username: {e}")
            return None

    @staticmethod
    def _extract_auth_token(headers: Dict[str, Any]) -> Optional[str]:
        """Extract bearer token from Authorization header"""
        if not headers:
            return None

        auth = headers.get("authorization") or headers.get("Authorization")
        if not auth:
            return None

        return auth.replace("Bearer ", "").strip()

    @staticmethod
    def _find_pattern_in_json(obj: Any, pattern: str) -> Optional[str]:
        """
        Recursively search JSON structure for string matching regex pattern.

        Args:
            obj: JSON-serializable object (dict, list, str, etc.)
            pattern: Regex pattern to match

        Returns:
            First matching string found, or None
        """
        if isinstance(obj, dict):
            for value in obj.values():
                if isinstance(value, str) and re.match(pattern, value):
                    return value
                result = BridgeResolver._find_pattern_in_json(value, pattern)
                if result:
                    return result
        elif isinstance(obj, list):
            for item in obj:
                result = BridgeResolver._find_pattern_in_json(item, pattern)
                if result:
                    return result
        elif isinstance(obj, str) and re.match(pattern, obj):
            return obj

        return None

    @staticmethod
    def _get_method_name(resolver_func) -> BridgeResolutionMethod:
        """Map resolver function to its corresponding enum"""
        mapping = {
            "_from_auth_token": BridgeResolutionMethod.AUTH_TOKEN,
            "_from_query_user_id": BridgeResolutionMethod.QUERY_USER_ID,
            "_from_path_username": BridgeResolutionMethod.PATH_USERNAME,
            "_from_transaction_id": BridgeResolutionMethod.TRANSACTION_ID,
            "_from_transaction_events": BridgeResolutionMethod.TRANSACTION_EVENTS,
            "_from_room_id": BridgeResolutionMethod.ROOM_ID,
            "_from_body_username": BridgeResolutionMethod.BODY_USERNAME,
            "_from_owner_username": BridgeResolutionMethod.OWNER_USERNAME,
        }
        return mapping.get(resolver_func.__name__, BridgeResolutionMethod.UNKNOWN)
