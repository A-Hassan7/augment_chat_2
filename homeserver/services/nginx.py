"""
Nginx load balancer and reverse proxy service

Handles Nginx deployment, configuration, and health checks for Matrix homeserver.
"""

from pathlib import Path
from typing import Dict, Any, Optional
import docker

import sys

import config as HS_CONFIG
from services.base import BaseService


class NginxService(BaseService):
    """
    Nginx load balancer and reverse proxy service

    Manages:
    - Nginx configuration generation
    - Upstream configuration (synapse or workers)
    - Reverse proxy setup
    - Container deployment
    - Health checking via status endpoint
    """

    def __init__(
        self,
        homeserver_id: str,
        base_dir: Path,
        network_name: str,
        domain: str = "localhost",
        num_workers: int = 0,
        synapse_container: Optional[str] = None,
    ):
        """
        Args:
            homeserver_id: Unique ID for this homeserver
            base_dir: Base directory for configs and data
            network_name: Docker network name
            domain: Domain name for the server
            num_workers: Number of workers (0 for monolith mode)
            synapse_container: Name of main synapse container
        """
        super().__init__(homeserver_id, base_dir, network_name)

        self.domain = domain
        self.num_workers = num_workers
        self.synapse_container = synapse_container or f"{homeserver_id}_synapse"
        self.container_name = f"{homeserver_id}_nginx"

        # Paths
        self.nginx_dir = base_dir / "nginx"
        self.config_path = self.nginx_dir / "synapse.conf"
        self.template_path = Path("templates") / "nginx_config_template.conf"

    def service_name(self) -> str:
        return "nginx"

    def image_name(self) -> str:
        return HS_CONFIG.NGINX_IMAGE

    def validate_config(self) -> bool:
        """Validate Nginx configuration"""
        if not self.domain or not self.domain.strip():
            raise ValueError("Domain must be provided")

        if self.num_workers < 0:
            raise ValueError("Number of workers cannot be negative")

        # Check template exists
        if not self.template_path.exists():
            raise ValueError(f"Nginx template not found: {self.template_path}")

        return True

    def generate_config(self) -> None:
        """Generate Nginx configuration from template"""
        print(f"Generating {self.service_name()} configuration...")

        # Create nginx directory
        self.nginx_dir.mkdir(parents=True, exist_ok=True)

        # Load template
        with open(self.template_path, "r") as f:
            template = f.read()

        # Build upstream servers block
        if self.num_workers > 0:
            # Load balance across workers
            upstream_servers = "\n".join(
                f"    server {self.homeserver_id}_worker{i}:8083;"
                for i in range(1, self.num_workers + 1)
            )
        else:
            # Single main process
            upstream_servers = (
                f"    server {self.synapse_container}:{HS_CONFIG.SYNAPSE_HTTP_PORT};"
            )

        # Substitute variables
        nginx_config = template.replace("{{UPSTREAM_SERVERS}}", upstream_servers)
        nginx_config = nginx_config.replace(
            "{{NGINX_STATUS_PORT}}", str(HS_CONFIG.NGINX_STATUS_PORT)
        )
        nginx_config = nginx_config.replace(
            "{{NGINX_HTTP_PORT}}", str(HS_CONFIG.NGINX_HTTP_PORT)
        )
        nginx_config = nginx_config.replace("{{DOMAIN}}", self.domain)
        nginx_config = nginx_config.replace(
            "{{CLIENT_MAX_BODY_SIZE}}", HS_CONFIG.NGINX_CLIENT_MAX_BODY_SIZE
        )

        # Write config
        with open(self.config_path, "w") as f:
            f.write(nginx_config)

        print(f"  ✓ {self.service_name()} configuration generated")

    def deploy(self) -> docker.models.containers.Container:
        """Deploy Nginx container"""
        print(f"Deploying {self.service_name()}: {self.container_name}")

        # Remove existing container if present
        try:
            existing = self.docker_client.containers.get(self.container_name)
            print(f"  Container already exists, removing...")
            existing.stop()
            existing.remove()
        except docker.errors.NotFound:
            pass

        # Start Nginx container
        container = self.docker_client.containers.run(
            self.image_name(),
            name=self.container_name,
            volumes={
                str(self.nginx_dir.absolute()): {
                    "bind": "/etc/nginx/conf.d",
                    "mode": "ro",
                }
            },
            ports={
                f"{HS_CONFIG.NGINX_HTTP_PORT}/tcp": HS_CONFIG.NGINX_HTTP_PORT,
                f"{HS_CONFIG.NGINX_STATUS_PORT}/tcp": HS_CONFIG.NGINX_STATUS_PORT,
            },
            network=self.network_name,
            detach=True,
            remove=False,
        )

        print(f"  ✓ {self.service_name()} container started")
        return container

    def is_healthy(self) -> bool:
        """Check if Nginx is healthy"""
        try:
            container = self.docker_client.containers.get(self.container_name)

            # Check if container is running
            if container.status != "running":
                return False

            # Check status endpoint
            result = container.exec_run(
                f"curl -sf http://localhost:{HS_CONFIG.NGINX_STATUS_PORT}/nginx_status"
            )

            return result.exit_code == 0

        except docker.errors.NotFound:
            return False
        except Exception:
            return False

    def reload(self) -> bool:
        """
        Reload Nginx configuration without restarting container

        Returns:
            True if reload successful
        """
        try:
            container = self.docker_client.containers.get(self.container_name)
            result = container.exec_run("nginx -s reload")
            return result.exit_code == 0
        except docker.errors.NotFound:
            return False

    def update_config(self, num_workers: int, reload: bool = True) -> bool:
        """
        Update Nginx configuration for new worker count

        Args:
            num_workers: New number of workers
            reload: Whether to reload nginx after update

        Returns:
            True if update successful
        """
        # Update worker count
        old_workers = self.num_workers
        self.num_workers = num_workers

        # Regenerate config
        self.generate_config()

        # Reload if requested
        if reload:
            if self.reload():
                print(
                    f"  ✓ Updated nginx config ({old_workers} → {num_workers} workers)"
                )
                return True
            else:
                print(f"  ✗ Failed to reload nginx")
                return False

        return True

    def get_upstream_summary(self) -> Dict[str, Any]:
        """Get summary of upstream configuration"""
        if self.num_workers > 0:
            upstreams = [
                f"{self.homeserver_id}_worker{i}:8083"
                for i in range(1, self.num_workers + 1)
            ]
            mode = "load_balanced"
        else:
            upstreams = [f"{self.synapse_container}:{HS_CONFIG.SYNAPSE_HTTP_PORT}"]
            mode = "direct"

        return {
            "mode": mode,
            "num_upstreams": len(upstreams),
            "upstreams": upstreams,
            "domain": self.domain,
        }
