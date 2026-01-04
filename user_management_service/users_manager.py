from .database.models import User
from .register import UserRegister
from .bridge_manager import UserBridgeManager


class UsersManager:
    """
    Centralize user management and orchestration.
    Handles everything the user needs from registration, managing bridges, generating suggestions, deleting messages/rooms etc.

    Responsibilities
    ---

    Onboarding:
    - Create augment chat user
    - Create matrix user
    - Create requested bridge and provide status updates (creating rooms, backfilling rooms)

    Messages management:
    - message processing with access controls for certain rooms (blacklist to disable syncing of certain rooms)
    - backfill rooms that have been enabled
    - Most recent rooms

    Bridge management:
    - Get list of associated bridges
    - Get bridge statuses

    Augmentation Management:
    - create suggestions
    - custom prompts

    Delete user:
    - delete all bridges
    - delete all messages and rooms on matrix
    - delete matrix user
    - delete all transcripts and suggestions in the augment chat database

    GDPR:
    - export all user data

    Audit Trail:
    - keep an audit trail of the all the actions being taken for the user.
    - This also provides the ability to give status updates

    """

    def __init__(self):
        self.user_register = UserRegister()
        self.user_bridge_manager = UserBridgeManager()

        pass

    # ============================================================
    # Onboarding
    #
    # 1. Augment chat and matrix user
    # 2. Register a bridge
    # ============================================================
    def create_user(self, username):
        return self.user_register.register(username)

    def register_bridge(self, user: User, service):
        bridge = self.user_bridge_manager.create_bridge(user, service)
        login_code = self.user_bridge_manager.login(user, bridge)

    def list_bridges(self, user: User, service):
        return self.user_bridge_manager.list_bridges(user)
