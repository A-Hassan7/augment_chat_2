import asyncio

from .config import BridgeManagerConfig
from .orchestrator.orchestrator import BridgeOrchestrator
from .bridge_clients.whatsapp_bridge_client import WhatsappBridgeClient


class BridgeManagerInterface:

    def __init__(self):
        self.whatsapp_client = WhatsappBridgeClient()
        self.bridge_orchestrator = BridgeOrchestrator(BridgeManagerConfig())

    def create_bridge(self, matrix_username, service):

        bridge_model = self.bridge_orchestrator.create_bridge(
            bridge=service, owner_matrix_username=matrix_username
        )

        return bridge_model

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
