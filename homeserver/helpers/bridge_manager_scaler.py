"""
Bridge Manager instance scaling for Matrix homeserver deployments.

This module provides scaling operations for the bridge manager appservice proxy
and can be used as an importable module or a standalone CLI tool.

CLI Usage (from the homeserver directory):
    python helpers/bridge_manager_scaler.py <homeserver_id> --scale <N>
    python helpers/bridge_manager_scaler.py <homeserver_id> --status

Architecture:
    Synapse / Bridges
        → {hs_id}_nginx_bm:5000
            → {hs_id}_bridge_manager_1:5001
            → {hs_id}_bridge_manager_2:5001
            → {hs_id}_bridge_manager_N:5001

All instances share the same PostgreSQL database and are therefore stateless —
any instance can handle any inbound request.

High-level operations:
- scale_bridge_managers(): Scale instances up or down with nginx reload
- get_bridge_manager_status(): Display running instances
- get_bridge_manager_count(): Return number of deployed instances
"""

import sys
import os

# Ensure the homeserver root is on sys.path so relative imports work regardless
# of how this script is invoked (e.g. python helpers/bridge_manager_scaler.py).
_HOMESERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _HOMESERVER_DIR not in sys.path:
    sys.path.insert(0, _HOMESERVER_DIR)

import docker
import time
from pathlib import Path
from typing import Optional

import config
from services.bridge_manager import BridgeManagerService, BridgeManagerNginxService

docker_client = docker.from_env()


def get_bridge_manager_count(homeserver_id: str) -> int:
    """
    Return the number of bridge manager instances currently deployed.

    Args:
        homeserver_id: The homeserver ID

    Returns:
        Number of running bridge manager instance containers
    """
    count = 0
    i = 1
    while True:
        name = f"{homeserver_id}_bridge_manager_{i}"
        try:
            docker_client.containers.get(name)
            count += 1
            i += 1
        except docker.errors.NotFound:
            break
    return count


def deploy_bridge_manager_instance(
    homeserver_id: str,
    instance_num: int,
    network_name: str,
    base_dir: Path,
    env_file: Optional[Path] = None,
):
    """
    Deploy a single additional bridge manager instance.

    Args:
        homeserver_id: The homeserver ID
        instance_num: Instance number (1-indexed)
        network_name: Docker network name
        base_dir: Base deployment directory
        env_file: Path to .env file (default: homeserver/.env)
    """
    service = BridgeManagerService(
        homeserver_id=homeserver_id,
        base_dir=base_dir,
        network_name=network_name,
        num_instances=1,
        env_file=env_file,
    )
    service._ensure_configs_volume()
    env_vars = service._load_env_vars()
    service._deploy_instance(instance_num, env_vars)
    print(f"  ✓ Bridge manager instance {instance_num} deployed")


def remove_bridge_manager_instance(homeserver_id: str, instance_num: int):
    """
    Remove a single bridge manager instance container.

    Args:
        homeserver_id: The homeserver ID
        instance_num: Instance number (1-indexed)
    """
    name = f"{homeserver_id}_bridge_manager_{instance_num}"
    try:
        container = docker_client.containers.get(name)
        container.stop()
        container.remove()
        print(f"  ✓ Removed bridge manager instance {instance_num}")
    except docker.errors.NotFound:
        pass


def update_nginx_bm_config(
    homeserver_id: str,
    num_instances: int,
    base_dir: Path,
) -> bool:
    """
    Regenerate the bridge manager nginx config and reload without restart.

    Args:
        homeserver_id: The homeserver ID
        num_instances: New total number of instances
        base_dir: Base deployment directory

    Returns:
        True if successful
    """
    network_name = f"{homeserver_id}_network"
    nginx_service = BridgeManagerNginxService(
        homeserver_id=homeserver_id,
        base_dir=base_dir,
        network_name=network_name,
        num_instances=num_instances,
    )
    return nginx_service.update_config(num_instances=num_instances, reload=True)


