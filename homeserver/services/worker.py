"""
Worker service for distributed Synapse deployment

Manages deployment of Synapse worker containers for load distribution.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
import yaml
import socket
import random
import docker

import config as HS_CONFIG
from services.base import BaseService


class WorkerService(BaseService):
    """
    Synapse worker service

    Manages:
    - Worker configuration generation
    - Worker container deployment
    - Port allocation with collision avoidance
    - Health checking per worker
    - Batch deployment
    """

    def __init__(
        self,
        homeserver_id: str,
        base_dir: Path,
        network_name: str,
        num_workers: int = 1,
        synapse_container: Optional[str] = None,
    ):
        """
        Args:
            homeserver_id: Unique ID for this homeserver
            base_dir: Base directory for configs and data
            network_name: Docker network name
            num_workers: Number of workers to deploy
            synapse_container: Name of main synapse container
        """
        # Set num_workers before super().__init__ since service_name() needs it
        self.num_workers = num_workers

        super().__init__(homeserver_id, base_dir, network_name)

        self.synapse_container = synapse_container or f"{homeserver_id}_synapse"

        # Paths
        self.data_dir = base_dir / "data"
        self.workers_dir = self.data_dir / "workers"

        # Track deployed workers
        self.deployed_workers: List[Dict[str, Any]] = []

    def service_name(self) -> str:
        return f"workers ({self.num_workers})"

    def image_name(self) -> str:
        return HS_CONFIG.SYNAPSE_IMAGE

    def validate_config(self) -> bool:
        """Validate worker configuration"""
        if self.num_workers < 1:
            raise ValueError("Number of workers must be at least 1")

        if self.num_workers > 50:
            raise ValueError("Number of workers cannot exceed 50")

        return True

    def generate_config(self) -> None:
        """Generate worker configuration files"""
        print(f"Generating configurations for {self.num_workers} workers...")

        # Create workers directory
        self.workers_dir.mkdir(parents=True, exist_ok=True)

        # Generate config for each worker
        for i in range(1, self.num_workers + 1):
            self._create_worker_config(i)

        print(f"  ✓ Generated {self.num_workers} worker configurations")

    def _create_worker_config(self, worker_num: int):
        """
        Create configuration file for a single worker

        Args:
            worker_num: Worker number (1-indexed)
        """
        worker_name = f"generic_worker{worker_num}"
        worker_config = {
            "worker_app": "synapse.app.generic_worker",
            "worker_name": worker_name,
            "worker_listeners": [
                {
                    "type": "http",
                    "port": 8083,
                    "x_forwarded": True,
                    "resources": [{"names": ["client", "federation"]}],
                },
                {
                    "type": "http",
                    "port": 9093,
                    "resources": [{"names": ["replication"]}],
                },
                {
                    "type": "http",
                    "port": 9000,
                    "resources": [{"names": ["metrics"]}],
                },
            ],
        }

        worker_config_path = self.workers_dir / f"worker{worker_num}.yaml"
        with open(worker_config_path, "w") as f:
            yaml.dump(worker_config, f, default_flow_style=False)

    def deploy(self) -> docker.models.containers.Container:
        """
        Deploy all worker containers

        Returns:
            The last deployed container (for compatibility with base class)
        """
        print(f"Deploying {self.num_workers} worker containers...")

        last_container = None
        for i in range(1, self.num_workers + 1):
            container = self._deploy_worker(i)
            last_container = container

            # Small delay between worker starts to avoid port collisions
            if i < self.num_workers:
                import time

                time.sleep(1.0)

        print(f"  ✓ All {self.num_workers} workers deployed")
        return last_container

    def _deploy_worker(self, worker_num: int) -> docker.models.containers.Container:
        """
        Deploy a single worker container

        Args:
            worker_num: Worker number (1-indexed)

        Returns:
            The deployed container
        """
        worker_container_name = f"{self.homeserver_id}_worker{worker_num}"

        # Find available port
        start_port = HS_CONFIG.WORKER_BASE_PORT + worker_num
        worker_port = self._find_available_port(start_port)

        # Remove existing container if present
        try:
            existing = self.docker_client.containers.get(worker_container_name)
            existing.stop()
            existing.remove()
        except docker.errors.NotFound:
            pass

        # Start worker container
        container = self.docker_client.containers.run(
            self.image_name(),
            name=worker_container_name,
            command=[
                "run",
                "-m",
                "synapse.app.generic_worker",
                "--config-path=/data/homeserver.yaml",
                f"--config-path=/data/workers/worker{worker_num}.yaml",
            ],
            volumes={str(self.data_dir.absolute()): {"bind": "/data", "mode": "rw"}},
            ports={f"8083/tcp": worker_port},
            network=self.network_name,
            detach=True,
            remove=False,
        )

        # Track deployed worker
        self.deployed_workers.append(
            {
                "number": worker_num,
                "container_name": worker_container_name,
                "port": worker_port,
                "container": container,
            }
        )

        return container

    def _find_available_port(self, start_port: int) -> int:
        """
        Find an available port with collision avoidance

        Args:
            start_port: Starting port for search

        Returns:
            Available port number
        """
        max_attempts = HS_CONFIG.WORKER_PORT_MAX_ATTEMPTS

        # Add random offset to reduce collision probability
        offset = random.randint(0, HS_CONFIG.WORKER_PORT_RANDOM_OFFSET)

        for attempt in range(max_attempts):
            port = start_port + offset + attempt
            if port > 65535:
                port = start_port + attempt

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    sock.bind(("0.0.0.0", port))
                    return port
                except OSError:
                    continue

        raise RuntimeError(f"Could not find available port starting from {start_port}")

    def is_healthy(self) -> bool:
        """Check if all workers are healthy"""
        if not self.deployed_workers:
            # Try to find workers if not tracked
            for i in range(1, self.num_workers + 1):
                worker_name = f"{self.homeserver_id}_worker{i}"
                try:
                    container = self.docker_client.containers.get(worker_name)
                    if container.status != "running":
                        return False
                except docker.errors.NotFound:
                    return False
            return True

        # Check tracked workers
        for worker in self.deployed_workers:
            try:
                container = self.docker_client.containers.get(worker["container_name"])
                container.reload()  # Refresh container state
                if container.status != "running":
                    return False

                # Check logs for successful startup message
                logs = container.logs(tail=100).decode("utf-8", errors="ignore")
                if "Synapse now listening" not in logs:
                    return False

            except docker.errors.NotFound:
                return False
            except Exception:
                return False

        return True

    def cleanup(self) -> None:
        """Remove all worker containers"""
        print(f"Cleaning up {self.num_workers} workers...")

        for i in range(1, self.num_workers + 1):
            worker_name = f"{self.homeserver_id}_worker{i}"
            try:
                container = self.docker_client.containers.get(worker_name)
                container.stop()
                container.remove()
                print(f"  ✓ Removed {worker_name}")
            except docker.errors.NotFound:
                pass

        self.deployed_workers = []

    def get_status(self) -> Dict[str, Any]:
        """Get detailed status of all workers"""
        workers_status = []

        for i in range(1, self.num_workers + 1):
            worker_name = f"{self.homeserver_id}_worker{i}"
            try:
                container = self.docker_client.containers.get(worker_name)
                workers_status.append(
                    {
                        "number": i,
                        "name": worker_name,
                        "status": container.status,
                        "healthy": container.status == "running",
                    }
                )
            except docker.errors.NotFound:
                workers_status.append(
                    {
                        "number": i,
                        "name": worker_name,
                        "status": "not deployed",
                        "healthy": False,
                    }
                )

        return {
            "name": self.service_name(),
            "num_workers": self.num_workers,
            "workers": workers_status,
            "healthy": all(w["healthy"] for w in workers_status),
        }

    def get_deployed_ports(self) -> List[int]:
        """Get list of ports workers are deployed on"""
        return [w["port"] for w in self.deployed_workers]
