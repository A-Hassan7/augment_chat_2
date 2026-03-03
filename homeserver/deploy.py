"""
Deployment orchestrator using service abstraction

Demonstrates improved maintainability patterns:
- Service-based architecture
- Validation before deployment
- Structured error handling
- Easy inspection and debugging
"""

from pathlib import Path
from typing import List, Dict, Any
import docker
import config as HS_CONFIG
from services import (
    PostgresService,
    RedisService,
    SynapseService,
    WorkerService,
    NginxService,
    PrometheusService,
    GrafanaService,
)

docker_client = docker.from_env()


class DeploymentPlan:
    """
    Represents a deployment plan with validation and execution

    Benefits:
    - Validate configs before deploying anything
    - See what will be deployed (dry-run)
    - Rollback on failure
    - Track what's been deployed
    """

    def __init__(
        self, homeserver_id: str, domain: str = "localhost", num_workers: int = 0
    ):
        self.homeserver_id = homeserver_id
        self.domain = domain
        self.num_workers = num_workers

        # Setup paths
        self.base_dir = Path("deployments") / homeserver_id
        self.network_name = f"{homeserver_id}_network"

        # Build service list
        self.services = []
        self._build_service_list()

        # Track deployment state
        self.deployed_services = []

    def _build_service_list(self):
        """Build list of services to deploy"""
        # Always need PostgreSQL
        self.services.append(
            PostgresService(self.homeserver_id, self.base_dir, self.network_name)
        )

        # Redis only if using workers
        if self.num_workers > 0:
            self.services.append(
                RedisService(self.homeserver_id, self.base_dir, self.network_name)
            )

        # Synapse homeserver
        self.services.append(
            SynapseService(
                self.homeserver_id,
                self.base_dir,
                self.network_name,
                num_workers=self.num_workers,
                postgres_container=f"{self.homeserver_id}_postgres",
                redis_container=(
                    f"{self.homeserver_id}_redis" if self.num_workers > 0 else None
                ),
            )
        )

        # Workers (if using distributed mode)
        if self.num_workers > 0:
            self.services.append(
                WorkerService(
                    self.homeserver_id,
                    self.base_dir,
                    self.network_name,
                    num_workers=self.num_workers,
                    synapse_container=f"{self.homeserver_id}_synapse",
                )
            )

        # Nginx load balancer
        self.services.append(
            NginxService(
                self.homeserver_id,
                self.base_dir,
                self.network_name,
                domain=self.domain,
                num_workers=self.num_workers,
                synapse_container=f"{self.homeserver_id}_synapse",
            )
        )

        # Prometheus metrics collection
        self.services.append(
            PrometheusService(
                self.homeserver_id,
                self.base_dir,
                self.network_name,
                num_workers=self.num_workers,
                synapse_container=f"{self.homeserver_id}_synapse",
                nginx_container=f"{self.homeserver_id}_nginx",
            )
        )

        # Grafana visualization
        self.services.append(
            GrafanaService(
                self.homeserver_id,
                self.base_dir,
                self.network_name,
                prometheus_container=f"{self.homeserver_id}_prometheus",
            )
        )

    def validate(self) -> bool:
        """
        Validate all service configurations before deployment

        Returns:
            True if all configurations are valid

        Raises:
            ValueError: If any configuration is invalid
        """
        print(f"Validating deployment plan for {self.homeserver_id}...")

        for service in self.services:
            print(f"  Validating {service.service_name()}...")
            service.validate_config()

        print("✓ All configurations valid")
        return True

    def summary(self) -> str:
        """Return a human-readable summary of the deployment plan"""
        lines = [
            f"Deployment Plan: {self.homeserver_id}",
            f"Domain: {self.domain}",
            f"Workers: {self.num_workers}",
            "",
            "Services to deploy:",
        ]

        for service in self.services:
            lines.append(f"  - {service.service_name()} ({service.image_name()})")

        return "\n".join(lines)

    def execute(self) -> Dict[str, Any]:
        """
        Execute the deployment plan

        Returns:
            Dictionary with deployment results

        Raises:
            Exception: If deployment fails (will attempt rollback)
        """
        print(f"\nDeploying homeserver: {self.homeserver_id}")
        print(self.summary())
        print()

        # Create network
        self._create_network()

        # Deploy services in order
        try:
            for i, service in enumerate(self.services):
                service.generate_config()
                service.deploy()
                self.deployed_services.append(service)

                # Wait for service to be healthy
                if not service.wait_until_ready(timeout=60):
                    raise Exception(f"{service.service_name()} failed health check")

                # Add delay after Synapse before deploying workers
                if service.service_name() == "synapse" and self.num_workers > 0:
                    print(
                        "  Waiting 10 seconds for Synapse to stabilize before deploying workers..."
                    )
                    import time

                    time.sleep(10)

            print(f"\n✓ {self.homeserver_id} deployed successfully!")
            return self._build_result()

        except Exception as e:
            print(f"\n✗ Deployment failed: {e}")
            print("Rolling back...")
            self.rollback()
            raise

    def _create_network(self):
        """Create Docker network"""
        print(f"Creating network: {self.network_name}")
        try:
            docker_client.networks.create(self.network_name, driver="bridge")
        except docker.errors.APIError as e:
            if "already exists" in str(e):
                print(f"  Network already exists")
            else:
                raise

    def rollback(self):
        """Rollback deployed services"""
        print("Rolling back deployed services...")
        for service in reversed(self.deployed_services):
            print(f"  Removing {service.service_name()}...")
            service.cleanup()
        self.deployed_services = []
        print("✓ Rollback complete")

    def status(self) -> List[Dict[str, Any]]:
        """Get status of all services"""
        return [service.get_status() for service in self.services]

    def _build_result(self) -> Dict[str, Any]:
        """Build deployment result dictionary"""
        return {
            "homeserver_id": self.homeserver_id,
            "domain": self.domain,
            "num_workers": self.num_workers,
            "services": [s.service_name() for s in self.deployed_services],
            "status": self.status(),
        }


if __name__ == "__main__":
    # Example usage
    import argparse

    parser = argparse.ArgumentParser(
        description="Deploy homeserver with new architecture"
    )
    parser.add_argument("homeserver_id", help="Homeserver ID (e.g., hs-001)")
    parser.add_argument("--workers", type=int, default=0, help="Number of workers")
    parser.add_argument(
        "--validate-only", action="store_true", help="Only validate, don't deploy"
    )
    parser.add_argument(
        "--status", action="store_true", help="Show status of existing deployment"
    )

    args = parser.parse_args()

    plan = DeploymentPlan(args.homeserver_id, num_workers=args.workers)

    if args.status:
        print(plan.summary())
        print("\nCurrent Status:")
        for status in plan.status():
            health = "✓" if status.get("healthy") else "✗"
            print(f"  {health} {status['name']}: {status['status']}")

    elif args.validate_only:
        plan.validate()
        print("\n" + plan.summary())
        print("\n✓ Validation successful (use without --validate-only to deploy)")

    else:
        plan.validate()
        result = plan.execute()
        print(f"\nDeployment complete: {result}")
