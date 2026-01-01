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

        pass

    # ============================================================
    # Onboarding
    # ============================================================

    def create_user(self, username):
        pass
