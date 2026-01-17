"""
Centralized Nginx configuration management

Handles generation and reloading of nginx configs for Matrix homeserver deployments.
Uses a template-based approach with variable substitution.
"""

import docker
from pathlib import Path
import homeserver_config as config

docker_client = docker.from_env()


def generate_nginx_config(
    homeserver_id: str,
    domain: str,
    num_workers: int,
    synapse_container: str = None,
) -> str:
    """
    Generate nginx configuration from template with variable substitution

    Args:
        homeserver_id: The homeserver ID
        domain: Domain name for the server
        num_workers: Number of workers (0 = monolith mode)
        synapse_container: Name of main synapse container (used when num_workers=0)

    Returns:
        Generated nginx configuration as string
    """
    # Load template
    template_path = Path(__file__).parent / "nginx_config_template.conf"
    with open(template_path, "r") as f:
        template = f.read()

    # Build upstream servers block
    if num_workers > 0:
        # Load balance across workers
        upstream_servers = "\n".join(
            f"    server {homeserver_id}_worker{i}:{config.WORKER_BASE_PORT};"
            for i in range(1, num_workers + 1)
        )
    else:
        # Single main process
        if synapse_container is None:
            synapse_container = f"{homeserver_id}_synapse"
        upstream_servers = f"    server {synapse_container}:{config.SYNAPSE_HTTP_PORT};"

    # Substitute variables
    nginx_config = template.replace("{{UPSTREAM_SERVERS}}", upstream_servers)
    nginx_config = nginx_config.replace(
        "{{NGINX_STATUS_PORT}}", str(config.NGINX_STATUS_PORT)
    )
    nginx_config = nginx_config.replace(
        "{{NGINX_HTTP_PORT}}", str(config.NGINX_HTTP_PORT)
    )
    nginx_config = nginx_config.replace("{{DOMAIN}}", domain)
    nginx_config = nginx_config.replace(
        "{{CLIENT_MAX_BODY_SIZE}}", config.NGINX_CLIENT_MAX_BODY_SIZE
    )

    return nginx_config


def write_nginx_config(config_path: Path, nginx_config: str):
    """
    Write nginx configuration to file

    Args:
        config_path: Path to write config file
        nginx_config: Nginx configuration string
    """
    with open(config_path, "w") as f:
        f.write(nginx_config)


def reload_nginx(homeserver_id: str) -> bool:
    """
    Reload nginx configuration in running container

    Args:
        homeserver_id: The homeserver ID

    Returns:
        True if reload successful, False otherwise
    """
    try:
        nginx_container = docker_client.containers.get(f"{homeserver_id}_nginx")
        result = nginx_container.exec_run("nginx -s reload")
        return result.exit_code == 0
    except docker.errors.NotFound:
        return False


def update_nginx_config(
    homeserver_id: str,
    domain: str,
    num_workers: int,
    base_dir: Path,
    synapse_container: str = None,
    reload: bool = True,
):
    """
    Generate, write, and optionally reload nginx configuration

    Args:
        homeserver_id: The homeserver ID
        domain: Domain name for the server
        num_workers: Total number of workers
        base_dir: Base deployment directory
        synapse_container: Name of main synapse container (optional)
        reload: Whether to reload nginx after writing config
    """
    nginx_dir = base_dir / "nginx"
    config_path = nginx_dir / "synapse.conf"

    if not config_path.exists():
        print("  ! Nginx not deployed, skipping")
        return

    # Generate config
    nginx_config = generate_nginx_config(
        homeserver_id=homeserver_id,
        domain=domain,
        num_workers=num_workers,
        synapse_container=synapse_container,
    )

    # Write to file
    write_nginx_config(config_path, nginx_config)

    # Reload if requested
    if reload:
        if reload_nginx(homeserver_id):
            print("  ✓ Updated and reloaded nginx config")
        else:
            print("  ! Failed to reload nginx (container not found)")
    else:
        print("  ✓ Nginx configuration written")
