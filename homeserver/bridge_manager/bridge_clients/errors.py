"""
Custom exceptions for bridge clients.
"""


class BridgeClientError(Exception):
    """Base exception for bridge client operations."""

    pass


class BridgeLoginError(BridgeClientError):
    """Raised when bridge login fails."""

    pass


class BridgeConnectionError(BridgeClientError):
    """Raised when bridge connection/communication fails."""

    pass


class BridgeStatusError(BridgeClientError):
    """Raised when bridge status check fails."""

    pass


class BridgeLogoutError(BridgeClientError):
    """Raised when bridge logout fails."""

    pass
