"""
Script to deploy a new homeserver setup and run the api

- Create new synapse homeserver docker instance
- Create postgres database
- Register bridge manager
- Create admin user
- Create the bridge manager
"""

import os
import time
import docker
import subprocess
from pathlib import Path
import yaml
import worker_manager


# Docker image versions
POSTGRES_IMAGE = "postgres:15-alpine"
SYNAPSE_IMAGE = "matrixdotorg/synapse:latest"
REDIS_IMAGE = "redis:7-alpine"
NGINX_IMAGE = "nginx:alpine"
PROMETHEUS_IMAGE = "prom/prometheus:latest"
GRAFANA_IMAGE = "grafana/grafana:latest"

docker_client = docker.from_env()


class HomeserverDeployer:
    """Deploy a complete homeserver instance"""

    def __init__(
        self,
        homeserver_id: str,
        domain: str = "localhost",
        num_workers: int = 0,  # 0 = no workers (monolith mode)
    ):
        self.homeserver_id = homeserver_id
        self.domain = domain
        self.num_workers = num_workers
        self.base_dir = Path(__file__).parent / "deployments" / homeserver_id
        self.synapse_dir = self.base_dir / "synapse"
        self.data_dir = self.synapse_dir / "data"
        self.postgres_data_dir = self.base_dir / "postgres_data"
        self.workers_dir = self.data_dir / "workers"
        self.nginx_dir = self.base_dir / "nginx"
        self.prometheus_dir = self.base_dir / "prometheus"
        self.grafana_dir = self.base_dir / "grafana"
        self.grafana_provisioning_dir = self.base_dir / "grafana_provisioning"
        self.grafana_dashboards_dir = self.base_dir / "grafana_dashboards"

        # Network and container names
        self.network_name = f"{homeserver_id}_network"
        self.postgres_container = f"{homeserver_id}_postgres"
        self.redis_container = f"{homeserver_id}_redis"
        self.synapse_container = f"{homeserver_id}_synapse"
        self.nginx_container = f"{homeserver_id}_nginx"
        self.prometheus_container = f"{homeserver_id}_prometheus"
        self.grafana_container = f"{homeserver_id}_grafana"

        # Database credentials
        self.db_name = homeserver_id.replace("-", "_")
        self.db_user = "synapse"
        self.db_password = "password"  # In production, generate securely

    def deploy(self):
        """Deploy the complete homeserver stack"""
        print(f"Deploying homeserver: {self.homeserver_id}")

        if self.num_workers > 0:
            print(f"  Worker mode: {self.num_workers} workers")
        else:
            print("  Monolith mode (no workers)")

        # Create directory structure
        self._create_directories()

        # Create Docker network
        self._create_network()

        # Deploy Postgres
        self._deploy_postgres()

        # Deploy Redis if using workers
        if self.num_workers > 0:
            self._deploy_redis()

        # Generate Synapse config
        self._generate_synapse_config()

        # Update config for Postgres
        self._configure_postgres_connection()

        # Configure workers if needed
        if self.num_workers > 0:
            self._configure_workers()

        # Deploy Synapse
        self._deploy_synapse()

        # Wait for Synapse to be ready
        self._wait_for_synapse()

        # Deploy workers if configured
        if self.num_workers > 0:
            self._deploy_workers()

        # Deploy Nginx load balancer
        self._deploy_nginx()

        # Deploy monitoring stack
        self._deploy_monitoring()

        # Register admin user
        admin_user = self._register_admin_user()

        print(f"\n✓ Homeserver {self.homeserver_id} deployed successfully!")
        print(f"  Synapse URL (via Nginx): http://{self.domain}:80")
        print(f"  Synapse Direct: http://{self.domain}:8008")
        print(f"  Admin user: {admin_user}")
        if self.num_workers > 0:
            print(f"  Workers: {self.num_workers} generic workers running")
        print(f"  Prometheus: http://{self.domain}:9090")
        print(f"  Grafana: http://{self.domain}:3000 (admin/admin)")

        return {
            "homeserver_id": self.homeserver_id,
            "synapse_url": f"http://{self.domain}:80",
            "synapse_direct_url": f"http://{self.domain}:8008",
            "admin_user": admin_user,
            "postgres_container": self.postgres_container,
            "synapse_container": self.synapse_container,
            "nginx_container": self.nginx_container,
            "prometheus_url": f"http://{self.domain}:9090",
            "grafana_url": f"http://{self.domain}:3000",
            "num_workers": self.num_workers,
        }

    def _create_directories(self):
        """Create necessary directories"""
        print("Creating directories...")
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.synapse_dir.mkdir(exist_ok=True)
        self.data_dir.mkdir(exist_ok=True)
        self.postgres_data_dir.mkdir(exist_ok=True)
        self.nginx_dir.mkdir(exist_ok=True)
        self.prometheus_dir.mkdir(exist_ok=True)
        self.grafana_dir.mkdir(exist_ok=True)
        (self.grafana_provisioning_dir / "datasources").mkdir(
            parents=True, exist_ok=True
        )
        (self.grafana_provisioning_dir / "dashboards").mkdir(
            parents=True, exist_ok=True
        )
        self.grafana_dashboards_dir.mkdir(exist_ok=True)
        if self.num_workers > 0:
            self.workers_dir.mkdir(exist_ok=True)

    def _create_network(self):
        """Create Docker network for homeserver components"""
        print(f"Creating Docker network: {self.network_name}")
        try:
            docker_client.networks.create(self.network_name, driver="bridge")
        except docker.errors.APIError as e:
            if "already exists" in str(e):
                print(f"  Network {self.network_name} already exists")
            else:
                raise

    def _deploy_postgres(self):
        """Deploy Postgres container"""
        print(f"Deploying Postgres container: {self.postgres_container}")

        # Check if container already exists
        try:
            existing = docker_client.containers.get(self.postgres_container)
            print(f"  Container already exists, removing...")
            existing.stop()
            existing.remove()
        except docker.errors.NotFound:
            pass

        # Start Postgres container
        container = docker_client.containers.run(
            POSTGRES_IMAGE,
            name=self.postgres_container,
            environment={
                "POSTGRES_DB": self.db_name,
                "POSTGRES_USER": self.db_user,
                "POSTGRES_PASSWORD": self.db_password,
                "POSTGRES_INITDB_ARGS": "--encoding=UTF8 --lc-collate=C --lc-ctype=C",
            },
            volumes={
                str(self.postgres_data_dir.absolute()): {
                    "bind": "/var/lib/postgresql/data",
                    "mode": "rw",
                }
            },
            network=self.network_name,
            detach=True,
            remove=False,
        )

        # Wait for Postgres to be ready
        print("  Waiting for Postgres to be ready...")
        time.sleep(5)

        for i in range(30):
            result = container.exec_run(
                f"pg_isready -U {self.db_user} -d {self.db_name}"
            )
            if result.exit_code == 0:
                print("  ✓ Postgres is ready")
                break
            time.sleep(1)
        else:
            raise Exception("Postgres failed to start")

    def _deploy_redis(self):
        """Deploy Redis container for worker communication"""
        print(f"Deploying Redis container: {self.redis_container}")

        # Check if container already exists
        try:
            existing = docker_client.containers.get(self.redis_container)
            print(f"  Container already exists, removing...")
            existing.stop()
            existing.remove()
        except docker.errors.NotFound:
            pass

        # Start Redis container
        container = docker_client.containers.run(
            REDIS_IMAGE,
            name=self.redis_container,
            network=self.network_name,
            detach=True,
            remove=False,
        )

        # Wait for Redis to be ready
        print("  Waiting for Redis to be ready...")
        time.sleep(2)

        for i in range(30):
            result = container.exec_run("redis-cli PING")
            if result.exit_code == 0 and b"PONG" in result.output:
                print("  ✓ Redis is ready")
                break
            time.sleep(1)
        else:
            raise Exception("Redis failed to start")

    def _generate_synapse_config(self):
        """Generate Synapse configuration"""
        print("Generating Synapse configuration...")

        config_path = self.data_dir / "homeserver.yaml"

        if config_path.exists():
            print("  Config already exists, skipping generation")
            return

        # Generate config using Docker
        docker_client.containers.run(
            SYNAPSE_IMAGE,
            command="generate",
            environment={
                "SYNAPSE_SERVER_NAME": self.homeserver_id,
                "SYNAPSE_REPORT_STATS": "no",
            },
            volumes={str(self.data_dir.absolute()): {"bind": "/data", "mode": "rw"}},
            remove=True,
        )

        print("  ✓ Configuration generated")

    def _configure_postgres_connection(self):
        """Update Synapse config to use Postgres"""
        print("Configuring Postgres connection...")

        config_path = self.data_dir / "homeserver.yaml"

        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        # Update database config
        config["database"] = {
            "name": "psycopg2",
            "args": {
                "user": self.db_user,
                "password": self.db_password,
                "database": self.db_name,
                "host": self.postgres_container,
                "port": 5432,
                "cp_min": 5,
                "cp_max": 10,
            },
        }

        # Enable registration for admin user creation
        config["enable_registration"] = True
        config["enable_registration_without_verification"] = True

        # Enable metrics for monitoring
        config["enable_metrics"] = True

        # Only add metrics listener for monolith mode (no workers)
        # Workers have their own metrics listeners in worker config
        if self.num_workers == 0:
            if "listeners" not in config:
                config["listeners"] = []
            config["listeners"].append(
                {
                    "port": 9000,
                    "bind_addresses": ["0.0.0.0"],
                    "type": "http",
                    "resources": [{"names": ["metrics"]}],
                }
            )

        with open(config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False)

        print("  ✓ Postgres connection configured")

    def _configure_workers(self):
        """Configure Synapse for worker mode"""
        print(f"Configuring {self.num_workers} workers...")

        config_path = self.data_dir / "homeserver.yaml"

        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        # Enable Redis
        config["redis"] = {"enabled": True, "host": self.redis_container, "port": 6379}

        # Add HTTP replication listener for main process
        if "listeners" not in config:
            config["listeners"] = []

        config["listeners"].append(
            {
                "port": 9093,
                "bind_addresses": ["0.0.0.0"],
                "type": "http",
                "resources": [{"names": ["replication"]}],
            }
        )

        # Add metrics listener for main process
        config["listeners"].append(
            {
                "port": 9000,
                "bind_addresses": ["0.0.0.0"],
                "type": "http",
                "resources": [{"names": ["metrics"]}],
            }
        )

        # Build instance map
        instance_map = {"main": {"host": self.synapse_container, "port": 9093}}

        # Add each worker to instance map
        for i in range(1, self.num_workers + 1):
            worker_name = f"generic_worker{i}"
            instance_map[worker_name] = {
                "host": f"{self.homeserver_id}_worker{i}",
                "port": 9093,
            }

        config["instance_map"] = instance_map

        # Save updated config
        with open(config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False)

        # Create worker config files
        for i in range(1, self.num_workers + 1):
            self._create_worker_config(i)

        print(f"  ✓ Worker configuration complete")

    def _create_worker_config(self, worker_num: int):
        """Create configuration file for a worker"""
        worker_manager.create_worker_config(self.workers_dir, worker_num)

    def _deploy_synapse(self):
        """Deploy Synapse container"""
        print(f"Deploying Synapse container: {self.synapse_container}")

        # Check if container already exists
        try:
            existing = docker_client.containers.get(self.synapse_container)
            print(f"  Container already exists, removing...")
            existing.stop()
            existing.remove()
        except docker.errors.NotFound:
            pass

        # Start Synapse container
        container = docker_client.containers.run(
            SYNAPSE_IMAGE,
            name=self.synapse_container,
            volumes={str(self.data_dir.absolute()): {"bind": "/data", "mode": "rw"}},
            ports={"8008/tcp": 8008, "8448/tcp": 8448},
            network=self.network_name,
            detach=True,
            remove=False,
        )

        print("  ✓ Synapse container started")

    def _deploy_workers(self):
        """Deploy worker containers"""
        print(f"Deploying {self.num_workers} worker containers...")

        worker_manager.deploy_workers_batch(
            self.homeserver_id,
            start_num=1,
            end_num=self.num_workers,
            data_dir=self.data_dir,
            network_name=self.network_name,
            workers_dir=self.workers_dir,
            delay_between=1.0,
        )

        print(f"  ✓ All workers deployed")

    def _deploy_nginx(self):
        """Deploy Nginx as load balancer and reverse proxy"""
        print(f"Deploying Nginx load balancer: {self.nginx_container}")

        # Generate Nginx configuration
        self._generate_nginx_config()

        # Check if container already exists
        try:
            existing = docker_client.containers.get(self.nginx_container)
            existing.stop()
            existing.remove()
        except docker.errors.NotFound:
            pass

        # Start Nginx container
        docker_client.containers.run(
            NGINX_IMAGE,
            name=self.nginx_container,
            volumes={
                str(self.nginx_dir.absolute()): {
                    "bind": "/etc/nginx/conf.d",
                    "mode": "ro",
                }
            },
            ports={"80/tcp": 80, "8080/tcp": 8080},  # Status/metrics endpoint
            network=self.network_name,
            detach=True,
            remove=False,
        )

        print("  ✓ Nginx deployed")

    def _generate_nginx_config(self):
        """Generate Nginx configuration for load balancing"""
        print("  Generating Nginx configuration...")

        # Build upstream configuration
        if self.num_workers > 0:
            # Load balance across workers
            upstream_servers = []
            for i in range(1, self.num_workers + 1):
                upstream_servers.append(
                    f"        server {self.homeserver_id}_worker{i}:8083;"
                )
            upstream_block = "\n".join(upstream_servers)
        else:
            # Single main process
            upstream_block = f"        server {self.synapse_container}:8008;"

        nginx_config = f"""
# Docker DNS resolver
resolver 127.0.0.11 valid=30s;

# Upstream for Synapse (main or workers)
upstream synapse_backend {{
    # Use consistent hashing for sticky sessions
    hash $remote_addr consistent;
    
{upstream_block}
    
    # Health checks and load balancing
    keepalive 32;
}}

# Health check endpoint for monitoring
server {{
    listen 8080;
    server_name _;
    
    location /health {{
        access_log off;
        return 200 "healthy\\n";
        add_header Content-Type text/plain;
    }}
    
    location /nginx_status {{
        stub_status on;
        access_log off;
    }}
}}

# Main proxy server
server {{
    listen 80;
    server_name {self.domain};
    
    # Increase buffer sizes for large requests
    client_max_body_size 50M;
    client_body_buffer_size 128k;
    
    # Logging
    access_log /var/log/nginx/synapse_access.log;
    error_log /var/log/nginx/synapse_error.log;
    
    # Matrix client API
    location /_matrix {{
        proxy_pass http://synapse_backend;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Host $host;
        
        # Timeouts
        proxy_connect_timeout 90s;
        proxy_send_timeout 90s;
        proxy_read_timeout 90s;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }}
    
    # Federation API
    location /_synapse {{
        proxy_pass http://synapse_backend;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Host $host;
    }}
    
    # Health check endpoint
    location /health {{
        access_log off;
        proxy_pass http://synapse_backend/_matrix/client/versions;
    }}
}}
"""

        config_path = self.nginx_dir / "synapse.conf"
        with open(config_path, "w") as f:
            f.write(nginx_config)

        print("  ✓ Nginx configuration generated")

    def _deploy_monitoring(self):
        """Deploy Prometheus and Grafana for monitoring"""
        print("Deploying monitoring stack...")

        # Generate Prometheus configuration
        self._generate_prometheus_config()

        # Deploy Prometheus
        self._deploy_prometheus()

        # Deploy Grafana
        self._deploy_grafana()

        print("  ✓ Monitoring stack deployed")

    def _generate_prometheus_config(self):
        """Generate Prometheus configuration"""
        print("  Generating Prometheus configuration...")

        # Build scrape targets
        scrape_configs = [
            # Synapse main process
            f"""
  - job_name: 'synapse_main'
    metrics_path: '/_synapse/metrics'
    static_configs:
      - targets: ['{self.synapse_container}:9000']
        labels:
          instance: 'main'
          homeserver: '{self.homeserver_id}'
"""
        ]

        # Add workers
        for i in range(1, self.num_workers + 1):
            scrape_configs.append(
                f"""
  - job_name: 'synapse_worker_{i}'
    metrics_path: '/_synapse/metrics'
    static_configs:
      - targets: ['{self.homeserver_id}_worker{i}:9000']
        labels:
          instance: 'worker{i}'
          homeserver: '{self.homeserver_id}'
"""
            )

        # Add Nginx metrics
        scrape_configs.append(
            f"""
  - job_name: 'nginx'
    metrics_path: '/nginx_status'
    static_configs:
      - targets: ['{self.nginx_container}:8080']
        labels:
          instance: 'nginx'
          homeserver: '{self.homeserver_id}'
"""
        )

        prometheus_config = f"""
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
{''.join(scrape_configs)}
"""

        config_path = self.prometheus_dir / "prometheus.yml"
        with open(config_path, "w") as f:
            f.write(prometheus_config)

        print("  ✓ Prometheus configuration generated")

    def _deploy_prometheus(self):
        """Deploy Prometheus container"""
        print("  Deploying Prometheus...")

        # Check if container already exists
        try:
            existing = docker_client.containers.get(self.prometheus_container)
            existing.stop()
            existing.remove()
        except docker.errors.NotFound:
            pass

        # Start Prometheus container
        docker_client.containers.run(
            PROMETHEUS_IMAGE,
            name=self.prometheus_container,
            volumes={
                str(self.prometheus_dir.absolute()): {
                    "bind": "/etc/prometheus",
                    "mode": "ro",
                }
            },
            ports={"9090/tcp": 9090},
            network=self.network_name,
            detach=True,
            remove=False,
        )

        print("  ✓ Prometheus deployed")

    def _generate_grafana_provisioning(self):
        """Generate Grafana provisioning files from templates"""
        print("  Generating Grafana provisioning files from templates...")

        templates_dir = Path(__file__).parent / "grafana_templates"

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

        # Copy and process datasources.yml
        datasources_template = templates_dir / "datasources.yml"
        if datasources_template.exists():
            with open(datasources_template, "r") as f:
                content = substitute_template(f.read())
            datasources_path = (
                self.grafana_provisioning_dir / "datasources" / "datasources.yml"
            )
            with open(datasources_path, "w") as f:
                f.write(content)
        else:
            print("  Warning: datasources.yml template not found")

        # Dashboards are imported via API, not file provisioning
        # Store dashboard templates with substituted variables for API import
        self._processed_dashboards = []
        dashboard_files = list(templates_dir.glob("*.json"))

        for template_file in dashboard_files:
            with open(template_file, "r") as f:
                content = substitute_template(f.read())
            import json

            self._processed_dashboards.append(
                {"name": template_file.name, "dashboard": json.loads(content)}
            )

        print("  ✓ Grafana provisioning files generated")

    def _deploy_grafana(self):
        """Deploy Grafana container"""
        print("  Deploying Grafana...")

        # Generate provisioning files (datasources only)
        self._generate_grafana_provisioning()

        # Check if container already exists
        try:
            existing = docker_client.containers.get(self.grafana_container)
            existing.stop()
            existing.remove()
        except docker.errors.NotFound:
            pass

        # Start Grafana container
        docker_client.containers.run(
            GRAFANA_IMAGE,
            name=self.grafana_container,
            environment={
                "GF_SECURITY_ADMIN_PASSWORD": "admin",
                "GF_AUTH_ANONYMOUS_ENABLED": "true",
                "GF_AUTH_ANONYMOUS_ORG_ROLE": "Viewer",
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
            ports={"3000/tcp": 3000},
            network=self.network_name,
            detach=True,
            remove=False,
        )

        print("  ✓ Grafana deployed")

        # Import dashboards via API for editability
        self._import_grafana_dashboards()

    def _import_grafana_dashboards(self):
        """Import dashboards via API so they're editable in UI"""
        print("  Importing dashboards via API...")

        # Wait for Grafana to be ready
        import time
        import requests

        grafana_url = "http://localhost:3000"
        auth = ("admin", "admin")

        for i in range(30):
            try:
                response = requests.get(f"{grafana_url}/api/health")
                if response.status_code == 200:
                    break
            except requests.exceptions.ConnectionError:
                pass
            time.sleep(2)
        else:
            print("  Warning: Grafana didn't start in time")
            return

        # Import each dashboard
        if not hasattr(self, "_processed_dashboards"):
            print("  No dashboards to import")
            return

        for dash_info in self._processed_dashboards:
            dashboard = dash_info["dashboard"]
            name = dash_info["name"]

            # Remove id/uid/version so Grafana creates new dashboard
            dashboard.pop("id", None)
            dashboard.pop("uid", None)
            dashboard.pop("version", None)

            try:
                response = requests.post(
                    f"{grafana_url}/api/dashboards/db",
                    json={"dashboard": dashboard, "overwrite": True},
                    auth=auth,
                    headers={"Content-Type": "application/json"},
                )
                if response.status_code == 200:
                    print(f"  ✓ Imported dashboard: {name}")
                else:
                    print(f"  Warning: Failed to import {name}: {response.text}")
            except Exception as e:
                print(f"  Warning: Could not import {name}: {e}")

    def _wait_for_synapse(self):
        """Wait for Synapse to be ready"""
        print("Waiting for Synapse to be ready...")

        import requests

        for i in range(60):
            try:
                response = requests.get(
                    f"http://{self.domain}:8008/_matrix/client/versions", timeout=2
                )
                if response.status_code == 200:
                    print("  ✓ Synapse is ready")
                    return
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                pass
            time.sleep(1)

        raise Exception("Synapse failed to start within 60 seconds")

    def _register_admin_user(self):
        """Register an admin user"""
        print("Registering admin user...")

        admin_username = f"admin"
        admin_password = "admin"  # In production, generate securely

        container = docker_client.containers.get(self.synapse_container)

        # Register user using register_new_matrix_user
        result = container.exec_run(
            f"register_new_matrix_user -c /data/homeserver.yaml "
            f"-u {admin_username} -p {admin_password} --admin http://{self.domain}:8008",
            stdin=True,
        )

        if result.exit_code == 0 or "User ID already taken" in result.output.decode():
            print(f"  ✓ Admin user registered: @{admin_username}:{self.homeserver_id}")
            return f"@{admin_username}:{self.homeserver_id}"
        else:
            print(f"  Warning: {result.output.decode()}")
            return f"@{admin_username}:{self.homeserver_id}"

    def _setup_grafana(self):
        """Configure Grafana with Prometheus datasource and dashboards"""
        print("Setting up Grafana...")

        import requests

        grafana_url = f"http://{self.domain}:3000"
        auth = ("admin", "admin")

        # Wait for Grafana to be ready
        print("  Waiting for Grafana to be ready...")
        for i in range(30):
            try:
                response = requests.get(f"{grafana_url}/api/health", timeout=2)
                if response.status_code == 200:
                    break
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                pass
            time.sleep(2)

        # Add Prometheus datasource
        print("  Adding Prometheus datasource...")
        datasource = {
            "name": "Prometheus",
            "type": "prometheus",
            "access": "proxy",
            "url": f"http://{self.prometheus_container}:9090",
            "isDefault": True,
            "jsonData": {"timeInterval": "15s"},
        }

        try:
            response = requests.post(
                f"{grafana_url}/api/datasources",
                json=datasource,
                auth=auth,
                headers={"Content-Type": "application/json"},
                timeout=5,
            )
            if response.status_code in [200, 409]:  # 409 = already exists
                print("  ✓ Prometheus datasource configured")
            else:
                print(f"  Warning: Failed to add datasource: {response.text}")
        except Exception as e:
            print(f"  Warning: Could not configure datasource: {e}")

        print("  ✓ Grafana setup complete")
        print(f"  Access Grafana at: {grafana_url}")
        print(f"  Username: admin, Password: admin")


def deploy(
    homeserver_id: str = "hs-002", domain: str = "localhost", num_workers: int = 0
):
    """
    Deploy a new homeserver instance

    Args:
        homeserver_id: Unique identifier for this homeserver
        domain: Domain name for the homeserver
        num_workers: Number of generic workers to deploy (0 = monolith mode)

    Returns:
        dict: Deployment information

    Examples:
        # Deploy monolith (no workers)
        deploy("HS-001", "localhost")

        # Deploy with 3 workers
        deploy("HS-001", "localhost", num_workers=3)
    """
    deployer = HomeserverDeployer(homeserver_id, domain, num_workers)
    return deployer.deploy()


if __name__ == "__main__":
    # Deploy with 2 workers for demonstration
    deploy(num_workers=3)
