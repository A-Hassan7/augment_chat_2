"""
Bridge Orchestrator - Docker container lifecycle management for bridges.

Handles:
- Creating bridge containers with custom configurations
- Starting/stopping/deleting bridge containers
- Multi-host Docker support
- Health monitoring
- Volume and network management
"""

from bridge_manager.orchestrator.orchestrator import BridgeOrchestrator
from bridge_manager.orchestrator.bridges import WhatsAppBridge
from bridge_manager.orchestrator.docker_client import DockerClientManager
from config import BRIDGE_MANAGER_CONFIG, WhatsAppBridgeConfig
from bridge_manager.orchestrator.errors import (
    OrchestratorError,
    BridgeCreationError,
    BridgeStartError,
    BridgeStopError,
    BridgeDeletionError,
    ConfigurationError,
    DockerConnectionError,
    HealthCheckError,
)

__all__ = [
    "BridgeOrchestrator",
    "WhatsAppBridge",
    "DockerClientManager",
    "BRIDGE_MANAGER_CONFIG",
    "WhatsAppBridgeConfig",
    "OrchestratorError",
    "BridgeCreationError",
    "BridgeStartError",
    "BridgeStopError",
    "BridgeDeletionError",
    "ConfigurationError",
    "DockerConnectionError",
    "HealthCheckError",
]
