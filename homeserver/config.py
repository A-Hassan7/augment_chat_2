"""
Centralized configuration for homeserver deployment.

Single source of truth for all homeserver configuration including:
- Synapse deployment settings
- Bridge Manager appservice configuration
- Docker, database, and networking settings

All services (bridge_manager, orchestrator, etc.) pull from this file.
"""

import os
from pathlib import Path
from typing import Dict, Optional
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables from .env file in homeserver directory
HOMESERVER_DIR = Path(__file__).parent
ENV_PATH = HOMESERVER_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)


def _get_env(key: str, default: str = None) -> Optional[str]:
    """Get environment variable with optional default."""
    return os.getenv(key, default)


def _get_required_env(key: str) -> str:
    """Get required environment variable or raise error."""
    value = os.getenv(key)
    if value is None:
        raise ValueError(
            f"Required environment variable {key} is not set. "
            f"Please check {ENV_PATH}"
        )
    return value


# ========================================
# Bridge Manager Configuration
# ========================================


@dataclass
class WhatsAppBridgeConfig:
    """WhatsApp bridge-specific configuration."""

    # Docker image for WhatsApp bridge
    docker_image: str = "dock.mau.dev/mautrix/whatsapp:latest"

    # Config template filename
    config_template: str = "whatsapp.yaml"

    # Location in container where config should be mounted
    config_path_in_container: str = "/data/config.yaml"

    # Container entrypoint
    entrypoint: list = None

    # Health check endpoints
    health_live_endpoint: str = "_matrix/mau/live"
    health_ready_endpoint: str = "_matrix/mau/ready"

    def __post_init__(self):
        """Set default entrypoint if not provided."""
        if self.entrypoint is None:
            self.entrypoint = [
                "/usr/bin/mautrix-whatsapp",
                "-c",
                "/data/config.yaml",
            ]


class BridgeManagerConfig:
    """Configuration for bridge manager appservice and orchestrator."""

    # Bridge Manager Identity
    INSTANCE_ID = _get_required_env("BRIDGE_MANAGER_INSTANCE_ID")

    # Homeserver Configuration
    HOMESERVER_ID = _get_required_env("HOMESERVER_ID")
    HOMESERVER_NAME = _get_required_env("HOMESERVER_NAME")
    HOMESERVER_URL = _get_required_env("HOMESERVER_URL")
    HOMESERVER_HS_TOKEN = _get_required_env("HOMESERVER_HS_TOKEN")

    # Networking
    HOST = _get_required_env("BRIDGE_MANAGER_HOST")
    PORT = int(_get_required_env("BRIDGE_MANAGER_PORT"))

    # Auth tokens
    AS_TOKEN = _get_required_env("BRIDGE_MANAGER_AS_TOKEN")

    # Username patterns
    NAMESPACE = "_bm_"  # Namespace for all bridge manager users

    @property
    def username_pattern(self) -> str:
        """
        Regex pattern for bridge manager usernames.
        Format: @_bm_<bridge_type>_<bridge_id>_<username>:<homeserver>
        """
        return rf"@{self.NAMESPACE}(?P<bridge_type>[^_]+)_(?P<bridge_id>[^_]+)_(?P<username>[^:]+):(?P<homeserver>.+)"

    # Docker configuration
    DOCKER_NETWORK = _get_required_env("BRIDGE_MANAGER_DOCKER_NETWORK")

    # Docker hosts (for multi-host deployment)
    DOCKER_HOSTS: Dict[str, str] = {
        "local": "unix:///var/run/docker.sock",
        # Add remote hosts as needed:
        # "host-a": "tcp://192.168.1.10:2375",
        # "host-b": "tcp://192.168.1.11:2375",
    }

    # Database
    DATABASE_URL = _get_required_env("BRIDGE_MANAGER_DATABASE_URL")

    # Logging
    LOG_LEVEL = _get_env("BRIDGE_MANAGER_LOG_LEVEL", "INFO")
    LOG_REQUESTS = _get_env("BRIDGE_MANAGER_LOG_REQUESTS", "true").lower() == "true"

    # Orchestrator Settings
    # Default Docker restart policy
    RESTART_POLICY: Dict[str, str] = {"Name": "unless-stopped"}

    # Network mode (null for default, "host" for host networking)
    NETWORK_MODE: Optional[str] = None

    # Templates directory for bridge configs
    TEMPLATES_DIR = (
        HOMESERVER_DIR / "bridge_manager" / "orchestrator" / "config_templates"
    )

    # Output directory for generated configs
    CONFIGS_DIR = HOMESERVER_DIR / "bridge_manager" / "orchestrator" / "configs"

    # WhatsApp bridge configuration
    WHATSAPP = WhatsAppBridgeConfig()

    # Bridge manager hostname for containers to connect to
    # Use "host.docker.internal" for Docker Desktop (Mac/Windows)
    # Use actual IP or hostname for Linux
    BRIDGE_MANAGER_HOSTNAME: str = _get_env(
        "BRIDGE_MANAGER_HOSTNAME", "host.docker.internal"
    )

    # Host used by the appservice proxy to reach bridge containers.
    # Default is "localhost" (running natively on the host).
    # Set to "host.docker.internal" when running inside Docker containers.
    BRIDGE_HOST: str = _get_env("BRIDGE_HOST", "localhost")


