"""
This will create and manage bridges. Bridges are created by deploying bridge docker containers with custom configs.

This module needs to:

1. Create new bridges
    - each bridge will need a custom ID so each user created by this bridge is uniquly identifiable on the homeserver
    - I'll have to handle port mappings. bridges can't use their default port on the external network

2. Check the status of existing bridges
    - there must be some health check endpoint I can use

3. Delete bridges

4. Register the bridge in the database


Questions:

- Where is the data stored?
  - mounted storage vs managed by docker

-

Tasks:

1. Create bridge docker instance
2. Find a way to template the bridge config files and upload them to docker container

3. bridge status checker
4. delete bridge

"""

from datetime import datetime, timezone
from dataclasses import dataclass
import tarfile
import socket
import random
import uuid
import io

import jinja2
import docker
import requests

from bridge_manager.database.repositories import HomeserversRepository
from bridge_manager.config import BridgeManagerConfig
from bridge_manager.bridge_registry import BridgeRegistry
from bridge_manager.database.models import Bridges
from bridge_manager.database.repositories import BridgesRepository


TEMPLATES_PATH = "bridge_manager/orchestrator/config_templates"
CONFIGS_PATH = "bridge_manager/orchestrator/configs"


@dataclass
class Whatsapp:

    SERVICE = "whatsapp"

    # docker image to create the bridge with
    DOCKER_IMAGE = "dock.mau.dev/mautrix/whatsapp:latest"

    # The bridges config file name in the config_templates folder
    CONFIG_TEMPLATE_FILENAME = "whatsapp.yaml"

    # The location in the bridge container the config file should go
    CONFIG_LOCATION_BRIDGE = "/data/"

    ID = None
    CONTAINER_NAME = None
    HS_TOKEN = None

    PARAMS = {
        "homeserver_address": None,
        "homeserver_name": None,
        "appservice_address": None,
        "appservice_hostname": None,
        "appservice_port": None,
        "appservice_id": None,
        "appservice_bot_username": None,
        "appservice_as_token": None,
        "appservice_hs_token": None,
    }

    def initialise(self, homeserver, bridge_port):

        self.ID = uuid.uuid4().hex[:8]
        self.CONTAINER_NAME = f"bridge_manager__wa_{self.ID}"
        self.MATRIX_BOT_USERNAME = (
            f"@_bridge_manager__wa_{self.ID}__whatsappbot:{homeserver.name}"
        )

        self.HS_TOKEN = homeserver.hs_token
        self.AS_TOKEN = uuid.uuid4().hex

        # self.PARAMS["homeserver_address"] = (
        #     f"http://{BridgeManagerConfig.HOST}:{BridgeManagerConfig.PORT}/bridge"
        # )
        self.PARAMS["homeserver_address"] = (
            f"http://host.docker.internal:{BridgeManagerConfig.PORT}/bridge"
        )
        self.PARAMS["homeserver_name"] = homeserver.name

        self.PARAMS["appservice_address"] = f"http://whatsapp-brige:{bridge_port}"
        self.PARAMS["appservice_hostname"] = "0.0.0.0"
        self.PARAMS["appservice_port"] = bridge_port
        self.PARAMS["appservice_id"] = self.ID

        self.PARAMS["appservice_as_token"] = self.AS_TOKEN
        self.PARAMS["appservice_hs_token"] = homeserver.hs_token


