"""
Custom exceptions for bridge manager.
"""


class BridgeManagerError(Exception):
    """Base exception for bridge manager."""

    pass


class BridgeNotFoundError(BridgeManagerError):
    """Raised when a bridge cannot be found or identified."""

    pass


class BridgeRoutingError(BridgeManagerError):
    """Raised when bridge routing fails."""

    pass


class AuthenticationError(BridgeManagerError):
    """Raised when authentication fails."""

    pass


class HomeserverNotFoundError(BridgeManagerError):
    """Raised when a homeserver cannot be found."""

    pass


class BridgeCreationError(BridgeManagerError):
    """Raised when bridge creation fails."""

    pass


class BridgeDeletionError(BridgeManagerError):
    """Raised when bridge deletion fails."""

    pass


class TokenValidationError(BridgeManagerError):
    """Raised when token validation fails."""

    pass


class BridgeClientError(BridgeManagerError):
    """Raised when bridge client operations fail."""

    pass


class DockerError(BridgeManagerError):
    """Raised when Docker operations fail."""

    pass
