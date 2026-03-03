"""
Bridge orchestrator for managing bridge container lifecycle.

Handles creation, configuration, deployment, monitoring, and deletion of bridge containers.
"""

import io
import os
import socket
import tarfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

import docker
import requests
from jinja2 import Environment, FileSystemLoader, select_autoescape

from config import BRIDGE_MANAGER_CONFIG
from bridge_manager.database.models import Bridge, BridgeType, BridgeStatus
from bridge_manager.database.repositories import (
    BridgeRepository,
    HomeserverRepository,
)
from bridge_manager.logger import BridgeLogger
from bridge_manager.orchestrator.bridges import WhatsAppBridge
from bridge_manager.orchestrator.docker_client import DockerClientManager
from bridge_manager.orchestrator.errors import (
    BridgeCreationError,
    BridgeStartError,
    BridgeStopError,
    BridgeDeletionError,
    ConfigurationError,
    HealthCheckError,
)
from bridge_manager.appservice.token_manager import TokenManager


class BridgeOrchestrator:
    """
    Main orchestrator for managing bridge containers.

    Provides high-level operations for creating, monitoring, and managing bridge
    containers across potentially multiple Docker hosts.
    """

    def __init__(self):
        """Initialize orchestrator with Docker client manager and logger."""
        self.docker_manager = DockerClientManager()
        self.logger = BridgeLogger()
        self.jinja_env = Environment(
            loader=FileSystemLoader(BRIDGE_MANAGER_CONFIG.TEMPLATES_DIR),
            autoescape=select_autoescape(),
            # Use [[ ]] delimiters to avoid conflicts with bridge config {{ }}
            variable_start_string="[[",
            variable_end_string="]]",
            block_start_string="[%",
            block_end_string="%]",
            comment_start_string="[#",
            comment_end_string="#]",
        )

    def create_bridge(
        self,
        bridge_type: BridgeType,
        homeserver_id: str,
        owner_matrix_username: str,
        docker_host: Optional[str] = None,
    ) -> Bridge:
        """
        Create and start a new bridge instance.

        Complete workflow:
        1. Initialize bridge-specific configuration
        2. Allocate port for appservice
        3. Create Docker volume and container
        4. Generate and copy configuration
        5. Start container and wait for health checks
        6. Register bridge in database

        Args:
            bridge_type: Type of bridge to create (e.g., BridgeType.WHATSAPP)
            homeserver_id: ID of homeserver to connect to
            owner_matrix_username: Matrix user ID that owns this bridge
            docker_host: Optional Docker host URI for remote deployment

        Returns:
            Bridge: Database record of created bridge

        Raises:
            BridgeCreationError: If bridge creation fails at any step
            ConfigurationError: If config generation or template rendering fails
            HealthCheckError: If bridge fails health checks after starting
        """
        if not owner_matrix_username:
            raise BridgeCreationError("owner_matrix_username is required")
        # Initialize bridge-specific configuration
        if bridge_type == BridgeType.WHATSAPP:
            bridge = WhatsAppBridge()
        else:
            raise BridgeCreationError(f"Unsupported bridge type: {bridge_type}")

        # Get homeserver details
        homeserver = HomeserverRepository.get_by_id(homeserver_id)
        if not homeserver:
            raise BridgeCreationError(f"Homeserver {homeserver_id} not found")

        # Initialize bridge with unique ID
        bridge_id = str(uuid.uuid4())[:8]
        bridge.initialize(
            bridge_id=bridge_id,
            homeserver_id=homeserver_id,
            homeserver_name=homeserver.name,
            homeserver_address=homeserver.url,
            owner_matrix_username=owner_matrix_username,
            docker_host=docker_host,
        )

        # Allocate port and configure appservice addresses
        port = self._get_free_port()
        bridge.appservice_port = port
        bridge.config_params["appservice_port"] = port

        bridge.appservice_address = f"http://{BRIDGE_MANAGER_CONFIG.BRIDGE_MANAGER_HOSTNAME}:{BRIDGE_MANAGER_CONFIG.PORT}/bridge/{bridge_id}"
        bridge.config_params["appservice_address"] = bridge.appservice_address
        bridge.config_params["homeserver_address"] = bridge.appservice_address

        # Get Docker client
        docker_client = self.docker_manager.get_client(docker_host)

        # Create volume
        volume = self._create_volume(bridge, docker_client)

        # Create container
        try:
            container = self._create_container(bridge, bridge_type, port, docker_client)
        except BridgeCreationError:
            self._cleanup_on_failure(volume=volume)
            raise

        # Generate and copy config
        try:
            config_content = self._generate_config(
                bridge_type=bridge_type,
                params=bridge.config_params,
            )
            self.logger.log_debug(f"Generated config for bridge {bridge_id}")

            self._copy_config_to_container(
                container, config_content, bridge_type, bridge_id
            )
        except (ConfigurationError, BridgeCreationError):
            self._cleanup_on_failure(container, volume)
            raise

        # Save to database
        bridge_record = self._save_bridge_record(
            bridge, bridge_type, container, homeserver_id, docker_host
        )

        # Start container and wait for health
        try:
            self._start_and_wait_for_health(container, port, bridge_id)
        except (BridgeStartError, HealthCheckError):
            self._cleanup_on_failure(container, volume)
            raise

        return bridge_record

    def check_bridge_status(
        self,
        bridge_id: str,
    ) -> BridgeStatus:
        """
        Check the health and status of a bridge.

        Performs health checks on the bridge's HTTP endpoints and updates database status.

        Args:
            bridge_id: ID of bridge to check

        Returns:
            BridgeStatus: Current status of the bridge

        Raises:
            ValueError: If bridge not found
        """
        bridge = BridgeRepository.get_by_orchestrator_id(bridge_id)

        if not bridge:
            raise ValueError(f"Bridge {bridge_id} not found")

        # Check if container exists and is running
        try:
            docker_client = self.docker_manager.get_client(bridge.host)
            container = docker_client.containers.get(bridge.container_id)

            if container.status != "running":
                BridgeRepository.update_status(bridge.id, BridgeStatus.STOPPED.value)
                return BridgeStatus.STOPPED
        except docker.errors.NotFound:
            BridgeRepository.update_status(bridge.id, BridgeStatus.DELETED.value)
            return BridgeStatus.DELETED
        except Exception as e:
            self.logger.log_error(f"Error checking container: {e}")
            BridgeRepository.update_status(bridge.id, BridgeStatus.ERROR.value)
            return BridgeStatus.ERROR

        # Check health endpoints
        try:
            self._check_health_endpoints(
                host="localhost",
                port=bridge.port,
            )
            BridgeRepository.update_status(bridge.id, BridgeStatus.RUNNING.value)
            return BridgeStatus.RUNNING
        except HealthCheckError:
            BridgeRepository.update_status(bridge.id, BridgeStatus.UNHEALTHY.value)
            return BridgeStatus.UNHEALTHY

    def stop_bridge(
        self,
        bridge_id: str,
    ) -> None:
        """
        Stop a running bridge container.

        Args:
            bridge_id: ID of bridge to stop

        Raises:
            BridgeStopError: If bridge cannot be stopped
            ValueError: If bridge not found
        """
        bridge = BridgeRepository.get_by_orchestrator_id(bridge_id)

        if not bridge:
            raise ValueError(f"Bridge {bridge_id} not found")

        try:
            docker_client = self.docker_manager.get_client(bridge.host)
            container = docker_client.containers.get(bridge.container_id)
            container.stop(timeout=10)

            BridgeRepository.update_status(bridge.id, BridgeStatus.STOPPED.value)
            self.logger.log_info(f"Stopped bridge {bridge_id}")
        except docker.errors.NotFound:
            raise BridgeStopError(f"Container not found for bridge {bridge_id}")
        except Exception as e:
            raise BridgeStopError(f"Failed to stop bridge: {e}")

    def start_bridge(
        self,
        bridge_id: str,
    ) -> None:
        """
        Start a stopped bridge container.

        Args:
            bridge_id: ID of bridge to start

        Raises:
            BridgeStartError: If bridge cannot be started
            ValueError: If bridge not found
        """
        bridge = BridgeRepository.get_by_orchestrator_id(bridge_id)

        if not bridge:
            raise ValueError(f"Bridge {bridge_id} not found")

        try:
            docker_client = self.docker_manager.get_client(bridge.host)
            container = docker_client.containers.get(bridge.container_id)
            container.start()

            BridgeRepository.update_status(bridge.id, BridgeStatus.STARTING.value)
            self.logger.log_info(f"Started bridge {bridge_id}")

            # Wait for health checks
            self._wait_for_health_checks(
                host="localhost",
                port=bridge.port,
                timeout=60,
            )
            BridgeRepository.update_status(bridge.id, BridgeStatus.RUNNING.value)

        except docker.errors.NotFound:
            raise BridgeStartError(f"Container not found for bridge {bridge_id}")
        except HealthCheckError as e:
            BridgeRepository.update_status(bridge.id, BridgeStatus.UNHEALTHY.value)
            raise BridgeStartError(f"Bridge started but failed health checks: {e}")
        except Exception as e:
            raise BridgeStartError(f"Failed to start bridge: {e}")

    def delete_bridge(
        self,
        bridge_id: str,
        remove_volume: bool = True,
    ) -> None:
        """
        Delete a bridge and optionally its persistent data.

        Stops and removes the container, optionally removes the volume,
        and deletes the database record.

        Args:
            bridge_id: ID of bridge to delete
            remove_volume: Whether to also remove the persistent data volume

        Raises:
            BridgeDeletionError: If bridge cannot be deleted
            ValueError: If bridge not found
        """
        bridge = BridgeRepository.get_by_orchestrator_id(bridge_id)

        if not bridge:
            raise ValueError(f"Bridge {bridge_id} not found")

        docker_client = self.docker_manager.get_client(bridge.host)

        # Stop and remove container
        try:
            container = docker_client.containers.get(bridge.container_id)
            container.stop(timeout=10)
            container.remove()
            self.logger.log_info(f"Removed container for bridge {bridge_id}")
        except docker.errors.NotFound:
            self.logger.log_warning(f"Container not found for bridge {bridge_id}")
        except Exception as e:
            raise BridgeDeletionError(f"Failed to remove container: {e}")

        # Optionally remove volume
        if remove_volume and bridge.volume_name:
            try:
                volume = docker_client.volumes.get(bridge.volume_name)
                volume.remove()
                self.logger.log_info(f"Removed volume {bridge.volume_name}")
            except docker.errors.NotFound:
                self.logger.log_warning(f"Volume not found: {bridge.volume_name}")
            except Exception as e:
                self.logger.log_warning(f"Failed to remove volume: {e}")

        # Soft delete from database
        BridgeRepository.soft_delete(bridge.id)
        self.logger.log_success(f"Deleted bridge {bridge_id}")

    def _create_volume(self, bridge: WhatsAppBridge, docker_client) -> any:
        """
        Create Docker volume for bridge persistent data.

        Args:
            bridge: Bridge instance with volume configuration
            docker_client: Docker client to use for volume creation

        Returns:
            Docker volume object

        Raises:
            BridgeCreationError: If volume creation fails
        """
        try:
            volume = docker_client.volumes.create(
                name=bridge.volume_name,
                driver="local",
            )
            self.logger.log_info(
                f"Created volume {bridge.volume_name} for bridge {bridge.bridge_id}"
            )
            return volume
        except Exception as e:
            raise BridgeCreationError(f"Failed to create volume: {e}")

    def _create_container(
        self,
        bridge: WhatsAppBridge,
        bridge_type: BridgeType,
        port: int,
        docker_client,
    ) -> any:
        """
        Create Docker container for bridge (but don't start it yet).

        Args:
            bridge: Bridge instance with container configuration
            bridge_type: Type of bridge being created
            port: Port to expose for appservice
            docker_client: Docker client to use for container creation

        Returns:
            Docker container object

        Raises:
            BridgeCreationError: If container creation fails
        """
        try:
            container = docker_client.containers.create(
                image=BRIDGE_MANAGER_CONFIG.WHATSAPP.docker_image,
                name=f"bridge_{bridge_type.value}_{bridge.bridge_id}",
                detach=True,
                restart_policy=BRIDGE_MANAGER_CONFIG.RESTART_POLICY,
                network_mode=BRIDGE_MANAGER_CONFIG.NETWORK_MODE,
                volumes={
                    bridge.volume_name: {
                        "bind": "/data",
                        "mode": "rw",
                    }
                },
                entrypoint=BRIDGE_MANAGER_CONFIG.WHATSAPP.entrypoint,
            )
            bridge.container_id = container.id

            self.logger.log_info(
                f"Created container {container.name} for bridge {bridge.bridge_id}"
            )
            return container
        except Exception as e:
            raise BridgeCreationError(f"Failed to create container: {e}")

    def _copy_config_to_container(
        self,
        container,
        config_content: str,
        bridge_type: BridgeType,
        bridge_id: str,
    ) -> None:
        """
        Copy generated configuration into container.

        Args:
            container: Docker container to copy config into
            config_content: Generated configuration content
            bridge_type: Type of bridge
            bridge_id: ID of bridge (for logging)

        Raises:
            BridgeCreationError: If copying config fails
        """
        try:
            config_tar = self._get_file_as_tar(
                config_content,
                BRIDGE_MANAGER_CONFIG.WHATSAPP.config_path_in_container,
            )
            container.put_archive("/", config_tar)
            self.logger.log_info(f"Copied config to container for bridge {bridge_id}")
        except Exception as e:
            raise BridgeCreationError(f"Failed to copy config to container: {e}")

    def _start_and_wait_for_health(
        self,
        container,
        port: int,
        bridge_id: str,
    ) -> None:
        """
        Start container and wait for health checks to pass.

        Args:
            container: Docker container to start
            port: Port for health checks
            bridge_id: ID of bridge (for logging)

        Raises:
            BridgeStartError: If container fails to start
            HealthCheckError: If health checks don't pass
        """
        try:
            container.start()
            self.logger.log_info(f"Started container for bridge {bridge_id}")
        except Exception as e:
            raise BridgeStartError(f"Failed to start container: {e}")

        # Wait for health checks to pass
        try:
            self._wait_for_health_checks(
                host="localhost",
                port=port,
                timeout=60,
            )
            self.logger.log_success(f"Bridge {bridge_id} is running and healthy")
        except HealthCheckError as e:
            self.logger.log_error(f"Bridge {bridge_id} failed health checks: {e}")
            raise

    def _save_bridge_record(
        self,
        bridge: WhatsAppBridge,
        bridge_type: BridgeType,
        container,
        homeserver_id: str,
        docker_host: Optional[str],
    ) -> Bridge:
        """
        Create database record for successfully created bridge.

        Args:
            bridge: Bridge instance with all configuration
            bridge_type: Type of bridge
            container: Docker container object
            homeserver_id: ID of connected homeserver
            docker_host: Docker host URI (or None for local)

        Returns:
            Bridge: Database record
        """
        bridge_record = BridgeRepository.create(
            orchestrator_id=bridge.bridge_id,
            bridge_type=bridge_type.value,
            container_id=container.id,
            container_name=container.name,
            volume_name=bridge.volume_name,
            host=docker_host or "local",
            port=bridge.appservice_port,
            as_token=bridge.as_token,
            hs_token=bridge.hs_token,
            homeserver_id=homeserver_id,
            bridge_manager_id=BRIDGE_MANAGER_CONFIG.INSTANCE_ID,
            matrix_bot_username=bridge.matrix_bot_username,
            owner_matrix_username=bridge.owner_matrix_username,
            bridge_management_room_id=None,  # Will be set later when room is created
        )
        return bridge_record

    def _cleanup_on_failure(self, container=None, volume=None) -> None:
        """
        Centralized cleanup for failed bridge creation.

        Args:
            container: Docker container to remove (optional)
            volume: Docker volume to remove (optional)
        """
        if container:
            try:
                container.remove(force=True)
            except Exception as e:
                self.logger.log_warning(
                    f"Failed to remove container during cleanup: {e}"
                )

        if volume:
            try:
                volume.remove()
            except Exception as e:
                self.logger.log_warning(f"Failed to remove volume during cleanup: {e}")

    def _generate_config(
        self,
        bridge_type: BridgeType,
        params: Dict,
    ) -> str:
        """
        Generate bridge configuration from Jinja2 template.

        Args:
            bridge_type: Type of bridge
            params: Parameters for template rendering

        Returns:
            str: Rendered configuration content

        Raises:
            ConfigurationError: If template rendering fails
        """
        try:
            if bridge_type == BridgeType.WHATSAPP:
                template_name = BRIDGE_MANAGER_CONFIG.WHATSAPP.config_template
            else:
                raise ConfigurationError(f"No template for bridge type: {bridge_type}")

            template = self.jinja_env.get_template(template_name)
            return template.render(**params)
        except Exception as e:
            raise ConfigurationError(f"Failed to render template: {e}")

    def _get_free_port(self) -> int:
        """
        Find and return an available port on localhost.

        Uses socket binding to find a free port that the OS allocates.

        Returns:
            int: Free port number
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", 0))
            s.listen(1)
            port = s.getsockname()[1]
        return port

    def _get_file_as_tar(self, content: str, path: str) -> bytes:
        """
        Create a tar archive containing a single file.

        Used to copy configuration files into Docker containers.

        Args:
            content: File content as string
            path: Path where file should be placed in container

        Returns:
            bytes: Tar archive as bytes
        """
        tar_stream = io.BytesIO()
        tar = tarfile.open(fileobj=tar_stream, mode="w")

        # Create tarinfo for the file
        file_data = content.encode("utf-8")
        tarinfo = tarfile.TarInfo(name=path.lstrip("/"))
        tarinfo.size = len(file_data)
        tarinfo.mtime = time.time()

        # Add file to tar
        tar.addfile(tarinfo, io.BytesIO(file_data))
        tar.close()

        tar_stream.seek(0)
        return tar_stream.read()

    def _check_health_endpoints(
        self,
        host: str,
        port: int,
    ) -> None:
        """
        Check bridge health endpoints.

        Pings the bridge's liveness and readiness endpoints to verify it's operational.

        Args:
            host: Host to check
            port: Port to check

        Raises:
            HealthCheckError: If health checks fail
        """
        base_url = f"http://{host}:{port}"

        # Check liveness endpoint
        try:
            response = requests.get(
                f"{base_url}/{BRIDGE_MANAGER_CONFIG.WHATSAPP.health_live_endpoint}",
                timeout=5,
            )
            if response.status_code != 200:
                raise HealthCheckError(f"Liveness check failed: {response.status_code}")
        except requests.exceptions.RequestException as e:
            raise HealthCheckError(f"Liveness check failed: {e}")

        # Check readiness endpoint
        try:
            response = requests.get(
                f"{base_url}/{BRIDGE_MANAGER_CONFIG.WHATSAPP.health_ready_endpoint}",
                timeout=5,
            )
            if response.status_code != 200:
                raise HealthCheckError(
                    f"Readiness check failed: {response.status_code}"
                )
        except requests.exceptions.RequestException as e:
            raise HealthCheckError(f"Readiness check failed: {e}")

    def _wait_for_health_checks(
        self,
        host: str,
        port: int,
        timeout: int = 60,
        interval: int = 2,
    ) -> None:
        """
        Wait for bridge health checks to pass.

        Polls health endpoints until they return successful responses or timeout is reached.

        Args:
            host: Host to check
            port: Port to check
            timeout: Maximum seconds to wait
            interval: Seconds between check attempts

        Raises:
            HealthCheckError: If health checks don't pass within timeout
        """
        start_time = time.time()
        last_error = None

        while time.time() - start_time < timeout:
            try:
                self._check_health_endpoints(host, port)
                return  # Health checks passed
            except HealthCheckError as e:
                last_error = e
                time.sleep(interval)

        # Timeout reached
        raise HealthCheckError(
            f"Health checks did not pass within {timeout}s. Last error: {last_error}"
        )

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close Docker connections."""
        self.docker_manager.close_all()
