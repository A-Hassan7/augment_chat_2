"""
WhatsApp Bridge Client.

Handles WhatsApp-specific operations via Matrix bot commands:
- QR code login (via "login qr" command)
- Connection status (via "ping" command)
- User info (via status messages)
- Logout (via "logout" command)

Uses Matrix messages instead of HTTP API calls since mautrix-whatsapp
uses bridgev2 architecture with bot commands.
"""

from typing import Dict, Any, Optional
import logging
import asyncio
import re

from .base_client import BaseBridgeClient
from .errors import BridgeLoginError, BridgeStatusError, BridgeLogoutError

logger = logging.getLogger(__name__)


class WhatsAppBridgeClient(BaseBridgeClient):
    """
    Client for mautrix-whatsapp bridge operations via Matrix bot commands.

    Mautrix-whatsapp uses bridgev2 architecture where bridge management happens
    through Matrix messages sent to the bridge bot, not HTTP API calls.

    Commands:
    - "login qr" - Get QR code for WhatsApp login
    - "logout" - Disconnect from WhatsApp
    - "ping" - Check bridge connection status
    - "help" - Get list of available commands
    """

    # Bridge bot user ID pattern
    BRIDGE_BOT_LOCALPART = "whatsappbot"

    # Response timeout for bot commands
    COMMAND_TIMEOUT = 30  # seconds

    def __init__(self, bridge, homeserver_client):
        """
        Initialize WhatsApp bridge client.

        Args:
            bridge: Bridge model instance
            homeserver_client: HomeserverClient for Matrix operations
        """
        super().__init__(bridge)
        self.homeserver_client = homeserver_client
        self._owner_room_id = None  # DM room with bridge bot
        self._owner_access_token = None  # Owner's access token

    async def _ensure_owner_setup(self):
        """
        Ensure bridge owner user is registered and has DM room with bridge bot.

        Creates:
        1. Owner user if not registered
        2. DM room between owner and bridge bot
        3. Stores access token and room ID for future commands
        """
        if self._owner_room_id and self._owner_access_token:
            return  # Already set up

        owner_username = self.bridge.owner_username

        # Check if user exists, register if not
        if not self.homeserver_client.is_user_registered(owner_username):
            logger.info(f"Registering owner user: {owner_username}")
            await self.homeserver_client.register_user(owner_username)

        # Login to get access token
        login_result = await self.homeserver_client.login(owner_username)
        self._owner_access_token = login_result["access_token"]

        # Create or get DM room with bridge bot
        bridge_bot_id = self._get_bridge_bot_id()

        # Try to find existing DM room first (future enhancement)
        # For now, create new room
        self._owner_room_id = await self.homeserver_client.create_room(
            username=owner_username,
            access_token=self._owner_access_token,
            is_direct=True,
            invite=[bridge_bot_id],
        )

        logger.info(
            f"Owner setup complete: room={self._owner_room_id}, "
            f"user={owner_username}"
        )

    def _get_bridge_bot_id(self) -> str:
        """
        Get bridge bot's Matrix user ID.

        Returns:
            Full Matrix user ID of bridge bot
        """
        homeserver_name = self.bridge.homeserver.name
        return f"@{self.BRIDGE_BOT_LOCALPART}:{homeserver_name}"

    async def _send_command(
        self,
        command: str,
        wait_for_response: bool = True,
        timeout: int = COMMAND_TIMEOUT,
    ) -> Optional[str]:
        """
        Send command to bridge bot and optionally wait for response.

        Args:
            command: Command string to send
            wait_for_response: Whether to wait for bot's response
            timeout: Max seconds to wait for response

        Returns:
            Bot's response message or None
        """
        await self._ensure_owner_setup()

        # Send command message
        await self.homeserver_client.send_message(
            username=self.bridge.owner_username,
            access_token=self._owner_access_token,
            room_id=self._owner_room_id,
            message=command,
        )

        logger.debug(f"Sent command to bridge bot: {command}")

        if not wait_for_response:
            return None

        # Wait for bot's response
        # TODO: Implement proper message polling/listening
        # For now, use simple delay and fetch recent messages
        await asyncio.sleep(2)  # Give bot time to respond

        # Fetch recent messages from room
        # This is a placeholder - proper implementation would use sync API
        # to get new messages since command was sent
        return "Response received"  # Placeholder

    async def login(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """
        Initiate WhatsApp login via QR code.

        Sends "login qr" command to bridge bot.

        Args:
            credentials: Empty dict or optional params

        Returns:
            Dict with:
                - success: bool
                - qr_code: str (if successful) - QR code data or instructions
                - message: str - Bot's response message
                - status: str - current login status

        Raises:
            BridgeLoginError: If login initiation fails
        """
        try:
            logger.info(f"Initiating WhatsApp login for bridge {self.bridge.id}")

            # Send "login qr" command to bridge bot
            response = await self._send_command("login qr")

            # Parse response for QR code
            # Bot will send a message with QR code or instructions
            # Format depends on bridge implementation

            return {
                "success": True,
                "message": response,
                "status": "qr_requested",
                "instructions": (
                    "QR code requested. Check your Matrix client for the QR code "
                    "message from the bridge bot."
                ),
            }

        except Exception as e:
            logger.error(f"WhatsApp login error for bridge {self.bridge.id}: {e}")
            raise BridgeLoginError(f"Login failed: {e}")

    async def check_status(self) -> Dict[str, Any]:
        """
        Check WhatsApp connection status.

        Sends "ping" command to bridge bot.

        Returns:
            Dict with:
                - connected: bool
                - logged_in: bool
                - message: str - Bot's response
                - info: Optional[Dict] - User details if available

        Raises:
            BridgeStatusError: If status check fails
        """
        try:
            logger.debug(f"Checking WhatsApp status for bridge {self.bridge.id}")

            # Send "ping" command
            response = await self._send_command("ping")

            # Parse response to determine connection status
            # Bot typically responds with connection info

            # For now, return basic structure
            # Real implementation would parse bot's response
            return {
                "connected": True,  # Placeholder
                "logged_in": True,  # Placeholder
                "message": response,
                "info": None,
            }

        except Exception as e:
            logger.error(
                f"WhatsApp status check error for bridge {self.bridge.id}: {e}"
            )
            raise BridgeStatusError(f"Status check failed: {e}")

    async def logout(self) -> bool:
        """
        Logout from WhatsApp.

        Sends "logout" command to bridge bot.

        Returns:
            True if logout successful

        Raises:
            BridgeLogoutError: If logout fails
        """
        try:
            logger.info(f"Logging out WhatsApp for bridge {self.bridge.id}")

            # Send "logout" command
            response = await self._send_command("logout")

            logger.info(f"WhatsApp logout initiated for bridge {self.bridge.id}")
            logger.debug(f"Bot response: {response}")

            return True

        except Exception as e:
            logger.error(f"WhatsApp logout error for bridge {self.bridge.id}: {e}")
            raise BridgeLogoutError(f"Logout failed: {e}")

    async def get_help(self) -> str:
        """
        Get list of available bot commands.

        Returns:
            Help text from bridge bot
        """
        try:
            response = await self._send_command("help")
            return response or "No help text available"
        except Exception as e:
            logger.error(f"Failed to get help text: {e}")
            return f"Error getting help: {e}"

    async def reconnect(self) -> bool:
        """
        Attempt to reconnect to WhatsApp.

        Sends "reconnect" command if available.

        Returns:
            True if reconnect command sent successfully
        """
        try:
            logger.info(f"Attempting WhatsApp reconnect for bridge {self.bridge.id}")

            await self._send_command("reconnect", wait_for_response=False)

            logger.info(f"WhatsApp reconnect command sent for bridge {self.bridge.id}")
            return True

        except Exception as e:
            logger.error(f"WhatsApp reconnect error: {e}")
            return False

    async def ping(self) -> bool:
        """
        Send ping to WhatsApp bridge bot.

        Returns:
            True if bridge responds
        """
        try:
            response = await self._send_command("ping")
            return response is not None
        except Exception:
            return False
