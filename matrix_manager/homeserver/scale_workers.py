"""
Utility to scale workers up or down for an existing homeserver deployment
"""

import docker
import yaml
import socket
import random
import time
from pathlib import Path

docker_client = docker.from_env()

SYNAPSE_IMAGE = "matrixdotorg/synapse:latest"


def find_available_port(start_port: int, max_attempts: int = 100) -> int:
    """Find an available port starting from start_port with random offset to avoid collisions"""
    # Add random offset to reduce collision probability when multiple workers start simultaneously
    offset = random.randint(0, 50)
    for attempt in range(max_attempts):
        port = start_port + offset + attempt
        if port > 65535:  # Max port number
            port = start_port + attempt

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("0.0.0.0", port))
                # Successfully bound, port is available
                return port
            except OSError:
                continue
    raise RuntimeError(f"Could not find available port starting from {start_port}")


def scale_workers(homeserver_id: str, target_workers: int):
    """
    Scale the number of workers for a homeserver

    Args:
        homeserver_id: The homeserver to scale
        target_workers: Desired number of workers
    """
    base_dir = Path(__file__).parent / "deployments" / homeserver_id
    data_dir = base_dir / "synapse" / "data"
    workers_dir = data_dir / "workers"
    config_path = data_dir / "homeserver.yaml"

    if not config_path.exists():
        raise ValueError(f"Homeserver {homeserver_id} not found")

    # Get current worker count
    current_workers = (
        len(list(workers_dir.glob("worker*.yaml"))) if workers_dir.exists() else 0
    )

    print(f"Current workers: {current_workers}")
    print(f"Target workers: {target_workers}")

    if target_workers == current_workers:
        print("No scaling needed")
        return

    if target_workers > current_workers:
        # Scale up
        _scale_up(homeserver_id, current_workers, target_workers)
    else:
        # Scale down
        _scale_down(homeserver_id, current_workers, target_workers)

    # Update main config
    _update_instance_map(homeserver_id, target_workers)

    # Update nginx config
    _update_nginx_config(homeserver_id, target_workers)

    # Update prometheus config
    _update_prometheus_config(homeserver_id, target_workers)

    print(f"✓ Scaled to {target_workers} workers")


def _scale_up(homeserver_id: str, current: int, target: int):
    """Add new workers"""
    print(f"Scaling up: adding {target - current} workers...")

    base_dir = Path(__file__).parent / "deployments" / homeserver_id
    data_dir = base_dir / "synapse" / "data"
    workers_dir = data_dir / "workers"
    workers_dir.mkdir(exist_ok=True)
    network_name = f"{homeserver_id}_network"

    for i in range(current + 1, target + 1):
        # Create worker config
        worker_name = f"generic_worker{i}"
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

        worker_config_path = workers_dir / f"worker{i}.yaml"
        with open(worker_config_path, "w") as f:
            yaml.dump(worker_config, f, default_flow_style=False)

        # Deploy worker container
        worker_container_name = f"{homeserver_id}_worker{i}"
        worker_port = find_available_port(8000 + i)

        docker_client.containers.run(
            SYNAPSE_IMAGE,
            name=worker_container_name,
            command=[
                "run",
                "-m",
                "synapse.app.generic_worker",
                "--config-path=/data/homeserver.yaml",
                f"--config-path=/data/workers/worker{i}.yaml",
            ],
            volumes={str(data_dir.absolute()): {"bind": "/data", "mode": "rw"}},
            ports={f"8083/tcp": worker_port},
            network=network_name,
            detach=True,
            remove=False,
        )

        print(f"  ✓ Added worker {i} on port {worker_port}")

        # Small delay to ensure port is fully bound before next worker
        time.sleep(1)


def _scale_down(homeserver_id: str, current: int, target: int):
    """Remove workers"""
    print(f"Scaling down: removing {current - target} workers...")

    base_dir = Path(__file__).parent / "deployments" / homeserver_id
    data_dir = base_dir / "synapse" / "data"
    workers_dir = data_dir / "workers"

    for i in range(target + 1, current + 1):
        # Stop and remove container
        worker_container_name = f"{homeserver_id}_worker{i}"
        try:
            container = docker_client.containers.get(worker_container_name)
            container.stop()
            container.remove()
            print(f"  ✓ Removed worker {i}")
        except docker.errors.NotFound:
            print(f"  Worker {i} container not found (already removed?)")

        # Remove config file
        worker_config_path = workers_dir / f"worker{i}.yaml"
        if worker_config_path.exists():
            worker_config_path.unlink()


def _update_instance_map(homeserver_id: str, num_workers: int):
    """Update the instance map in main config"""
    base_dir = Path(__file__).parent / "deployments" / homeserver_id
    data_dir = base_dir / "synapse" / "data"
    config_path = data_dir / "homeserver.yaml"

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    # Rebuild instance map
    instance_map = {"main": {"host": f"{homeserver_id}_synapse", "port": 9093}}

    for i in range(1, num_workers + 1):
        worker_name = f"generic_worker{i}"
        instance_map[worker_name] = {"host": f"{homeserver_id}_worker{i}", "port": 9093}

    config["instance_map"] = instance_map

    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False)

    print("  ✓ Updated instance map")


