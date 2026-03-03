"""
Docker client wrapper for orchestrator.

Provides a thin wrapper around Docker SDK with multi-host support.
"""

import logging
from typing import Dict, Optional
import docker
from docker.models.containers import Container
from docker.models.volumes import Volume

from .errors import DockerConnectionError

logger = logging.getLogger(__name__)


class DockerClientManager:
    """
    Manages Docker client connections to multiple Docker hosts.

    Supports:
    - Local Docker (docker.from_env())
    - Remote Docker hosts (docker.DockerClient(base_url=...))
    - Connection pooling and caching
    """

    def __init__(self):
        """Initialize Docker client manager with connection cache."""
        self._clients: Dict[str, docker.DockerClient] = {}
        self._default_client: Optional[docker.DockerClient] = None

    def get_client(self, docker_host: Optional[str] = None) -> docker.DockerClient:
        """
        Get or create Docker client for specified host.

        Args:
            docker_host: Docker host URL (e.g., "unix:///var/run/docker.sock" or "tcp://192.168.1.10:2375")
                        If None, uses local Docker

        Returns:
            Connected Docker client

        Raises:
            DockerConnectionError: If connection fails
        """
        # Use default local client if no host specified
        if docker_host is None:
            if self._default_client is None:
                try:
                    self._default_client = docker.from_env()
                    logger.info("Connected to local Docker daemon")
                except docker.errors.DockerException as e:
                    raise DockerConnectionError(
                        f"Failed to connect to local Docker: {e}"
                    )
            return self._default_client

        # Check if we already have a connection to this host
        if docker_host in self._clients:
            return self._clients[docker_host]

        # Create new connection
        try:
            client = docker.DockerClient(base_url=docker_host)
            # Test connection
            client.ping()
            self._clients[docker_host] = client
            logger.info(f"Connected to Docker host: {docker_host}")
            return client
        except docker.errors.DockerException as e:
            raise DockerConnectionError(
                f"Failed to connect to Docker host {docker_host}: {e}"
            )

    def close_all(self):
        """Close all Docker client connections."""
        for client in self._clients.values():
            try:
                client.close()
            except Exception as e:
                logger.warning(f"Error closing Docker client: {e}")

        if self._default_client:
            try:
                self._default_client.close()
            except Exception as e:
                logger.warning(f"Error closing default Docker client: {e}")

        self._clients.clear()
        self._default_client = None
        logger.info("Closed all Docker connections")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close all connections."""
        self.close_all()
