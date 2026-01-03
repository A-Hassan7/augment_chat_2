import asyncio

from .config import BridgeManagerConfig
from .orchestrator.orchestrator import BridgeOrchestrator
from .bridge_clients.whatsapp_bridge_client import WhatsappBridgeClient
from .bridge_registry import BridgeRegistry


class BridgeManagerInterface:

    def __init__(self):
        # self.whatsapp_client = WhatsappBridgeClient()
        self.bridge_orchestrator = BridgeOrchestrator(BridgeManagerConfig())
        self.bridge_registry = BridgeRegistry(BridgeManagerConfig())

    def create_bridge(self, matrix_username, service):

        bridge_model = self.bridge_orchestrator.create_bridge(
            bridge=service, owner_matrix_username=matrix_username
        )
        return bridge_model

    def login(self, bridge, phone_number: str):
        bridge_mapper = {"whatsapp": WhatsappBridgeClient}

        bridge_client_cls = bridge_mapper.get(bridge.bridge_service)
        bridge_client = bridge_client_cls(bridge)

        try:
            asyncio.run(bridge_client.register())
        except Exception as e:
            # Bridge already exists or registration failed, continue with login
            print(e)
            pass

        login_code = asyncio.run(bridge_client.login(phone_number))

    def list_bridges_by_owner(self, matrix_username):
        return self.bridge_registry.list_bridges_by_owner(matrix_username)

    def whatsapp_register_user(self, matrix_username):
        """
        Register a user with the whatsapp bridge

        Args:
            matrix_username (_type_): _description_
        """
        asyncio.run(self.whatsapp_client.register(matrix_username))

    def whatsapp_login_user(self, matrix_username, phone_number):
        """
        Create a login request with the whatsapp bridge for the matrix user. Phone number must of in international format.

        Args:
            matrix_username (_type_): _description_
            phone_number (_type_): _description_
        """
        whatsapp_login_code = asyncio.run(
            self.whatsapp_client.login(
                mx_username=matrix_username, phone_number=phone_number
            )
        )

        return whatsapp_login_code
