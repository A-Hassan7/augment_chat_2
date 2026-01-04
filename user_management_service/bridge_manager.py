from enum import Enum
from typing import List, Dict, Any

from bridge_manager.interface import BridgeManagerInterface
from bridge_manager.database.models import Bridges
from .database.models import User
from .errors import (
    BridgeAccessDeniedError,
    BridgeCreationError,
    BridgeLoginError,
    InvalidBridgeServiceError,
)
from logger import Logger


class BridgeService(Enum):
    """Supported bridge platforms"""

    WHATSAPP = "whatsapp"
    DISCORD = "discord"
    TELEGRAM = "telegram"
    MESSENGER = "messenger"


class UserBridgeManager:
    """
    Manages bridge lifecycle for users.
    Provides access control and validation for all bridge operations.
    """

    def __init__(self):
        self.bridge_manager = BridgeManagerInterface()

        logger_instance = Logger()
        self.logger = logger_instance.get_logger(name=__class__.__name__)

    def create_bridge(self, user: User, service: str) -> Bridges:
        """
        Create a new bridge for a user.

        Args:
            user: User object with matrix_username populated
            service: Bridge service type (whatsapp, discord, etc.)

        Returns:
            Bridges: Created bridge model

        Raises:
            BridgeCreationError: If bridge creation fails
            InvalidBridgeServiceError: If service type is not supported
        """
        # Validate user has Matrix account
        if not user.matrix_username:
            raise BridgeCreationError(
                f"User {user.username} does not have a Matrix account yet"
            )

        # Validate service type
        try:
            service_enum = BridgeService(service.lower())
        except ValueError:
            valid_services = [s.value for s in BridgeService]
            raise InvalidBridgeServiceError(
                f"Invalid service '{service}'. Must be one of: {valid_services}"
            )

        self.logger.info(
            f"Creating {service} bridge for user {user.username} "
            f"(matrix: {user.matrix_username})"
        )

        try:
            bridge_model = self.bridge_manager.create_bridge(
                matrix_username=user.matrix_username, service=service_enum.value
            )

            self.logger.info(
                f"Bridge created successfully: {bridge_model.orchestrator_id} "
                f"for user {user.username}"
            )

            return bridge_model

        except Exception as e:
            self.logger.error(
                f"Failed to create {service} bridge for {user.username}: {str(e)}"
            )
            raise BridgeCreationError(f"Failed to create bridge: {str(e)}")

    def list_bridges(self, user: User) -> List[Bridges]:
        """
        List all bridges owned by a user.

        Args:
            user: User object

        Returns:
            List of Bridges models
        """
        if not user.matrix_username:
            self.logger.warning(
                f"User {user.username} has no Matrix account, no bridges found"
            )
            return []

        bridges = self.bridge_manager.list_bridges_by_owner(user.matrix_username)

        self.logger.info(f"Found {len(bridges)} bridge(s) for user {user.username}")

        return bridges

    def login(self, user: User, bridge: Bridges, phone_number: str) -> Dict[str, Any]:
        """
        Login to a bridge (e.g., WhatsApp with phone number).

        Args:
            user: User object
            bridge: Bridge model
            phone_number: Phone number in international format (for WhatsApp)

        Returns:
            Dict with login details (login_code, phone_number, bridge_id)

        Raises:
            BridgeAccessDeniedError: If user doesn't own the bridge
            BridgeLoginError: If login fails
        """
        # Verify ownership
        if bridge.owner_matrix_username != user.matrix_username:
            raise BridgeAccessDeniedError("User must be the owner of the bridge")

        self.logger.info(
            f"Initiating login for user {user.username} on bridge "
            f"{bridge.orchestrator_id} ({bridge.bridge_service})"
        )

        try:
            login_code = self.bridge_manager.login(
                bridge=bridge, phone_number=phone_number
            )

            self.logger.info(
                f"Login request created for user {user.username} on bridge {bridge.orchestrator_id} with login code {login_code}"
            )

            return login_code

        except Exception as e:
            self.logger.error(
                f"Login failed for user {user.username} on bridge "
                f"{bridge.orchestrator_id}: {str(e)}"
            )
            raise BridgeLoginError(f"Bridge login failed: {str(e)}")

    def get_bridge_status(self, user: User, bridge: Bridges):
        """Get the current status of a bridge."""
        pass

    def delete_bridge(self, user: User, bridge: Bridges):
        """Delete a bridge and stop the container."""
        pass
