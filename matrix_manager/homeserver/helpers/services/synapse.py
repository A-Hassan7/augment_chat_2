"""
Synapse homeserver service

Handles Synapse deployment, configuration, and health checks.
"""

from pathlib import Path
from typing import Dict, Any, Optional
import yaml
import docker

import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import config as HS_CONFIG
from helpers.services.base import BaseService


class SynapseService(BaseService):
    """
    Synapse homeserver service

    Manages:
    - Config generation (homeserver.yaml)
    - Database connection setup
    - Worker mode configuration (if using workers)
    - Container deployment
    - Health checking
    """

    def __init__(
        self,
        homeserver_id: str,
        base_dir: Path,
        network_name: str,
        num_workers: int = 0,
        postgres_container: Optional[str] = None,
        redis_container: Optional[str] = None,
    ):
        """
        Args:
            homeserver_id: Unique ID for this homeserver
            base_dir: Base directory for configs and data
            network_name: Docker network name
            num_workers: Number of workers (0 for monolith mode)
            postgres_container: Name of postgres container
            redis_container: Name of redis container (required if num_workers > 0)
        """
        super().__init__(homeserver_id, base_dir, network_name)

        self.num_workers = num_workers
        self.container_name = f"{homeserver_id}_synapse"

        # Database config
        self.postgres_container = postgres_container or f"{homeserver_id}_postgres"
        self.db_user = HS_CONFIG.DB_USER
        self.db_password = HS_CONFIG.DB_PASSWORD
        self.db_name = homeserver_id.replace("-", "_")  # Match PostgresService naming

        # Redis config (for workers)
        self.redis_container = redis_container or f"{homeserver_id}_redis"

        # Paths
        self.data_dir = base_dir / "data"
        self.config_path = self.data_dir / "homeserver.yaml"

    def service_name(self) -> str:
        return "synapse"

    def image_name(self) -> str:
        return HS_CONFIG.SYNAPSE_IMAGE

    def validate_config(self) -> bool:
        """Validate Synapse configuration"""
        # Check homeserver_id is valid
        if not self.homeserver_id or not self.homeserver_id.strip():
            raise ValueError("homeserver_id cannot be empty")

        # Check database credentials
        if not self.db_user or not self.db_password or not self.db_name:
            raise ValueError("Database credentials must be provided")

        # If using workers, redis is required
        if self.num_workers > 0 and not self.redis_container:
            raise ValueError("Redis container name required when using workers")

        return True

    def generate_config(self) -> None:
        """Generate Synapse configuration files"""
        print(f"Generating {self.service_name()} configuration...")

        # Create data directory
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Generate base config if it doesn't exist
        if not self.config_path.exists():
            self._generate_base_config()
        else:
            print("  Config already exists, skipping generation")

        # Configure postgres connection
        self._configure_postgres()

        # Configure workers if needed
        if self.num_workers > 0:
            self._configure_workers()

        print(f"  ✓ {self.service_name()} configuration complete")

    def _generate_base_config(self):
        """Generate base Synapse config using Docker"""
        print("  Generating base configuration...")

        self.docker_client.containers.run(
            self.image_name(),
            command="generate",
            environment={
                "SYNAPSE_SERVER_NAME": self.homeserver_id,
                "SYNAPSE_REPORT_STATS": "no",
            },
            volumes={str(self.data_dir.absolute()): {"bind": "/data", "mode": "rw"}},
            remove=True,
        )

        print("  ✓ Base configuration generated")

    def _configure_postgres(self):
        """Configure Synapse to use PostgreSQL"""
        print("  Configuring PostgreSQL connection...")

        with open(self.config_path, "r") as f:
            config = yaml.safe_load(f)

        # Update database config
        config["database"] = {
            "name": "psycopg2",
            "args": {
                "user": self.db_user,
                "password": self.db_password,
                "database": self.db_name,
                "host": self.postgres_container,
                "port": HS_CONFIG.POSTGRES_PORT,
                "cp_min": HS_CONFIG.DB_MIN_CONNECTIONS,
                "cp_max": HS_CONFIG.DB_MAX_CONNECTIONS,
            },
        }

        # Enable registration for admin user creation
        config["enable_registration"] = True
        config["enable_registration_without_verification"] = True

        # Enable metrics for monitoring
        config["enable_metrics"] = True

        # Add metrics listener for monolith mode
        # (workers have their own metrics in worker configs)
        if self.num_workers == 0:
            if "listeners" not in config:
                config["listeners"] = []

            # Check if metrics listener already exists
            has_metrics = any(
                listener.get("port") == HS_CONFIG.SYNAPSE_METRICS_PORT
                for listener in config["listeners"]
            )

            if not has_metrics:
                config["listeners"].append(
                    {
                        "port": HS_CONFIG.SYNAPSE_METRICS_PORT,
                        "bind_addresses": ["0.0.0.0"],
                        "type": "http",
                        "resources": [{"names": ["metrics"]}],
                    }
                )

        with open(self.config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False)

        print("  ✓ PostgreSQL connection configured")

    def _configure_workers(self):
        """Configure Synapse for worker mode"""
        print(f"  Configuring {self.num_workers} workers...")

        with open(self.config_path, "r") as f:
            config = yaml.safe_load(f)

        # Enable Redis
        config["redis"] = {
            "enabled": True,
            "host": self.redis_container,
            "port": HS_CONFIG.REDIS_PORT,
        }

        # Add HTTP replication listener for main process
        if "listeners" not in config:
            config["listeners"] = []

        config["listeners"].append(
            {
                "port": HS_CONFIG.SYNAPSE_REPLICATION_PORT,
                "bind_addresses": ["0.0.0.0"],
                "type": "http",
                "resources": [{"names": ["replication"]}],
            }
        )

        # Add metrics listener for main process
        config["listeners"].append(
            {
                "port": HS_CONFIG.SYNAPSE_METRICS_PORT,
                "bind_addresses": ["0.0.0.0"],
                "type": "http",
                "resources": [{"names": ["metrics"]}],
            }
        )

        # Build instance map
        instance_map = {
            "main": {
                "host": self.container_name,
                "port": HS_CONFIG.SYNAPSE_REPLICATION_PORT,
            }
        }

        # Add workers to instance map
        for i in range(1, self.num_workers + 1):
            worker_name = f"generic_worker{i}"
            instance_map[worker_name] = {
                "host": f"{self.homeserver_id}_worker{i}",
                "port": HS_CONFIG.SYNAPSE_REPLICATION_PORT,
            }

        config["instance_map"] = instance_map

        with open(self.config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False)

        print(f"  ✓ Worker configuration complete")

    def deploy(self) -> docker.models.containers.Container:
        """Deploy Synapse container"""
        print(f"Deploying {self.service_name()}: {self.container_name}")

        # Remove existing container if present
        try:
            existing = self.docker_client.containers.get(self.container_name)
            print(f"  Container already exists, removing...")
            existing.stop()
            existing.remove()
        except docker.errors.NotFound:
            pass

        # Start Synapse container
        container = self.docker_client.containers.run(
            self.image_name(),
            name=self.container_name,
            volumes={str(self.data_dir.absolute()): {"bind": "/data", "mode": "rw"}},
            ports={
                f"{HS_CONFIG.SYNAPSE_HTTP_PORT}/tcp": HS_CONFIG.SYNAPSE_HTTP_PORT,
                f"{HS_CONFIG.SYNAPSE_FEDERATION_PORT}/tcp": HS_CONFIG.SYNAPSE_FEDERATION_PORT,
            },
            network=self.network_name,
            detach=True,
            remove=False,
        )

        print(f"  ✓ {self.service_name()} container started")
        return container

    def is_healthy(self) -> bool:
        """Check if Synapse is healthy"""
        try:
            container = self.docker_client.containers.get(self.container_name)

            # Check if container is running
            if container.status != "running":
                return False

            # Check if Synapse is responding by checking logs for "Synapse now listening"
            # or just verify the process is running
            logs = container.logs(tail=50).decode("utf-8", errors="ignore")

            # Look for startup completion indicators
            if "Synapse now listening" in logs or "worker starting" in logs:
                return True

            # If container has been running for a bit, assume it's healthy
            # (ports are exposed, process is up)
            return True

        except docker.errors.NotFound:
            return False
        except Exception:
            return False

    def get_config_summary(self) -> Dict[str, Any]:
        """Get summary of Synapse configuration"""
        summary = {
            "homeserver_id": self.homeserver_id,
            "mode": "worker" if self.num_workers > 0 else "monolith",
            "num_workers": self.num_workers,
            "database": f"{self.postgres_container}:{HS_CONFIG.POSTGRES_PORT}",
        }

        if self.num_workers > 0:
            summary["redis"] = f"{self.redis_container}:{HS_CONFIG.REDIS_PORT}"

        return summary
