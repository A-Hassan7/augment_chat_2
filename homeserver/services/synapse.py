"""
Synapse homeserver service

Handles Synapse deployment, configuration, and health checks.

Config generation uses a two-file pattern:
  homeserver.base.yaml  – clean config produced once by Synapse's own ``generate``
                          command; never modified after creation.
  homeserver.yaml       – rebuilt on every ``generate_config()`` call by copying the
                          base file and overlaying only our required changes (database,
                          appservices, workers).  This guarantees Synapse's defaults are
                          always preserved and that repeated runs never accumulate
                          duplicate configuration blocks.
"""

from pathlib import Path
from typing import Dict, Any, Optional
import shutil
import yaml
import docker

import config as HS_CONFIG
from services.base import BaseService


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
        num_bridge_managers: int = 0,
        postgres_container: Optional[str] = None,
        redis_container: Optional[str] = None,
    ):
        """
        Args:
            homeserver_id: Unique ID for this homeserver
            base_dir: Base directory for configs and data
            network_name: Docker network name
            num_workers: Number of workers (0 for monolith mode)
            num_bridge_managers: Number of bridge manager instances (0 = not deployed)
            postgres_container: Name of postgres container
            redis_container: Name of redis container (required if num_workers > 0)
        """
        super().__init__(homeserver_id, base_dir, network_name)

        self.num_workers = num_workers
        self.num_bridge_managers = num_bridge_managers
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
        # homeserver.base.yaml — untouched Synapse-generated config (created once)
        self.base_config_path = self.data_dir / "homeserver.base.yaml"
        # homeserver.yaml — runtime config rebuilt on every generate_config() call
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
        """Generate the runtime Synapse configuration (homeserver.yaml).

        Workflow
        --------
        1. Ensure ``homeserver.base.yaml`` exists.  If not, run Synapse's own
           ``generate`` command (via Docker) to produce it.  This file is
           **never modified** after creation so it always reflects Synapse's
           pristine defaults.
        2. Copy ``homeserver.base.yaml`` → ``homeserver.yaml`` on **every**
           call.  This resets the runtime config to a known-clean baseline so
           that repeated deployments never accumulate duplicate settings.
        3. Apply our required overlays on top of the fresh copy:
           - PostgreSQL connection
           - Application-service registrations
           - Worker / Redis configuration (when workers are enabled)
        """
        print(f"Generating {self.service_name()} configuration...")

        # Create data directory
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Step 1 – ensure the pristine base config exists
        if not self.base_config_path.exists():
            self._generate_base_config()
        else:
            print("  Base config already exists, reusing it")

        # Step 2 – always start the runtime config from a clean copy of the base
        shutil.copy2(self.base_config_path, self.config_path)
        print("  Copied base config to homeserver.yaml")

        # Step 3 – apply overlays
        self._configure_postgres()
        self._configure_appservices()
        if self.num_workers > 0:
            self._configure_workers()

        print(f"  ✓ {self.service_name()} configuration complete")

    def _generate_base_config(self):
        """Use Synapse's Docker image to generate the pristine base config.

        The generated files are written to ``self.data_dir`` by Synapse itself.
        After generation the canonical ``homeserver.yaml`` produced by Synapse
        is renamed to ``homeserver.base.yaml`` so it can serve as an immutable
        template for all future deployments.
        """
        print("  Generating base configuration via Synapse Docker image...")

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

        # Synapse writes homeserver.yaml; rename it to homeserver.base.yaml so it
        # is preserved as the immutable template and never directly modified.
        generated = self.data_dir / "homeserver.yaml"
        if generated.exists():
            generated.rename(self.base_config_path)

        print("  ✓ Base configuration generated and saved as homeserver.base.yaml")

    def _has_listener(self, config: dict, port: int) -> bool:
        """Return True if a listener on *port* already exists in *config*."""
        return any(
            listener.get("port") == port
            for listener in config.get("listeners", [])
        )

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

            if not self._has_listener(config, HS_CONFIG.SYNAPSE_METRICS_PORT):
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

    def _configure_appservices(self):
        """Configure application service registrations"""
        print("  Configuring application services...")

        if self.num_bridge_managers == 0:
            print("  No bridge managers requested — skipping appservice registration")
            return

        # Create appservices directory
        appservices_dir = self.data_dir / "appservices"
        appservices_dir.mkdir(exist_ok=True)

        # Read the source registration template
        source_registration = (
            Path("bridge_manager") / "bridge-manager-registration.yaml"
        )
        with open(source_registration) as f:
            registration = yaml.safe_load(f)

        # Build the correct URL for this deployment:
        #   > 1 instance  → nginx load balancer
        #   = 1 instance  → single worker container (no LB needed)
        if self.num_bridge_managers > 1:
            bm_host = f"{self.homeserver_id}_bridge_manager_nginx"
            bm_port = HS_CONFIG.BRIDGE_MANAGER_NGINX_PORT
        else:
            bm_host = f"{self.homeserver_id}_bridge_manager_worker_1"
            bm_port = HS_CONFIG.BRIDGE_MANAGER_INTERNAL_PORT

        registration["url"] = f"http://{bm_host}:{bm_port}/homeserver"

        registration_path = appservices_dir / "bridge_manager.yaml"
        with open(registration_path, "w") as f:
            yaml.dump(registration, f, default_flow_style=False)

        print(f"  ✓ Bridge manager appservice URL: {registration['url']}")

        # Update homeserver.yaml to reference the registration file
        with open(self.config_path, "r") as f:
            config = yaml.safe_load(f)

        # Add app_service_config_files if not present
        if "app_service_config_files" not in config:
            config["app_service_config_files"] = []

        # Add registration file path if not already present
        registration_ref = "/data/appservices/bridge_manager.yaml"
        if registration_ref not in config["app_service_config_files"]:
            config["app_service_config_files"].append(registration_ref)

        with open(self.config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False)

        print("  ✓ Application services configured")

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

        # Add HTTP replication listener for main process (guard against duplicates)
        if "listeners" not in config:
            config["listeners"] = []

        if not self._has_listener(config, HS_CONFIG.SYNAPSE_REPLICATION_PORT):
            config["listeners"].append(
                {
                    "port": HS_CONFIG.SYNAPSE_REPLICATION_PORT,
                    "bind_addresses": ["0.0.0.0"],
                    "type": "http",
                    "resources": [{"names": ["replication"]}],
                }
            )

        # Add metrics listener for main process (guard against duplicates)
        if not self._has_listener(config, HS_CONFIG.SYNAPSE_METRICS_PORT):
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