def _update_nginx_config(homeserver_id: str, num_workers: int):
    """Regenerate nginx config and reload"""
    base_dir = Path(__file__).parent / "deployments" / homeserver_id
    nginx_dir = base_dir / "nginx"
    config_path = nginx_dir / "synapse.conf"

    if not config_path.exists():
        print("  ! Nginx not deployed, skipping")
        return

    # Generate upstream configuration
    if num_workers > 0:
        upstream_servers = "\n".join(
            f"        server {homeserver_id}_worker{i}:8083;"
            for i in range(1, num_workers + 1)
        )
    else:
        upstream_servers = f"        server {homeserver_id}_synapse:8008;"

    nginx_config = f"""events {{
    worker_connections 1024;
}}

http {{
    # Docker DNS resolver
    resolver 127.0.0.11 valid=30s;
    
    upstream synapse {{
        hash $remote_addr consistent;
{upstream_servers}
    }}

    server {{
        listen 80;
        server_name {homeserver_id}.localhost;

        # Client API
        location ~ ^(/_matrix|/_synapse/client) {{
            proxy_pass http://synapse;
            proxy_set_header X-Forwarded-For $remote_addr;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header Host $host;
            
            # WebSocket support
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
        }}
        
        # Health check endpoint
        location /health {{
            access_log off;
            return 200 "healthy\\n";
            add_header Content-Type text/plain;
        }}
    }}

    # Metrics endpoint for Prometheus
    server {{
        listen 8080;
        location /nginx_status {{
            stub_status on;
            access_log off;
        }}
    }}
}}"""

    with open(config_path, "w") as f:
        f.write(nginx_config)

    # Reload nginx
    try:
        nginx_container = docker_client.containers.get(f"{homeserver_id}_nginx")
        nginx_container.exec_run("nginx -s reload")
        print("  ✓ Updated and reloaded nginx config")
    except docker.errors.NotFound:
        print("  ! Nginx container not found")


def _update_prometheus_config(homeserver_id: str, num_workers: int):
    """Regenerate prometheus config and reload"""
    base_dir = Path(__file__).parent / "deployments" / homeserver_id
    prometheus_dir = base_dir / "prometheus"
    config_path = prometheus_dir / "prometheus.yml"

    if not config_path.exists():
        print("  ! Prometheus not deployed, skipping")
        return

    # Build targets list
    targets = [f"{homeserver_id}_synapse:9000"]
    for i in range(1, num_workers + 1):
        targets.append(f"{homeserver_id}_worker{i}:9000")

    prometheus_config = {
        "global": {"scrape_interval": "15s", "evaluation_interval": "15s"},
        "scrape_configs": [
            {
                "job_name": "synapse",
                "metrics_path": "/_synapse/metrics",
                "static_configs": [
                    {"targets": targets, "labels": {"homeserver": homeserver_id}}
                ],
            },
            {
                "job_name": "nginx",
                "static_configs": [{"targets": [f"{homeserver_id}_nginx:8080"]}],
                "metrics_path": "/nginx_status",
            },
        ],
    }

    with open(config_path, "w") as f:
        yaml.dump(prometheus_config, f, default_flow_style=False)

    # Reload prometheus
    try:
        prometheus_container = docker_client.containers.get(
            f"{homeserver_id}_prometheus"
        )
        prometheus_container.exec_run("kill -HUP 1")
        print("  ✓ Updated and reloaded prometheus config")
    except docker.errors.NotFound:
        print("  ! Prometheus container not found")


def get_worker_status(homeserver_id: str):
    """Get status of all workers for a homeserver"""
    print(f"Worker status for {homeserver_id}:")

    i = 1
    while True:
        worker_container_name = f"{homeserver_id}_worker{i}"
        try:
            container = docker_client.containers.get(worker_container_name)
            status = container.status
            port = (
                container.attrs["NetworkSettings"]["Ports"]
                .get("8083/tcp", [{}])[0]
                .get("HostPort", "N/A")
            )
            print(f"  Worker {i}: {status} (port {port})")
            i += 1
        except docker.errors.NotFound:
            break

    if i == 1:
        print("  No workers deployed (monolith mode)")
    else:
        print(f"\nTotal: {i-1} workers")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python scale_workers.py <homeserver_id> <num_workers>")
        print("  python scale_workers.py <homeserver_id> status")
        print("\nExamples:")
        print("  python scale_workers.py HS-001 5    # Scale to 5 workers")
        print("  python scale_workers.py HS-001 0    # Scale down to monolith")
        print("  python scale_workers.py HS-001 status    # Check status")
        sys.exit(1)

    homeserver_id = sys.argv[1]

    if len(sys.argv) == 3 and sys.argv[2] == "status":
        get_worker_status(homeserver_id)
    elif len(sys.argv) == 3:
        target_workers = int(sys.argv[2])
        scale_workers(homeserver_id, target_workers)
    else:
        print("Invalid arguments")
        sys.exit(1)
