"""
Centralized worker management for Matrix homeserver deployments

This module provides complete worker management functionality and can be used
either as an importable module or as a standalone CLI tool.

CLI Usage:
    python worker_manager.py <homeserver_id> --scale <N>
    python worker_manager.py <homeserver_id> --status

Low-level operations:
- create_worker_config(): Create worker YAML configuration
- deploy_worker(): Deploy a single worker container
- remove_worker(): Remove a worker container and config
- deploy_workers_batch(): Deploy multiple workers in sequence
- remove_workers_batch(): Remove multiple workers in sequence
- find_available_port(): Find available port with collision avoidance

Configuration updates:
- update_instance_map(): Update homeserver.yaml instance_map
- update_nginx_config(): Regenerate and reload nginx config
- update_prometheus_config(): Regenerate and reload prometheus config

High-level orchestration:
- scale_workers(): Scale workers up or down with full config updates
- get_worker_status(): Display status of all workers
- get_worker_count(): Count deployed workers

This consolidation eliminates code duplication and ensures consistent
worker management behavior across deployment and scaling operations.
"""

import docker
import yaml
import socket
import random
import time
from pathlib import Path
from typing import Optional
import homeserver_config as config
import nginx_manager

docker_client = docker.from_env()


def find_available_port(start_port: int, max_attempts: int = None) -> int:
    """Find an available port starting from start_port with random offset to avoid collisions"""
    if max_attempts is None:
        max_attempts = config.WORKER_PORT_MAX_ATTEMPTS

    # Add random offset to reduce collision probability when multiple workers start simultaneously
    offset = random.randint(0, config.WORKER_PORT_RANDOM_OFFSET)
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


