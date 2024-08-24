import asyncio

from .whatsapp_bridge_client import WhatsappBridgeClient

class BridgeManagerInterface:

    def __init__(self):
        self.whatsapp_client = WhatsappBridgeClient()

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
