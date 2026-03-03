"""
Orchestrator error classes.
"""


class OrchestratorError(Exception):
    """Base exception for orchestrator errors."""

    pass


class BridgeCreationError(OrchestratorError):
    """Raised when bridge container creation fails."""

    pass


class BridgeStartError(OrchestratorError):
    """Raised when bridge container start fails."""

    pass


class BridgeStopError(OrchestratorError):
    """Raised when bridge container stop fails."""

    pass


class BridgeDeletionError(OrchestratorError):
    """Raised when bridge container deletion fails."""

    pass


class ConfigurationError(OrchestratorError):
    """Raised when bridge configuration generation fails."""

    pass


class DockerConnectionError(OrchestratorError):
    """Raised when Docker connection fails."""

    pass


class HealthCheckError(OrchestratorError):
    """Raised when bridge health check fails."""

    pass