def create_worker_config(workers_dir: Path, worker_num: int):
    """
    Create configuration file for a worker

    Args:
        workers_dir: Directory to store worker config
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

    workers_dir.mkdir(parents=True, exist_ok=True)
    worker_config_path = workers_dir / f"worker{worker_num}.yaml"
    with open(worker_config_path, "w") as f:
        yaml.dump(worker_config, f, default_flow_style=False)


def deploy_worker(
    homeserver_id: str,
    worker_num: int,
    data_dir: Path,
    network_name: str,
    start_port: Optional[int] = None,
) -> int:
    """
    Deploy a single worker container

    Args:
        homeserver_id: The homeserver ID
        worker_num: Worker number (1-indexed)
        data_dir: Path to synapse data directory
        network_name: Docker network name
        start_port: Starting port for port search (default: 8000 + worker_num)

    Returns:
        The port the worker was deployed on
    """
    worker_container_name = f"{homeserver_id}_worker{worker_num}"

    if start_port is None:
        start_port = 8000 + worker_num

    worker_port = find_available_port(start_port)

    # Check if container already exists
    try:
        existing = docker_client.containers.get(worker_container_name)
        existing.stop()
        existing.remove()
    except docker.errors.NotFound:
        pass

    # Start worker container
    docker_client.containers.run(
        config.SYNAPSE_IMAGE,
        name=worker_container_name,
        command=[
            "run",
            "-m",
            "synapse.app.generic_worker",
            "--config-path=/data/homeserver.yaml",
            f"--config-path=/data/workers/worker{worker_num}.yaml",
        ],
        volumes={str(data_dir.absolute()): {"bind": "/data", "mode": "rw"}},
        ports={f"8083/tcp": worker_port},
        network=network_name,
        detach=True,
        remove=False,
    )

    return worker_port


def remove_worker(homeserver_id: str, worker_num: int, workers_dir: Path):
    """
    Remove a worker container and its configuration

    Args:
        homeserver_id: The homeserver ID
        worker_num: Worker number (1-indexed)
        workers_dir: Directory containing worker configs
    """
    # Stop and remove container
    worker_container_name = f"{homeserver_id}_worker{worker_num}"
    try:
        container = docker_client.containers.get(worker_container_name)
        container.stop()
        container.remove()
    except docker.errors.NotFound:
        pass

    # Remove config file
    worker_config_path = workers_dir / f"worker{worker_num}.yaml"
    if worker_config_path.exists():
        worker_config_path.unlink()


def update_instance_map(homeserver_id: str, config_path: Path, num_workers: int):
    """
    Update the instance map in main homeserver config

    Args:
        homeserver_id: The homeserver ID
        config_path: Path to homeserver.yaml
        num_workers: Total number of workers
    """
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


def get_worker_count(workers_dir: Path) -> int:
    """
    Get the current number of deployed workers

    Args:
        workers_dir: Directory containing worker configs

    Returns:
        Number of worker config files found
    """
    if not workers_dir.exists():
        return 0
    return len(list(workers_dir.glob("worker*.yaml")))


def deploy_workers_batch(
    homeserver_id: str,
    start_num: int,
    end_num: int,
    data_dir: Path,
    network_name: str,
    workers_dir: Path,
    delay_between: float = 1.0,
):
    """
    Deploy multiple workers in sequence

    Args:
        homeserver_id: The homeserver ID
        start_num: First worker number (inclusive, 1-indexed)
        end_num: Last worker number (inclusive)
        data_dir: Path to synapse data directory
        network_name: Docker network name
        workers_dir: Directory to store worker configs
        delay_between: Seconds to wait between deployments
    """
    for i in range(start_num, end_num + 1):
        create_worker_config(workers_dir, i)
        worker_port = deploy_worker(homeserver_id, i, data_dir, network_name)
        print(f"  ✓ Worker {i} deployed on port {worker_port}")

        if i < end_num:  # Don't delay after last worker
            time.sleep(delay_between)


def remove_workers_batch(
    homeserver_id: str,
    start_num: int,
    end_num: int,
    workers_dir: Path,
):
    """
    Remove multiple workers in sequence

    Args:
        homeserver_id: The homeserver ID
        start_num: First worker number (inclusive, 1-indexed)
        end_num: Last worker number (inclusive)
        workers_dir: Directory containing worker configs
    """
    for i in range(start_num, end_num + 1):
        remove_worker(homeserver_id, i, workers_dir)
        print(f"  ✓ Removed worker {i}")


def update_nginx_config(
    homeserver_id: str, domain: str, num_workers: int, base_dir: Path
):
    """
    Regenerate nginx config and reload for new worker count

    Args:
        homeserver_id: The homeserver ID
        domain: Domain name for the server
        num_workers: Total number of workers
        base_dir: Base deployment directory
    """
    nginx_manager.update_nginx_config(
        homeserver_id=homeserver_id,
        domain=domain,
        num_workers=num_workers,
        base_dir=base_dir,
        reload=True,
    )


def update_prometheus_config(homeserver_id: str, num_workers: int, base_dir: Path):
    """
    Regenerate prometheus config and reload for new worker count

    Args:
        homeserver_id: The homeserver ID
        num_workers: Total number of workers
        base_dir: Base deployment directory
    """
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


def scale_workers(
    homeserver_id: str,
    target_workers: int,
    deployments_dir: Path,
    domain: str = "localhost",
):
    """
    Scale the number of workers for a homeserver up or down

    Args:
        homeserver_id: The homeserver to scale
        target_workers: Desired number of workers
        deployments_dir: Path to deployments directory
        domain: Domain name for nginx config (default: localhost)
    """
    base_dir = deployments_dir / homeserver_id
    data_dir = base_dir / "synapse" / "data"
    workers_dir = data_dir / "workers"
    config_path = data_dir / "homeserver.yaml"

    if not config_path.exists():
        raise ValueError(f"Homeserver {homeserver_id} not found")

    # Get current worker count
    current_workers = get_worker_count(workers_dir)

    print(f"Current workers: {current_workers}")
    print(f"Target workers: {target_workers}")

    if target_workers == current_workers:
        print("No scaling needed")
        return

    # Scale up or down
    if target_workers > current_workers:
        print(f"Scaling up: adding {target_workers - current_workers} workers...")
        network_name = f"{homeserver_id}_network"
        deploy_workers_batch(
            homeserver_id,
            start_num=current_workers + 1,
            end_num=target_workers,
            data_dir=data_dir,
            network_name=network_name,
            workers_dir=workers_dir,
            delay_between=1.0,
        )
    else:
        print(f"Scaling down: removing {current_workers - target_workers} workers...")
        remove_workers_batch(
            homeserver_id,
            start_num=target_workers + 1,
            end_num=current_workers,
            workers_dir=workers_dir,
        )

    # Update configurations
    update_instance_map(homeserver_id, config_path, target_workers)
    print("  ✓ Updated instance map")

    update_nginx_config(homeserver_id, domain, target_workers, base_dir)
    update_prometheus_config(homeserver_id, target_workers, base_dir)

    print(f"✓ Scaled to {target_workers} workers")


def get_worker_status(homeserver_id: str):
    """
    Get status of all workers for a homeserver

    Args:
        homeserver_id: The homeserver ID
    """
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
    import argparse

    parser = argparse.ArgumentParser(
        description="Worker management for Matrix homeserver deployments",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python worker_manager.py hs-001 --scale 5      # Scale to 5 workers
  python worker_manager.py hs-001 --scale 0      # Scale down to monolith
  python worker_manager.py hs-001 --status       # Check worker status
        """,
    )

    parser.add_argument("homeserver_id", help="The homeserver ID to manage")
    parser.add_argument(
        "--domain",
        type=str,
        default="localhost",
        help="Domain name for nginx config (default: localhost)",
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--scale",
        type=int,
        metavar="N",
        help="Scale to N workers (0 for monolith mode)",
    )
    group.add_argument(
        "--status",
        action="store_true",
        help="Show status of all workers",
    )

    args = parser.parse_args()

    deployments_dir = Path(__file__).parent / "deployments"

    try:
        if args.status:
            get_worker_status(args.homeserver_id)
        elif args.scale is not None:
            scale_workers(args.homeserver_id, args.scale, deployments_dir, args.domain)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)
