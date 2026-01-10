"""
Public interface for user management operations.
Single entry point for all user-related operations.
"""

from typing import List, Optional, Dict, Any

from .register import UserRegister
from .bridge_manager import UserBridgeManager
from .database.repositories import UsersRepository


class UserManagementInterface:
    """
    Single interface for all user management operations.
    All API routes should use ONLY this interface.
    """

    def __init__(self):
        self.register = UserRegister()
        self.bridge_manager = UserBridgeManager()
        self.users_repo = UsersRepository()

    # ============================================================
    # USER LIFECYCLE
    # ============================================================

    def create_user(self, username: str):
        """Create a new user with Matrix account."""
        return self.register.register(username)

    def get_user(self, user_id: int):
        """Get user by ID."""
        return self.users_repo.get_by_user_id(user_id)

    def get_user_by_username(self, username: str):
        """Get user by username."""
        return self.users_repo.get_by_username(username)

    def list_users(self):
        """List all users."""
        return self.users_repo.get_all()

    def get_user_status(self, user_id: int) -> Dict[str, Any]:
        """Get user status including bridges and rooms."""
        user = self.get_user(user_id)
        if not user:
            return None

        # Get bridges
        bridges = self.bridge_manager.list_bridges(user)

        # TODO: Get rooms count
        room_count = 0

        # TODO: Get recent activity
        recent_activity = []

        return {
            "user_id": user.id,
            "username": user.username,
            "matrix_user_id": user.matrix_username,
            "bridge_count": len(bridges),
            "room_count": room_count,
            "bridges": [
                {
                    "bridge_id": b.orchestrator_id,
                    "service": b.bridge_service,
                    "status": b.live_status or "unknown",
                    "created_at": b.created_at.isoformat() if b.created_at else None,
                }
                for b in bridges
            ],
            "recent_activity": recent_activity,
        }

    def delete_user(self, user_id: int, options: Optional[Dict] = None):
        """Delete user and all associated data. TODO: Implement."""
        raise NotImplementedError("User deletion not yet implemented")

    def export_user_data(self, user_id: int):
        """Export all user data. TODO: Implement."""
        raise NotImplementedError("User data export not yet implemented")

    # ============================================================
    # BRIDGE MANAGEMENT
    # ============================================================

    def list_bridges(self, user_id: int):
        """List all bridges for a user."""
        user = self.get_user(user_id)
        if not user:
            return []
        return self.bridge_manager.list_bridges(user)

    def create_bridge(
        self, user_id: int, service: str, credentials: Optional[Dict] = None
    ):
        """Create a new bridge for a user."""
        user = self.get_user(user_id)
        return self.bridge_manager.create_bridge(user, service)

    def login_bridge(self, user_id: int, bridge_id: str, phone_number: str):
        """Login to a bridge."""
        user = self.get_user(user_id)
        bridges = self.bridge_manager.list_bridges(user)
        bridge = next((b for b in bridges if b.orchestrator_id == bridge_id), None)

        if not bridge:
            raise ValueError(f"Bridge {bridge_id} not found")

        return self.bridge_manager.login(user, bridge, phone_number)

    def get_bridge_status(self, user_id: int, bridge_id: str):
        """Get bridge status. TODO: Implement in UserBridgeManager."""
        user = self.get_user(user_id)
        bridges = self.bridge_manager.list_bridges(user)
        bridge = next((b for b in bridges if b.orchestrator_id == bridge_id), None)

        if not bridge:
            raise ValueError(f"Bridge {bridge_id} not found")

        # Return basic status from bridge model
        return {
            "bridge_id": bridge.orchestrator_id,
            "service": bridge.bridge_service,
            "live_status": bridge.live_status,
            "ready_status": bridge.ready_status,
            "last_status_update": (
                bridge.status_updated_at.isoformat()
                if bridge.status_updated_at
                else None
            ),
            "matrix_bot_username": bridge.matrix_bot_username,
            "created_at": bridge.created_at.isoformat() if bridge.created_at else None,
        }

    def delete_bridge(self, user_id: int, bridge_id: str):
        """Delete a bridge. TODO: Implement."""
        raise NotImplementedError("Bridge deletion not yet implemented")

    # ============================================================
    # ROOM MANAGEMENT
    # ============================================================

    def list_rooms(self, user_id: int, platform: Optional[str] = None):
        """List all rooms for a user. TODO: Implement."""
        # TODO: Implement room listing
        return []

    def get_room_details(self, user_id: int, room_id: str):
        """Get room details. TODO: Implement."""
        raise NotImplementedError("Room details not yet implemented")

    def get_room_messages(
        self, user_id: int, room_id: str, page: int = 1, page_size: int = 50
    ):
        """Get messages for a room. TODO: Implement."""
        # TODO: Implement message retrieval
        return {
            "room_id": room_id,
            "messages": [],
            "total_count": 0,
            "page": page,
            "page_size": page_size,
        }

    def backfill_room(self, user_id: int, room_id: str):
        """Trigger transcript backfill for a room. TODO: Implement."""
        raise NotImplementedError("Room backfill not yet implemented")

    # ============================================================
    # SUGGESTIONS
    # ============================================================

    def generate_suggestion(
        self,
        user_id: int,
        room_id: str,
        suggestion_type: str = "joke",
        until_event_id: Optional[str] = None,
    ):
        """Generate a suggestion. TODO: Implement."""
        raise NotImplementedError("Suggestion generation not yet implemented")

    def get_room_suggestions(self, user_id: int, room_id: str):
        """Get suggestions for a room. TODO: Implement."""
        return []

    def get_suggestion_job_status(self, job_id: str):
        """Get suggestion job status. TODO: Implement."""
        raise NotImplementedError("Job status polling not yet implemented")
