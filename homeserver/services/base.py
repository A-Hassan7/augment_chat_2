"""
Base service class for homeserver deployment components
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Dict, Any
import docker

docker_client = docker.from_env()


class BaseService(ABC):
    """
    Base class for deployment services

    Each service handles its own:
    - Configuration generation
    - Container deployment
    - Health checking
    - Cleanup/rollback
    """

    def __init__(self, homeserver_id: str, base_dir: Path, network_name: str):
        self.homeserver_id = homeserver_id
        self.base_dir = base_dir
        self.network_name = network_name
        self.container = None
        self.docker_client = docker_client  # Reference module-level client
        self.container_name = f"{homeserver_id}_{self.service_name()}"

    @abstractmethod
    def service_name(self) -> str:
        """Return the service identifier (e.g., 'postgres', 'synapse')"""
        pass

    @abstractmethod
    def image_name(self) -> str:
        """Return the Docker image to use"""
        pass

    def validate_config(self) -> bool:
        """
        Validate configuration before deployment

        Returns:
            True if configuration is valid

        Raises:
            ValueError: If configuration is invalid
        """
        return True

    @abstractmethod
    def generate_config(self) -> None:
        """Generate configuration files needed by this service"""
        pass

    @abstractmethod
    def deploy(self) -> docker.models.containers.Container:
        """
        Deploy the service container

        Returns:
            The deployed container object
        """
        pass

    def is_healthy(self) -> bool:
        """
        Check if service is healthy

        Returns:
            True if service is running and healthy
        """
        if not self.container:
            try:
                self.container = docker_client.containers.get(self.container_name)
            except docker.errors.NotFound:
                return False

        try:
            self.container.reload()
            return self.container.status == "running"
        except docker.errors.NotFound:
            return False

    def wait_until_ready(self, timeout: int = 30) -> bool:
        """
        Wait for service to be ready

        Args:
            timeout: Maximum seconds to wait

        Returns:
            True if service became ready
        """
        import time

        for _ in range(timeout):
            if self.is_healthy():
                return True
            time.sleep(1)
        return False

    def cleanup(self) -> None:
        """Stop and remove the service container"""
        if self.container:
            try:
                self.container.stop()
                self.container.remove()
            except docker.errors.NotFound:
                pass

    def get_status(self) -> Dict[str, Any]:
        """
        Get current service status

        Returns:
            Dictionary with status information
        """
        if not self.container:
            return {
                "name": self.service_name(),
                "status": "not deployed",
                "healthy": False,
            }

        try:
            self.container.reload()
            health = self.container.attrs.get("State", {}).get("Health", {})
            return {
                "name": self.service_name(),
                "container": self.container_name,
                "status": self.container.status,
                "healthy": health.get("Status") == "healthy" if health else None,
                "image": (
                    self.container.image.tags[0]
                    if self.container.image.tags
                    else "unknown"
                ),
            }
        except docker.errors.NotFound:
            return {"name": self.service_name(), "status": "stopped", "healthy": False}