# Global instance
BRIDGE_MANAGER_CONFIG = BridgeManagerConfig()


# ========================================
# Synapse Deployment Configuration
# ========================================
# Docker Images
# ========================================
# ========================================
# Synapse Deployment Configuration
# ========================================

# ========================================
# Docker Images
# ========================================
POSTGRES_IMAGE = "postgres:15-alpine"
SYNAPSE_IMAGE = "matrixdotorg/synapse:latest"
REDIS_IMAGE = "redis:7-alpine"
NGINX_IMAGE = "nginx:alpine"
PROMETHEUS_IMAGE = "prom/prometheus:latest"
GRAFANA_IMAGE = "grafana/grafana:latest"
BRIDGE_MANAGER_IMAGE = "bridge-manager:latest"  # Built from Dockerfile.bridge_manager

# ========================================
# Network Ports
# ========================================
# Synapse
SYNAPSE_HTTP_PORT = 8008  # Main HTTP API port
SYNAPSE_FEDERATION_PORT = 8448  # Federation port (TLS)
SYNAPSE_METRICS_PORT = 9000  # Metrics endpoint
SYNAPSE_REPLICATION_PORT = 9093  # Worker replication port

# Monitoring
GRAFANA_PORT = 3000  # Grafana web interface
PROMETHEUS_PORT = 9090  # Prometheus web interface

# Databases
POSTGRES_PORT = 5432  # PostgreSQL database
EXPOSE_POSTGRES_PORT = True  # Expose PostgreSQL port to host
REDIS_PORT = 6379  # Redis (for workers)

# Nginx
NGINX_HTTP_PORT = 80  # Nginx load balancer
NGINX_STATUS_PORT = 8080  # Nginx metrics endpoint

# Bridge Manager Nginx (separate LB for bridge manager instances)
BRIDGE_MANAGER_NGINX_PORT = 5000  # External port of the bridge manager LB
BRIDGE_MANAGER_NGINX_STATUS_PORT = 5080  # Status/metrics port
BRIDGE_MANAGER_INTERNAL_PORT = 5001  # Port each bridge manager instance listens on

# Workers
WORKER_BASE_PORT = 8081  # Starting port for worker HTTP endpoints

# ========================================
# Default Credentials
# ========================================
# Database
DB_USER = "synapse"
DB_PASSWORD = "password"  # TODO: Generate securely in production

# Grafana
GRAFANA_ADMIN_USER = "admin"
GRAFANA_ADMIN_PASSWORD = "admin"  # TODO: Generate securely in production

# Matrix Admin User
MATRIX_ADMIN_USERNAME = "admin"
MATRIX_ADMIN_PASSWORD = "admin"  # TODO: Generate securely in production

# ========================================
# Timeouts
# ========================================
SYNAPSE_STARTUP_TIMEOUT = 60  # Seconds to wait for Synapse to be ready
GRAFANA_STARTUP_TIMEOUT = 60  # Seconds to wait for Grafana to be ready

# ========================================
# Worker Configuration
# ========================================
WORKER_PORT_MAX_ATTEMPTS = 100  # Max attempts to find available port
WORKER_PORT_RANDOM_OFFSET = 50  # Random offset to avoid port collisions

# ========================================
# Database Connection Pool
# ========================================
DB_MIN_CONNECTIONS = 5  # Minimum connections in pool
DB_MAX_CONNECTIONS = 10  # Maximum connections in pool

# ========================================
# Nginx Configuration
# ========================================
NGINX_CLIENT_MAX_BODY_SIZE = "50M"  # Max upload size

# ========================================
# Prometheus Configuration
# ========================================
PROMETHEUS_SCRAPE_INTERVAL = "15s"  # How often to scrape metrics
PROMETHEUS_EVALUATION_INTERVAL = "15s"  # How often to evaluate rules

# ========================================
# Grafana Configuration
# ========================================
GRAFANA_ANONYMOUS_ACCESS = True  # Allow anonymous viewers
GRAFANA_ANONYMOUS_ROLE = "Viewer"  # Role for anonymous users

# Homeserver Client Configuration
# ========================================
# These values are used by HomeserverClient for Matrix operations
# Most come from environment, with fallback to localhost for development
SYNAPSE_URL = _get_required_env("HOMESERVER_URL")
SYNAPSE_SERVER_NAME = _get_required_env("HOMESERVER_NAME")
SYNAPSE_DATABASE_URL = _get_required_env("SYNAPSE_DATABASE_URL")
