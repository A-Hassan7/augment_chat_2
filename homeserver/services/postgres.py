"""
PostgreSQL database service for Synapse homeserver
"""

from pathlib import Path
import time
import docker
import config as HS_CONFIG
from .base import BaseService, docker_client


class PostgresService(BaseService):
    """PostgreSQL database service"""

    def __init__(
        self,
        homeserver_id: str,
        base_dir: Path,
        network_name: str,
        db_user: str = None,
        db_password: str = None,
    ):
        super().__init__(homeserver_id, base_dir, network_name)
        self.db_name = homeserver_id.replace("-", "_")
        self.db_user = db_user or HS_CONFIG.DB_USER
        self.db_password = db_password or HS_CONFIG.DB_PASSWORD
        self.data_dir = base_dir / "postgres_data"

    def service_name(self) -> str:
        return "postgres"

    def image_name(self) -> str:
        return HS_CONFIG.POSTGRES_IMAGE

    def validate_config(self) -> bool:
        """Validate PostgreSQL configuration"""
        if not self.db_user:
            raise ValueError("Database user not configured")
        if not self.db_password:
            raise ValueError("Database password not configured")
        if not self.db_name:
            raise ValueError("Database name not configured")
        return True

    def generate_config(self) -> None:
        """Create postgres data directory"""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        print(f"  ✓ PostgreSQL data directory: {self.data_dir}")

    def deploy(self) -> docker.models.containers.Container:
        """Deploy PostgreSQL container"""
        print(f"Deploying PostgreSQL container: {self.container_name}")

        # Remove existing container if present
        try:
            existing = docker_client.containers.get(self.container_name)
            print(f"  Removing existing container...")
            existing.stop()
            existing.remove()
        except docker.errors.NotFound:
            pass

        # Start PostgreSQL container
        container_config = {
            "image": self.image_name(),
            "name": self.container_name,
            "environment": {
                "POSTGRES_DB": self.db_name,
                "POSTGRES_USER": self.db_user,
                "POSTGRES_PASSWORD": self.db_password,
                "POSTGRES_INITDB_ARGS": "--encoding=UTF8 --lc-collate=C --lc-ctype=C",
            },
            "volumes": {
                str(self.data_dir.absolute()): {
                    "bind": "/var/lib/postgresql/data",
                    "mode": "rw",
                }
            },
            "network": self.network_name,
            "detach": True,
            "remove": False,
        }

        # Optionally expose port based on config
        if HS_CONFIG.EXPOSE_POSTGRES_PORT:
            container_config["ports"] = {"5432/tcp": HS_CONFIG.POSTGRES_PORT}

        self.container = docker_client.containers.run(**container_config)

        # Wait for PostgreSQL to be ready
        print("  Waiting for PostgreSQL to be ready...")
        time.sleep(5)

        for i in range(30):
            result = self.container.exec_run(
                f"pg_isready -U {self.db_user} -d {self.db_name}"
            )
            if result.exit_code == 0:
                print("  ✓ PostgreSQL is ready")
                return self.container
            time.sleep(1)

        raise Exception("PostgreSQL failed to start")

    def is_healthy(self) -> bool:
        """Check if PostgreSQL is ready to accept connections"""
        if not super().is_healthy():
            return False

        try:
            result = self.container.exec_run(
                f"pg_isready -U {self.db_user} -d {self.db_name}"
            )
            return result.exit_code == 0
        except Exception:
            return False
