from bridge_manager.interface import BridgeManagerInterface


class UserBridgeManager:

    def __init__(self):
        self.bridge_manager = BridgeManagerInterface()

    def create_bridge(self, matrix_username, service):

        bridge_model = self.bridge_manager.create_bridge(
            matrix_username=matrix_username, service=service
        )

        return bridge_model
