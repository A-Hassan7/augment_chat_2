"""
Prometheus monitoring service

Handles Prometheus deployment, configuration, and metrics scraping.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
import yaml
import docker

import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import config as HS_CONFIG
from services.base import BaseService


class PrometheusService(BaseService):
    """
    Prometheus metrics collection service

    Manages:
    - Prometheus configuration generation
    - Scrape target configuration
    - Label management with relabel_configs
    - Container deployment
    - Health checking
    """

    def __init__(
        self,
        homeserver_id: str,
        base_dir: Path,
        network_name: str,
        num_workers: int = 0,
        synapse_container: Optional[str] = None,
        nginx_container: Optional[str] = None,
    ):
        """
        Args:
            homeserver_id: Unique ID for this homeserver
            base_dir: Base directory for configs and data
            network_name: Docker network name
            num_workers: Number of workers (for scraping)
            synapse_container: Name of main synapse container
            nginx_container: Name of nginx container
        """
        super().__init__(homeserver_id, base_dir, network_name)

        self.num_workers = num_workers
        self.synapse_container = synapse_container or f"{homeserver_id}_synapse"
        self.nginx_container = nginx_container or f"{homeserver_id}_nginx"
        self.container_name = f"{homeserver_id}_prometheus"

        # Paths
        self.prometheus_dir = base_dir / "prometheus"
        self.config_path = self.prometheus_dir / "prometheus.yml"

    def service_name(self) -> str:
        return "prometheus"

    def image_name(self) -> str:
        return HS_CONFIG.PROMETHEUS_IMAGE

    def validate_config(self) -> bool:
        """Validate Prometheus configuration"""
        if self.num_workers < 0:
            raise ValueError("Number of workers cannot be negative")

        return True

    def generate_config(self) -> None:
        """Generate Prometheus configuration with scrape targets"""
        print(f"Generating {self.service_name()} configuration...")

        # Create prometheus directory
        self.prometheus_dir.mkdir(parents=True, exist_ok=True)

        # Build scrape configs
        scrape_configs = []

        # Synapse main process
        scrape_configs.append(
            {
                "job_name": "synapse",
                "metrics_path": "/_synapse/metrics",
                "static_configs": [
                    {
                        "targets": [
                            f"{self.synapse_container}:{HS_CONFIG.SYNAPSE_METRICS_PORT}"
                        ],
                        "labels": {
                            "instance_name": "main",
                            "homeserver": self.homeserver_id,
                        },
                    }
                ],
                "relabel_configs": [
                    {"source_labels": ["instance_name"], "target_label": "instance"},
                    {"regex": "instance_name", "action": "labeldrop"},
                ],
            }
        )

        # Workers (if any)
        if self.num_workers > 0:
            worker_configs = []
            for i in range(1, self.num_workers + 1):
                worker_configs.append(
                    {
                        "targets": [
                            f"{self.homeserver_id}_worker{i}:{HS_CONFIG.SYNAPSE_METRICS_PORT}"
                        ],
                        "labels": {
                            "instance_name": f"worker{i}",
                            "homeserver": self.homeserver_id,
                        },
                    }
                )

            scrape_configs.append(
                {
                    "job_name": "synapse-workers",
                    "metrics_path": "/_synapse/metrics",
                    "static_configs": worker_configs,
                    "relabel_configs": [
                        {
                            "source_labels": ["instance_name"],
                            "target_label": "instance",
                        },
                        {"regex": "instance_name", "action": "labeldrop"},
                    ],
                }
            )

        # Nginx
        scrape_configs.append(
            {
                "job_name": "nginx",
                "metrics_path": "/nginx_status",
                "static_configs": [
                    {
                        "targets": [
                            f"{self.nginx_container}:{HS_CONFIG.NGINX_STATUS_PORT}"
                        ],
                        "labels": {
                            "instance": "nginx",
                            "homeserver": self.homeserver_id,
                        },
                    }
                ],
            }
        )

        # Build complete config
        prometheus_config = {
            "global": {
                "scrape_interval": HS_CONFIG.PROMETHEUS_SCRAPE_INTERVAL,
                "evaluation_interval": HS_CONFIG.PROMETHEUS_EVALUATION_INTERVAL,
            },
            "scrape_configs": scrape_configs,
        }

        # Write config file
        with open(self.config_path, "w") as f:
            yaml.dump(prometheus_config, f, default_flow_style=False, sort_keys=False)

        print(f"  ✓ {self.service_name()} configuration generated")

    def deploy(self) -> docker.models.containers.Container:
        """Deploy Prometheus container"""
        print(f"Deploying {self.service_name()}: {self.container_name}")

        # Remove existing container if present
        try:
            existing = self.docker_client.containers.get(self.container_name)
            print(f"  Container already exists, removing...")
            existing.stop()
            existing.remove()
        except docker.errors.NotFound:
            pass

        # Start Prometheus container
        container = self.docker_client.containers.run(
            self.image_name(),
            name=self.container_name,
            volumes={
                str(self.prometheus_dir.absolute()): {
                    "bind": "/etc/prometheus",
                    "mode": "ro",
                }
            },
            ports={f"{HS_CONFIG.PROMETHEUS_PORT}/tcp": HS_CONFIG.PROMETHEUS_PORT},
            network=self.network_name,
            detach=True,
            remove=False,
        )

        print(f"  ✓ {self.service_name()} container started")
        return container

    def is_healthy(self) -> bool:
        """Check if Prometheus is healthy"""
        try:
            container = self.docker_client.containers.get(self.container_name)

            # Check if container is running
            if container.status != "running":
                return False

            # Check ready endpoint
            result = container.exec_run(
                f"wget -q -O- http://localhost:{HS_CONFIG.PROMETHEUS_PORT}/-/ready"
            )

            return result.exit_code == 0

        except docker.errors.NotFound:
            return False
        except Exception:
            return False

    def reload(self) -> bool:
        """
        Reload Prometheus configuration without restarting

        Returns:
            True if reload successful
        """
        try:
            container = self.docker_client.containers.get(self.container_name)
            result = container.exec_run(
                f"wget --post-data='' -O- http://localhost:{HS_CONFIG.PROMETHEUS_PORT}/-/reload"
            )
            return result.exit_code == 0
        except docker.errors.NotFound:
            return False

    def update_scrape_targets(self, num_workers: int, reload: bool = True) -> bool:
        """
        Update scrape configuration for new worker count

        Args:
            num_workers: New number of workers
            reload: Whether to reload after update

        Returns:
            True if update successful
        """
        old_workers = self.num_workers
        self.num_workers = num_workers

        # Regenerate config
        self.generate_config()

        # Reload if requested
        if reload:
            if self.reload():
                print(
                    f"  ✓ Updated prometheus targets ({old_workers} → {num_workers} workers)"
                )
                return True
            else:
                print(f"  ✗ Failed to reload prometheus")
                return False

        return True

    def get_scrape_summary(self) -> Dict[str, Any]:
        """Get summary of scrape targets"""
        targets = {
            "synapse_main": f"{self.synapse_container}:{HS_CONFIG.SYNAPSE_METRICS_PORT}",
            "nginx": f"{self.nginx_container}:{HS_CONFIG.NGINX_STATUS_PORT}",
        }

        if self.num_workers > 0:
            targets["workers"] = [
                f"{self.homeserver_id}_worker{i}:{HS_CONFIG.SYNAPSE_METRICS_PORT}"
                for i in range(1, self.num_workers + 1)
            ]

        return {
            "scrape_interval": HS_CONFIG.PROMETHEUS_SCRAPE_INTERVAL,
            "num_targets": 2 + self.num_workers,  # main + nginx + workers
            "targets": targets,
        }