def scale_bridge_managers(
    homeserver_id: str,
    target_instances: int,
    deployments_dir: Path,
    env_file: Optional[Path] = None,
    delay_between: float = 1.0,
):
    """
    Scale bridge manager instances up or down.

    Steps:
    1. Scale containers (add or remove)
    2. Reload bridge manager nginx config

    Args:
        homeserver_id: The homeserver to scale
        target_instances: Desired number of bridge manager instances
        deployments_dir: Path to the deployments directory
        env_file: Path to .env file (default: homeserver/.env)
        delay_between: Seconds to wait between instance starts
    """
    base_dir = deployments_dir / homeserver_id
    network_name = f"{homeserver_id}_network"

    current = get_bridge_manager_count(homeserver_id)

    print(f"Current bridge manager instances: {current}")
    print(f"Target bridge manager instances:  {target_instances}")

    if target_instances == current:
        print("No scaling needed")
        return

    if target_instances < 1:
        raise ValueError("At least one bridge manager instance must remain running")

    if target_instances > current:
        print(
            f"Scaling up: adding {target_instances - current} bridge manager instance(s)..."
        )
        for i in range(current + 1, target_instances + 1):
            deploy_bridge_manager_instance(
                homeserver_id=homeserver_id,
                instance_num=i,
                network_name=network_name,
                base_dir=base_dir,
                env_file=env_file,
            )
            if i < target_instances:
                time.sleep(delay_between)
    else:
        print(
            f"Scaling down: removing {current - target_instances} bridge manager instance(s)..."
        )
        for i in range(current, target_instances, -1):
            remove_bridge_manager_instance(homeserver_id, i)

    # Reload nginx to reflect new upstream set
    update_nginx_bm_config(homeserver_id, target_instances, base_dir)

    print(f"✓ Bridge manager scaled to {target_instances} instance(s)")


def get_bridge_manager_status(homeserver_id: str):
    """
    Print status of all bridge manager instances.

    Args:
        homeserver_id: The homeserver ID
    """
    print(f"Bridge manager instance status for {homeserver_id}:")

    i = 1
    found = False
    while True:
        name = f"{homeserver_id}_bridge_manager_{i}"
        try:
            container = docker_client.containers.get(name)
            port_info = (
                container.attrs.get("NetworkSettings", {})
                .get("Ports", {})
                .get(f"{config.BRIDGE_MANAGER_INTERNAL_PORT}/tcp", [{}])
            )
            host_port = (port_info[0].get("HostPort", "N/A") if port_info else "N/A")
            print(f"  Instance {i}: {container.status} (host port {host_port})")
            found = True
            i += 1
        except docker.errors.NotFound:
            break

    # Check nginx LB
    nginx_name = f"{homeserver_id}_nginx_bm"
    try:
        nginx = docker_client.containers.get(nginx_name)
        print(
            f"\n  nginx_bm ({nginx_name}): {nginx.status} "
            f"(LB port {config.BRIDGE_MANAGER_NGINX_PORT})"
        )
    except docker.errors.NotFound:
        print(f"\n  nginx_bm ({nginx_name}): not deployed")

    if not found:
        print("  No bridge manager instances deployed")
    else:
        print(f"\nTotal: {i - 1} instance(s)")


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Scale bridge manager instances for a homeserver deployment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
        Examples:
            python bridge_manager_scaler.py hs-001 --scale 3   # Scale to 3 instances
            python bridge_manager_scaler.py hs-001 --scale 1   # Scale back to 1
            python bridge_manager_scaler.py hs-001 --status    # Check instance status
        """,
    )

    parser.add_argument("homeserver_id", help="The homeserver ID to manage")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--scale",
        type=int,
        metavar="N",
        help="Scale to N bridge manager instances (minimum 1)",
    )
    group.add_argument(
        "--status",
        action="store_true",
        help="Show status of all bridge manager instances",
    )

    args = parser.parse_args()

    # Deployments dir is relative to the homeserver directory
    deployments_dir = Path("deployments")

    try:
        if args.status:
            get_bridge_manager_status(args.homeserver_id)
        elif args.scale is not None:
            scale_bridge_managers(
                homeserver_id=args.homeserver_id,
                target_instances=args.scale,
                deployments_dir=deployments_dir,
            )
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)
