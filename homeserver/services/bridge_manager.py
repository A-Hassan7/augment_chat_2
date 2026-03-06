"""
Bridge Manager services for horizontal scaling.

Two service classes follow the same pattern as WorkerService / NginxService:

- BridgeManagerService: Deploy N stateless bridge manager instance containers.
- BridgeManagerNginxService: Deploy the nginx load balancer in front of them.

Architecture (N instances behind an nginx LB):

    Synapse / Bridges
        → {hs_id}_bridge_manager_nginx:{BRIDGE_MANAGER_NGINX_PORT}
            → {hs_id}_bridge_manager_worker_1:{BRIDGE_MANAGER_INTERNAL_PORT}
            → {hs_id}_bridge_manager_worker_2:{BRIDGE_MANAGER_INTERNAL_PORT}
            → …
            → {hs_id}_bridge_manager_worker_N:{BRIDGE_MANAGER_INTERNAL_PORT}

The bridge-manager-registration.yaml URL must point at the nginx LB so that
Synapse sees a single stable endpoint regardless of how many instances run.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
import docker

import config as HS_CONFIG
from services.base import BaseService


class BridgeManagerService(BaseService):
    """
    Deploys N stateless bridge manager appservice instances.

    Each instance is an identical container built from Dockerfile.bridge_manager.
    All instances share the same PostgreSQL database and are therefore stateless
    from a routing perspective — any instance can handle any request.

    The Docker socket is mounted so each instance can orchestrate bridge
    containers.  A volume is shared for generated bridge configurations.
    """

    def __init__(
        self,
        homeserver_id: str,
        base_dir: Path,
        network_name: str,
        num_instances: int = 1,
        env_file: Optional[Path] = None,
    ):
        """
        Args:
            homeserver_id: Unique ID for this homeserver
            base_dir: Base directory for configs and data
            network_name: Docker network name
            num_instances: Number of bridge manager instances to deploy
            env_file: Path to .env file to source environment variables from
        """
        self.num_instances = num_instances
        super().__init__(homeserver_id, base_dir, network_name)

        self.env_file = env_file or (Path(__file__).parent.parent / ".env")

        # Shared volume name for generated bridge configs
        self.configs_volume = f"{homeserver_id}_bridge_manager_configs"

        # Track deployed instances
        self.deployed_instances: List[Dict[str, Any]] = []

    def service_name(self) -> str:
        return f"bridge_manager ({self.num_instances} instances)"

    def image_name(self) -> str:
        return HS_CONFIG.BRIDGE_MANAGER_IMAGE

    def validate_config(self) -> bool:
        """Validate bridge manager configuration."""
        if self.num_instances < 1:
            raise ValueError("Number of bridge manager instances must be at least 1")

        if self.num_instances > 20:
            raise ValueError("Number of bridge manager instances cannot exceed 20")

        return True

    def generate_config(self) -> None:
        """No static config files — bridge manager reads all config from env/DB."""
        print(f"Preparing {self.num_instances} bridge manager instance(s)...")
        self._ensure_configs_volume()
        print(f"  ✓ Bridge manager configs volume ready: {self.configs_volume}")

    def _ensure_configs_volume(self) -> None:
        """Create the shared configs volume if it does not already exist."""
        try:
            self.docker_client.volumes.get(self.configs_volume)
        except docker.errors.NotFound:
            self.docker_client.volumes.create(self.configs_volume)

    def _load_env_vars(self) -> Dict[str, str]:
        """Load environment variables from the .env file."""
        env_vars: Dict[str, str] = {}
        if self.env_file.exists():
            with open(self.env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, value = line.partition("=")
                        env_vars[key.strip()] = value.strip()
        return env_vars

    def deploy(self) -> docker.models.containers.Container:
        """
        Deploy all bridge manager instance containers.

        Returns:
            The last deployed container (for compatibility with BaseService).
        """
        print(f"Deploying {self.num_instances} bridge manager instance(s)...")

        env_vars = self._load_env_vars()
        last_container = None

        for i in range(1, self.num_instances + 1):
            container = self._deploy_instance(i, env_vars)
            last_container = container

        print(f"  ✓ All {self.num_instances} bridge manager instance(s) deployed")
        return last_container

    def _deploy_instance(
        self, instance_num: int, env_vars: Dict[str, str]
    ) -> docker.models.containers.Container:
        """
        Deploy a single bridge manager instance container.

        Args:
            instance_num: Instance number (1-indexed)
            env_vars: Environment variables to inject

        Returns:
            The deployed container
        """
        container_name = f"{self.homeserver_id}_bridge_manager_worker_{instance_num}"

        # Remove existing container if present
        try:
            existing = self.docker_client.containers.get(container_name)
            existing.stop()
            existing.remove()
        except docker.errors.NotFound:
            pass

        # Override the instance ID so each container has a unique identity
        instance_env = dict(env_vars)
        instance_env["BRIDGE_MANAGER_INSTANCE_ID"] = (
            f"{self.homeserver_id}_bridge_manager_{instance_num}"
        )

        # Rewrite database URLs for in-container use: replace localhost /
        # 127.0.0.1 with the postgres container name so the bridge manager
        # can reach the database over the shared Docker network.
        postgres_host = f"{self.homeserver_id}_postgres"
        for key in ("BRIDGE_MANAGER_DATABASE_URL", "SYNAPSE_DATABASE_URL"):
            if key in instance_env:
                instance_env[key] = (
                    instance_env[key]
                    .replace("@localhost:", f"@{postgres_host}:")
                    .replace("@127.0.0.1:", f"@{postgres_host}:")
                )

        # Rewrite HOMESERVER_URL so the bridge manager can reach Synapse
        # over the shared Docker network rather than trying localhost.
        synapse_host = f"{self.homeserver_id}_synapse"
        if "HOMESERVER_URL" in instance_env:
            instance_env["HOMESERVER_URL"] = (
                instance_env["HOMESERVER_URL"]
                .replace("://localhost:", f"://{synapse_host}:")
                .replace("://127.0.0.1:", f"://{synapse_host}:")
            )

        container = self.docker_client.containers.run(
            self.image_name(),
            name=container_name,
            environment=instance_env,
            volumes={
                # Docker socket so the instance can orchestrate bridge containers
                "/var/run/docker.sock": {
                    "bind": "/var/run/docker.sock",
                    "mode": "rw",
                },
                # Shared volume for generated bridge configs
                self.configs_volume: {
                    "bind": "/app/bridge_manager/orchestrator/configs",
                    "mode": "rw",
                },
            },
            # Single instance: expose the nginx port on the host mapped to the internal
            # worker port so bridges always reach the bridge manager on the same port
            # regardless of whether a LB is in front.
            # Multiple instances: the nginx LB handles host exposure — don't bind here
            # (workers can't share a host port).
            ports=(
                {
                    f"{HS_CONFIG.BRIDGE_MANAGER_NGINX_PORT}/tcp": (
                        HS_CONFIG.BRIDGE_MANAGER_INTERNAL_PORT
                    )
                }
                if self.num_instances == 1
                else {}
            ),
            # Allow reaching host services (bridges exposed on host ports)
            extra_hosts={"host.docker.internal": "host-gateway"},
            network=self.network_name,
            detach=True,
            remove=False,
        )

        self.deployed_instances.append(
            {
                "number": instance_num,
                "container_name": container_name,
                "container": container,
            }
        )

        return container

    def is_healthy(self) -> bool:
        """Check if all bridge manager instances are running."""
        for i in range(1, self.num_instances + 1):
            name = f"{self.homeserver_id}_bridge_manager_worker_{i}"
            try:
                container = self.docker_client.containers.get(name)
                container.reload()
                if container.status != "running":
                    return False
            except docker.errors.NotFound:
                return False
        return True

    def cleanup(self) -> None:
        """Stop and remove all bridge manager instance containers."""
        for i in range(1, self.num_instances + 1):
            name = f"{self.homeserver_id}_bridge_manager_worker_{i}"
            try:
                container = self.docker_client.containers.get(name)
                container.stop()
                container.remove()
                print(f"  ✓ Removed {name}")
            except docker.errors.NotFound:
                pass
        self.deployed_instances = []

    def get_status(self) -> Dict[str, Any]:
        """Return status of every bridge manager instance."""
        instances_status = []
        for i in range(1, self.num_instances + 1):
            name = f"{self.homeserver_id}_bridge_manager_worker_{i}"
            try:
                container = self.docker_client.containers.get(name)
                instances_status.append(
                    {
                        "number": i,
                        "name": name,
                        "status": container.status,
                        "healthy": container.status == "running",
                    }
                )
            except docker.errors.NotFound:
                instances_status.append(
                    {
                        "number": i,
                        "name": name,
                        "status": "not deployed",
                        "healthy": False,
                    }
                )

        return {
            "name": self.service_name(),
            "num_instances": self.num_instances,
            "instances": instances_status,
            "healthy": all(inst["healthy"] for inst in instances_status),
        }


class BridgeManagerNginxService(BaseService):
    """
    Nginx load balancer that distributes requests across bridge manager instances.

    Container name: {homeserver_id}_bridge_manager_nginx
    Listens on:     BRIDGE_MANAGER_NGINX_PORT (default 5000)
    Status port:    BRIDGE_MANAGER_NGINX_STATUS_PORT (default 5080)

    The bridge-manager-registration.yaml should point at this container:
        url: "http://{homeserver_id}_bridge_manager_nginx:{BRIDGE_MANAGER_NGINX_PORT}/homeserver"
    """

    def __init__(
        self,
        homeserver_id: str,
        base_dir: Path,
        network_name: str,
        num_instances: int = 1,
    ):
        """
        Args:
            homeserver_id: Unique ID for this homeserver
            base_dir: Base deployment directory
            network_name: Docker network name
            num_instances: Number of bridge manager instances to load balance
        """
        self.num_instances = num_instances
        super().__init__(homeserver_id, base_dir, network_name)

        self.container_name = f"{homeserver_id}_bridge_manager_nginx"

        # Paths
        self.nginx_bm_dir = base_dir / "nginx_bm"
        self.config_path = self.nginx_bm_dir / "bridge_manager.conf"
        self.template_path = Path("templates") / "nginx_bm_template.conf"

    def service_name(self) -> str:
        return "bridge_manager_nginx"

    def image_name(self) -> str:
        return HS_CONFIG.NGINX_IMAGE

    def validate_config(self) -> bool:
        """Validate nginx bridge manager configuration."""
        if self.num_instances < 1:
            raise ValueError("num_instances must be at least 1")

        if not self.template_path.exists():
            raise ValueError(
                f"Bridge manager nginx template not found: {self.template_path}"
            )

        return True

    def generate_config(self) -> None:
        """Generate nginx config for bridge manager load balancing."""
        print(f"Generating {self.service_name()} configuration...")

        self.nginx_bm_dir.mkdir(parents=True, exist_ok=True)

        with open(self.template_path) as f:
            template = f.read()

        # Build round-robin upstream block (stateless instances)
        upstream_servers = "\n".join(
            f"    server {self.homeserver_id}_bridge_manager_worker_{i}"
            f":{HS_CONFIG.BRIDGE_MANAGER_INTERNAL_PORT};"
            for i in range(1, self.num_instances + 1)
        )

        nginx_config = template.replace("{{UPSTREAM_SERVERS}}", upstream_servers)
        nginx_config = nginx_config.replace(
            "{{NGINX_STATUS_PORT}}", str(HS_CONFIG.BRIDGE_MANAGER_NGINX_STATUS_PORT)
        )
        nginx_config = nginx_config.replace(
            "{{NGINX_HTTP_PORT}}", str(HS_CONFIG.BRIDGE_MANAGER_NGINX_PORT)
        )
        nginx_config = nginx_config.replace(
            "{{CLIENT_MAX_BODY_SIZE}}", HS_CONFIG.NGINX_CLIENT_MAX_BODY_SIZE
        )

        with open(self.config_path, "w") as f:
            f.write(nginx_config)

        print(f"  ✓ {self.service_name()} configuration generated")

    def deploy(self) -> docker.models.containers.Container:
        """Deploy the bridge manager nginx load balancer container."""
        print(f"Deploying {self.service_name()}: {self.container_name}")

        # Remove existing container if present
        try:
            existing = self.docker_client.containers.get(self.container_name)
            existing.stop()
            existing.remove()
        except docker.errors.NotFound:
            pass

        container = self.docker_client.containers.run(
            self.image_name(),
            name=self.container_name,
            volumes={
                str(self.nginx_bm_dir.absolute()): {
                    "bind": "/etc/nginx/conf.d",
                    "mode": "ro",
                }
            },
            ports={
                f"{HS_CONFIG.BRIDGE_MANAGER_NGINX_PORT}/tcp": (
                    HS_CONFIG.BRIDGE_MANAGER_NGINX_PORT
                ),
                f"{HS_CONFIG.BRIDGE_MANAGER_NGINX_STATUS_PORT}/tcp": (
                    HS_CONFIG.BRIDGE_MANAGER_NGINX_STATUS_PORT
                ),
            },
            network=self.network_name,
            detach=True,
            remove=False,
        )

        print(f"  ✓ {self.service_name()} container started")
        return container

    def is_healthy(self) -> bool:
        """Check if the nginx bridge manager container is healthy."""
        try:
            container = self.docker_client.containers.get(self.container_name)
            if container.status != "running":
                return False

            result = container.exec_run(
                f"curl -sf http://localhost:"
                f"{HS_CONFIG.BRIDGE_MANAGER_NGINX_STATUS_PORT}/nginx_status"
            )
            return result.exit_code == 0
        except docker.errors.NotFound:
            return False
        except Exception:
            return False

    def reload(self) -> bool:
        """Reload nginx config without restarting the container."""
        try:
            container = self.docker_client.containers.get(self.container_name)
            result = container.exec_run("nginx -s reload")
            return result.exit_code == 0
        except docker.errors.NotFound:
            return False

    def update_config(self, num_instances: int, reload: bool = True) -> bool:
        """
        Update the nginx config for a new number of instances.

        Args:
            num_instances: New number of bridge manager instances
            reload: Whether to reload nginx after updating

        Returns:
            True if successful
        """
        old = self.num_instances
        self.num_instances = num_instances
        self.generate_config()

        if reload:
            if self.reload():
                print(
                    f"  ✓ Updated bridge manager nginx config "
                    f"({old} → {num_instances} instances)"
                )
                return True
            else:
                print("  ✗ Failed to reload bridge manager nginx")
                return False

        return True
