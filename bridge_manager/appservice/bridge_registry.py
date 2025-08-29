from ..config import BridgeManagerConfig
from ..database.repositories import BridgeBotsRepository
from .bridge_service import WhatsappBridgeService


class BridgeRegistry:

    def __init__(self, bridge_manager_config: BridgeManagerConfig):
        self.bridge_manager_config = bridge_manager_config
        self.bridge_bots_repository = BridgeBotsRepository()

    def get_bridge(self, as_token: str = None, bridge_id: str = None):
        bridge_bot = None

        if as_token:
            bridge_bot = self.bridge_bots_repository.get_by_as_token(as_token)
        elif bridge_id:
            bridge_bot = self.bridge_bots_repository.get_by_id(bridge_id)
        else:
            return None

        if not bridge_bot:
            raise ValueError("Bridge bot not found.")

        if bridge_bot.bridge_service == "whatsapp":
            return WhatsappBridgeService(
                as_token=as_token or bridge_bot.as_token,
                bridge_manager_config=self.bridge_manager_config,
            )

        return None
