"""
Redis service for Synapse worker communication
"""

from pathlib import Path
import time
import docker
import config as HS_CONFIG
from .base import BaseService, docker_client


class RedisService(BaseService):
    """Redis service for worker communication"""

    def service_name(self) -> str:
        return "redis"

    def image_name(self) -> str:
        return HS_CONFIG.REDIS_IMAGE

    def generate_config(self) -> None:
        """Redis requires no additional configuration"""
        pass

    def deploy(self) -> docker.models.containers.Container:
        """Deploy Redis container"""
        print(f"Deploying Redis container: {self.container_name}")

        # Remove existing container if present
        try:
            existing = docker_client.containers.get(self.container_name)
            print(f"  Removing existing container...")
            existing.stop()
            existing.remove()
        except docker.errors.NotFound:
            pass

        # Start Redis container
        self.container = docker_client.containers.run(
            self.image_name(),
            name=self.container_name,
            network=self.network_name,
            detach=True,
            remove=False,
        )

        # Wait for Redis to be ready
        print("  Waiting for Redis to be ready...")
        time.sleep(2)

        for i in range(30):
            result = self.container.exec_run("redis-cli PING")
            if result.exit_code == 0 and b"PONG" in result.output:
                print("  ✓ Redis is ready")
                return self.container
            time.sleep(1)

        raise Exception("Redis failed to start")

    def is_healthy(self) -> bool:
        """Check if Redis responds to PING"""
        if not super().is_healthy():
            return False

        try:
            result = self.container.exec_run("redis-cli PING")
            return result.exit_code == 0 and b"PONG" in result.output
        except Exception:
            return False
