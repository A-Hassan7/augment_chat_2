from bridge_manager.interface import BridgeManagerInterface
from bridge_manager.database.models import Bridges
from .database.models import User


class UserBridgeManager:

    def __init__(self):
        self.bridge_manager = BridgeManagerInterface()

    def create_bridge(self, user: User, service):

        bridge_model = self.bridge_manager.create_bridge(
            matrix_username=user.matrix_username, service=service
        )
        return bridge_model

    def list_bridges(self, user: User):
        return self.bridge_manager.list_bridges_by_owner(user.matrix_username)

    def login(self, user: User, bridge: Bridges, phone_number: str):

        if not bridge.owner_matrix_username == user.matrix_username:
            raise ValueError("User must be the owner of the bridge")

        self.bridge_manager.login(bridge=bridge, phone_number=phone_number)

    def get_bridge_status(self, user, bridge):
        pass

