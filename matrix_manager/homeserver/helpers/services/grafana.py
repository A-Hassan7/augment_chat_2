"""
Grafana visualization service

Handles Grafana deployment, datasource configuration, and dashboard provisioning.
"""

from pathlib import Path
from typing import Dict, Any, Optional
import json
import docker

import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import config as HS_CONFIG
from helpers.services.base import BaseService


class GrafanaService(BaseService):
    """
    Grafana visualization service

    Manages:
    - Grafana container deployment
    - Datasource provisioning (Prometheus)
    - Dashboard provisioning
    - Configuration from templates
    - Health checking
    """

    def __init__(
        self,
        homeserver_id: str,
        base_dir: Path,
        network_name: str,
        prometheus_container: Optional[str] = None,
    ):
        """
        Args:
            homeserver_id: Unique ID for this homeserver
            base_dir: Base directory for configs and data
            network_name: Docker network name
            prometheus_container: Name of prometheus container
        """
        super().__init__(homeserver_id, base_dir, network_name)

        self.prometheus_container = (
            prometheus_container or f"{homeserver_id}_prometheus"
        )
        self.container_name = f"{homeserver_id}_grafana"

        # Paths
        self.grafana_dir = base_dir / "grafana"
        self.grafana_provisioning_dir = self.grafana_dir / "provisioning"
        self.templates_dir = (
            Path(__file__).parent.parent.parent / "templates" / "grafana"
        )

    def service_name(self) -> str:
        return "grafana"

    def image_name(self) -> str:
        return HS_CONFIG.GRAFANA_IMAGE

    def validate_config(self) -> bool:
        """Validate Grafana configuration"""
        # Check if templates directory exists
        if not self.templates_dir.exists():
            raise ValueError(
                f"Grafana templates directory not found: {self.templates_dir}"
            )

        # Check for datasources template
        datasources_template = self.templates_dir / "datasources.yml"
        if not datasources_template.exists():
            raise ValueError(f"Datasources template not found: {datasources_template}")

        return True

    def generate_config(self) -> None:
        """Generate Grafana provisioning configuration"""
        print(f"Generating {self.service_name()} configuration...")

        # Create directories
        self.grafana_dir.mkdir(parents=True, exist_ok=True)
        datasources_dir = self.grafana_provisioning_dir / "datasources"
        datasources_dir.mkdir(parents=True, exist_ok=True)

        # Template variables for substitution
        template_vars = {
            "{{homeserver_id}}": self.homeserver_id,
            "{{prometheus_container}}": self.prometheus_container,
        }

        def substitute_template(content: str) -> str:
            """Replace template variables in content"""
            for placeholder, value in template_vars.items():
                content = content.replace(placeholder, value)
            return content

        # Process datasources.yml template
        datasources_template = self.templates_dir / "datasources.yml"
        if datasources_template.exists():
            with open(datasources_template, "r") as f:
                content = substitute_template(f.read())
            datasources_path = datasources_dir / "datasources.yml"
            with open(datasources_path, "w") as f:
                f.write(content)
        else:
            print("  Warning: datasources.yml template not found")

        # Process dashboard templates for API import
        self._processed_dashboards = []
        dashboard_files = list(self.templates_dir.glob("*.json"))

        for template_file in dashboard_files:
            with open(template_file, "r") as f:
                content = substitute_template(f.read())
            self._processed_dashboards.append(
                {"name": template_file.name, "dashboard": json.loads(content)}
            )

        print(f"  ✓ {self.service_name()} configuration generated")

    def deploy(self) -> docker.models.containers.Container:
        """Deploy Grafana container"""
        print(f"Deploying {self.service_name()}: {self.container_name}")

        # Remove existing container if present
        try:
            existing = self.docker_client.containers.get(self.container_name)
            print(f"  Container already exists, removing...")
            existing.stop()
            existing.remove()
        except docker.errors.NotFound:
            pass

        # Start Grafana container
        container = self.docker_client.containers.run(
            self.image_name(),
            name=self.container_name,
            environment={
                "GF_SECURITY_ADMIN_PASSWORD": HS_CONFIG.GRAFANA_ADMIN_PASSWORD,
                "GF_AUTH_ANONYMOUS_ENABLED": (
                    "true" if HS_CONFIG.GRAFANA_ANONYMOUS_ACCESS else "false"
                ),
                "GF_AUTH_ANONYMOUS_ORG_ROLE": HS_CONFIG.GRAFANA_ANONYMOUS_ROLE,
            },
            volumes={
                str(self.grafana_dir.absolute()): {
                    "bind": "/var/lib/grafana",
                    "mode": "rw",
                },
                str(self.grafana_provisioning_dir.absolute()): {
                    "bind": "/etc/grafana/provisioning",
                    "mode": "ro",
                },
            },
            ports={f"{HS_CONFIG.GRAFANA_PORT}/tcp": HS_CONFIG.GRAFANA_PORT},
            network=self.network_name,
            detach=True,
            remove=False,
        )

        print(f"  ✓ {self.service_name()} container started")

        # Import dashboards via API for editability
        self._import_dashboards()

        return container

    def is_healthy(self) -> bool:
        """Check if Grafana is healthy"""
        try:
            container = self.docker_client.containers.get(self.container_name)

            # Check if container is running
            if container.status != "running":
                return False

            # Check health endpoint
            result = container.exec_run(
                f"wget -q -O- http://localhost:{HS_CONFIG.GRAFANA_PORT}/api/health"
            )

            return result.exit_code == 0

        except docker.errors.NotFound:
            return False
        except Exception:
            return False

    def _import_dashboards(self) -> None:
        """Import dashboards via API so they're editable in UI"""
        if not self._processed_dashboards:
            return

        print(f"  Importing {len(self._processed_dashboards)} dashboards via API...")

        import time
        import requests

        grafana_url = f"http://localhost:{HS_CONFIG.GRAFANA_PORT}"
        auth = (HS_CONFIG.GRAFANA_ADMIN_USER, HS_CONFIG.GRAFANA_ADMIN_PASSWORD)

        # Wait for Grafana to be ready
        for i in range(HS_CONFIG.GRAFANA_STARTUP_TIMEOUT // 2):
            try:
                response = requests.get(f"{grafana_url}/api/health")
                if response.status_code == 200:
                    break
            except requests.exceptions.ConnectionError:
                pass
            time.sleep(2)
        else:
            print("  Warning: Grafana didn't start in time, skipping dashboard import")
            return

        # Import each dashboard
        for dashboard_info in self._processed_dashboards:
            dashboard_payload = {
                "dashboard": dashboard_info["dashboard"],
                "overwrite": True,
                "message": f"Imported from template: {dashboard_info['name']}",
            }

            try:
                response = requests.post(
                    f"{grafana_url}/api/dashboards/db",
                    json=dashboard_payload,
                    auth=auth,
                    headers={"Content-Type": "application/json"},
                )

                if response.status_code == 200:
                    print(f"    ✓ Imported {dashboard_info['name']}")
                else:
                    print(
                        f"    ✗ Failed to import {dashboard_info['name']}: {response.text}"
                    )
            except Exception as e:
                print(f"    ✗ Error importing {dashboard_info['name']}: {e}")

    def get_dashboard_url(self) -> str:
        """Get Grafana dashboard URL"""
        return f"http://localhost:{HS_CONFIG.GRAFANA_PORT}"

    def get_config_summary(self) -> Dict[str, Any]:
        """Get summary of Grafana configuration"""
        return {
            "url": self.get_dashboard_url(),
            "admin_user": HS_CONFIG.GRAFANA_ADMIN_USER,
            "prometheus_datasource": f"http://{self.prometheus_container}:{HS_CONFIG.PROMETHEUS_PORT}",
            "anonymous_access": HS_CONFIG.GRAFANA_ANONYMOUS_ACCESS,
            "dashboards_count": (
                len(self._processed_dashboards)
                if hasattr(self, "_processed_dashboards")
                else 0
            ),
        }
