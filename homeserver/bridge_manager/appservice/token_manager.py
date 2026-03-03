"""
Token management for adjusting auth tokens between homeserver and bridges.

Handles:
1. Homeserver -> Bridge: Replace HS's AS token with bridge's expected HS token
2. Bridge -> Homeserver: Replace bridge's AS token with bridge manager's AS token
"""

from typing import Dict
from config import BRIDGE_MANAGER_CONFIG
from bridge_manager.database.models import Bridge
from bridge_manager.errors import TokenValidationError


class TokenManager:
    """Manages auth token adjustments for proxying."""

    def __init__(self):
        self.bridge_manager_as_token = BRIDGE_MANAGER_CONFIG.AS_TOKEN

    def adjust_for_bridge(
        self, headers: Dict[str, str], bridge: Bridge
    ) -> Dict[str, str]:
        """
        Adjust headers when forwarding request from homeserver to bridge.

        The homeserver sends requests with the AS token (bridge manager's token).
        We need to replace it with the HS token that this specific bridge expects.

        Args:
            headers: Request headers from homeserver
            bridge: Target bridge model

        Returns:
            Modified headers with bridge's expected HS token
        """
        adjusted_headers = headers.copy()

        # Replace with bridge's HS token
        adjusted_headers["authorization"] = f"Bearer {bridge.hs_token}"

        return adjusted_headers

    def adjust_for_homeserver(
        self, headers: Dict[str, str], bridge: Bridge
    ) -> Dict[str, str]:
        """
        Adjust headers when forwarding request from bridge to homeserver.

        The bridge sends requests with its AS token.
        We need to replace it with the bridge manager's AS token.

        Args:
            headers: Request headers from bridge
            bridge: Source bridge model

        Returns:
            Modified headers with bridge manager's AS token
        """
        adjusted_headers = headers.copy()

        # Replace with bridge manager's AS token
        adjusted_headers["authorization"] = f"Bearer {self.bridge_manager_as_token}"

        return adjusted_headers

    def validate_homeserver_token(self, headers: Dict[str, str]) -> bool:
        """
        Validate that request from homeserver has correct AS token.

        Args:
            headers: Request headers

        Returns:
            True if valid, raises TokenValidationError if invalid
        """
        auth_header = headers.get("authorization", "")

        if not auth_header.startswith("Bearer "):
            raise TokenValidationError("Missing or invalid Authorization header")

        token = auth_header[7:]  # Remove "Bearer " prefix

        if token != self.bridge_manager_as_token:
            raise TokenValidationError("Invalid AS token from homeserver")

        return True

    def validate_hs_token(self, incoming_token: str, expected_hs_token: str) -> bool:
        """
        Validate that request from homeserver uses the expected HS token.

        Args:
            incoming_token: Token from Authorization header
            expected_hs_token: Expected HS token for this bridge

        Returns:
            True if valid, False otherwise
        """
        if not incoming_token:
            return False
        return incoming_token == expected_hs_token

    def validate_bridge_token(self, headers: Dict[str, str], bridge: Bridge) -> bool:
        """
        Validate that request from bridge has correct AS token.

        Args:
            headers: Request headers
            bridge: Expected source bridge

        Returns:
            True if valid, raises TokenValidationError if invalid
        """
        auth_header = headers.get("authorization", "")

        if not auth_header.startswith("Bearer "):
            raise TokenValidationError("Missing or invalid Authorization header")

        token = auth_header[7:]  # Remove "Bearer " prefix

        if token != bridge.as_token:
            raise TokenValidationError(f"Invalid AS token for bridge {bridge.id}")

        return True

    def validate_as_token(self, incoming_token: str, expected_as_token: str) -> bool:
        """
        Validate that request from bridge uses the expected AS token.

        Args:
            incoming_token: Token from Authorization header
            expected_as_token: Expected AS token for this bridge

        Returns:
            True if valid, False otherwise
        """
        if not incoming_token:
            return False
        return incoming_token == expected_as_token

    def extract_token(self, headers: Dict[str, str]) -> str:
        """
        Extract bearer token from Authorization header.

        Args:
            headers: Request headers

        Returns:
            Token string without "Bearer " prefix
        """
        auth_header = headers.get("authorization", "")

        if auth_header.startswith("Bearer "):
            return auth_header[7:]

        return ""