class BridgeOrchestrator:

    def __init__(self, bridge_manager_config):

        self.docker_client = docker.from_env()
        self.bridge_registry = BridgeRegistry(bridge_manager_config)
        self.bridge_manager_config = bridge_manager_config

    def create_bridge(self, bridge, owner_matrix_username):

        bridge_mapper = {"whatsapp": Whatsapp}
        bridge_cls = bridge_mapper.get(bridge)
        if not bridge:
            raise ValueError(f"Unsupported bridge type: {bridge}")
        bridge = bridge_cls()

        # Initialise bridge
        # The bridge needs to know which homeserver it belongs and what port it should listen on
        homeserver = self._get_homeserver()
        free_port = self._get_free_port()
        bridge.initialise(homeserver=homeserver, bridge_port=free_port)

        # Create the container (without running it)
        # I need to copy the config file into the container before running it
        container = self.docker_client.containers.create(
            image=bridge.DOCKER_IMAGE,
            name=bridge.CONTAINER_NAME,
            detach=True,
            ports={
                free_port: ("0.0.0.0", free_port),
                # BridgeManagerConfig.PORT: ("0.0.0.0", BridgeManagerConfig.PORT),
            },
            # network_mode="host",
            restart_policy={"Name": "unless-stopped"},
            volumes=["wa_data:/data"],
        )

        # start container so it can run it's initial script (they auto stop as a result of this initial script)
        container.start()

        # create a new bridge config and save it so I can later copy to the container
        config_file_path = self.create_bridge_config(bridge)

        # copy the config file into the container
        config_file = self._get_file_as_tar(
            config_file_path, archive_name="config.yaml"
        )
        container.put_archive(bridge.CONFIG_LOCATION_BRIDGE, config_file)

        # start container
        container.start()

        # register the bridge in the database
        bridge_model = self.bridge_registry.register_bridge(
            bridge_service=bridge.SERVICE,
            matrix_bot_username=bridge.MATRIX_BOT_USERNAME,
            as_token=bridge.AS_TOKEN,
            hs_token=bridge.HS_TOKEN,
            ip=bridge.PARAMS["appservice_hostname"],
            port=bridge.PARAMS["appservice_port"],
            owner_matrix_username=owner_matrix_username,
        )

        return bridge_model

    def create_bridge_config(self, bridge):
        """
        Creates a bridge configuration by rendering a Jinja2 config template.
        """

        # Configure Jinja to use non-conflicting delimiters so {{ ... }} in the
        # upstream WhatsApp template remains literal.
        environment = jinja2.Environment(
            loader=jinja2.FileSystemLoader(TEMPLATES_PATH),
            variable_start_string="[[",
            variable_end_string="]]",
        )
        template = environment.get_template(bridge.CONFIG_TEMPLATE_FILENAME)

        # Validate that all template variables are defined in bridge.PARAMS
        template_source = environment.loader.get_source(
            environment, bridge.CONFIG_TEMPLATE_FILENAME
        )[0]
        parsed_content = environment.parse(template_source)
        template_vars = {var.name for var in parsed_content.find_all(jinja2.nodes.Name)}
        missing_vars = template_vars - bridge.PARAMS.keys()

        if missing_vars:
            raise ValueError(
                f"Template variables not defined in bridge.PARAMS: {sorted(missing_vars)}"
            )

        # Render template; add variables via template.render(...) if needed
        config_text = template.render(bridge.PARAMS)

        # Write config file to configs folder
        path = f"{CONFIGS_PATH}/{bridge.ID}.yaml"
        with open(path, "w", encoding="utf-8") as f:
            f.write(config_text)

        return path

    def check_bridge_status(self, bridge_model: Bridges):
        """
        Check the status of a bridge by pinging the live and ready endpoints on the bridge

        Args:
            bridge_model (Bridges): bridge database model
        """

        ip = bridge_model.ip
        port = bridge_model.port
        live_endpoint = "_matrix/mau/live"
        ready_endpoint = "_matrix/mau/ready"

        try:
            live_response = requests.get(f"http://{ip}:{port}/{live_endpoint}")
            ready_response = requests.get(f"http://{ip}:{port}/{ready_endpoint}")

            live_status = live_response.status_code
            ready_status = ready_response.status_code

        except requests.RequestException:

            live_status = "unknown"
            ready_status = "unknown"

        # Persist changes to database
        repository = BridgesRepository()
        repository.update(
            id_=bridge_model.id,
            live_status=live_status,
            ready_status=ready_status,
            status_updated_at=datetime.now(timezone.utc),
        )

    def _get_homeserver(self):
        homeservers = HomeserversRepository().get_all()
        if not homeservers:
            raise ValueError("No homeservers available in database")
        return random.choice(homeservers)

    def _get_free_port(self):
        """
        Get a free port on the machine
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("", 0))
        s.listen(1)
        port = s.getsockname()[1]
        s.close()
        return port

    def _get_file_as_tar(self, path, archive_name="config.yaml"):
        """
        To copy config files into the container I need to convert them into a tar stream.
        """
        tar_stream = io.BytesIO()
        with tarfile.open(fileobj=tar_stream, mode="w") as tar:
            tar.add(path, arcname=archive_name)
        tar_stream.seek(0)

        return tar_stream.read()


bridge_manager_config = BridgeManagerConfig()
orchestrator = BridgeOrchestrator(bridge_manager_config)

bridge_model = orchestrator.create_bridge(
    bridge="whatsapp", owner_matrix_username="@admin:matrix.localhost.me"
)

# repo = BridgesRepository()
# bridges = repo.get_all()
# for bridge in bridges:
#     orchestrator.check_bridge_status(bridge)
