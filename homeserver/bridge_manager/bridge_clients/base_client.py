"""
Base bridge client class.

Provides abstract interface for bridge-specific operations like:
- Login flows
- Status checks
- Health monitoring
- Logout
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import httpx
import logging

from ..database.models import Bridge
from .errors import BridgeConnectionError

logger = logging.getLogger(__name__)


class BaseBridgeClient(ABC):
    """
    Abstract base class for bridge-specific client implementations.

    Each bridge type (WhatsApp, Meta, Discord, etc.) should implement this interface
    to handle bridge-specific operations like login flows and status checks.
    """

    def __init__(self, bridge: Bridge):
        """
        Initialize bridge client.

        Args:
            bridge: Bridge model with connection details
        """
        self.bridge = bridge
        self.base_url = f"http://{bridge.host}:{bridge.port}"
        self.timeout = 30.0  # Default timeout in seconds

    @abstractmethod
    async def login(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """
        Initiate login flow for this bridge type.

        Implementation varies by bridge:
        - WhatsApp: Returns QR code for scanning
        - Meta: Returns OAuth URL or handles credentials
        - Telegram: Returns phone number verification

        Args:
            credentials: Bridge-specific credentials/parameters

        Returns:
            Dict containing login response (QR code, URL, status, etc.)

        Raises:
            BridgeLoginError: If login initiation fails
        """
        pass

    @abstractmethod
    async def check_status(self) -> Dict[str, Any]:
        """
        Check bridge connection status.

        Should return information about:
        - Whether bridge is connected to the service
        - Whether user is logged in
        - User info (phone number, username, etc.)
        - Any error states

        Returns:
            Dict with keys:
                - connected: bool
                - logged_in: bool
                - info: Optional[Dict] (user info, connection details)
                - error: Optional[str]

        Raises:
            BridgeStatusError: If status check fails
        """
        pass

    @abstractmethod
    async def logout(self) -> bool:
        """
        Logout from bridge.

        Should disconnect from the external service and clear credentials.

        Returns:
            True if logout successful

        Raises:
            BridgeLogoutError: If logout fails
        """
        pass

    async def health_check(self) -> bool:
        """
        Generic health check - verify bridge container is responsive.

        This is a generic implementation that works for most bridges.
        Override if bridge has a specific health endpoint.

        Returns:
            True if bridge is responsive, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Try common health endpoints
                for endpoint in ["/health", "/_matrix/mau/live", "/"]:
                    try:
                        response = await client.get(f"{self.base_url}{endpoint}")
                        if response.status_code in (
                            200,
                            404,
                        ):  # 404 is ok, means it's running
                            logger.debug(f"Bridge {self.bridge.id} health check passed")
                            return True
                    except httpx.RequestError:
                        continue

                logger.warning(f"Bridge {self.bridge.id} health check failed")
                return False

        except Exception as e:
            logger.error(f"Bridge {self.bridge.id} health check error: {e}")
            return False

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        headers: Optional[Dict[str, str]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> httpx.Response:
        """
        Make HTTP request to bridge.

        Helper method for subclasses to use.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., "/api/login")
            headers: Optional headers
            json_data: Optional JSON body
            params: Optional query parameters

        Returns:
            httpx.Response

        Raises:
            BridgeConnectionError: If request fails
        """
        url = f"{self.base_url}{endpoint}"

        # Add authorization header if not provided
        if headers is None:
            headers = {}
        if "authorization" not in headers and "Authorization" not in headers:
            headers["Authorization"] = f"Bearer {self.bridge.as_token}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=json_data,
                    params=params,
                )
                return response

        except httpx.TimeoutException as e:
            logger.error(f"Request to bridge {self.bridge.id} timed out: {e}")
            raise BridgeConnectionError(f"Request timed out: {e}")
        except httpx.RequestError as e:
            logger.error(f"Request to bridge {self.bridge.id} failed: {e}")
            raise BridgeConnectionError(f"Request failed: {e}")

    def get_bridge_info(self) -> Dict[str, Any]:
        """
        Get bridge information.

        Returns:
            Dict with bridge details
        """
        return {
            "id": self.bridge.id,
            "bridge_type": self.bridge.bridge_type,
            "host": self.bridge.host,
            "port": self.bridge.port,
            "status": self.bridge.status,
            "owner": self.bridge.owner_matrix_username,
            "matrix_bot": self.bridge.matrix_bot_username,
        }
