# Login user to whatsapp
# create a chat with the whatsapp bot if one doesn't exist already
# make sure I can track the whatsapp management rooms
# send login message
# read response text
# test and maintain status of connections
# should be able to support multiple whatsapp bridges

import random
import time
import re

from bridge_manager.database.models import Bridges
from bridge_manager.database.repositories import (
    BridgesRepository,
    # BridgeUserRegistrationsRepository,
)
from .errors import (
    NoBridgesFound,
    BridgeUserRegistrationAlreadyExists,
    NoBridgeUserRegistrationFound,
    UserAlreadyLoggedIn,
    LoginFailed,
)
from matrix_service.interface import MatrixServiceInterface
from bridge_manager.config import BridgeManagerConfig


class BaseBridgeClient:

    def __init__(self, bridge_model: Bridges):
        pass


class WhatsappBridgeClient(BaseBridgeClient):

    SERVICE_NAME = "whatsapp"
    BOT_MESSAGE_PREFIX = "!wa"

    def __init__(self, bridge_model: Bridges):
        super().__init__(bridge_model=bridge_model)

        if not bridge_model.bridge_service == self.SERVICE_NAME:
            raise ValueError(
                f"Bridge service mismatch: expected '{self.SERVICE_NAME}', "
                f"got '{bridge_model.bridge_service}'"
            )

        self.bridge = bridge_model

        self.matrix_service = MatrixServiceInterface()
        self.bridges_repository = BridgesRepository()

        # raise error if no bridge is found
        # if not self.bridges:
        #     raise NoBridgesFound(
        #         f"No bridge bots found for service {self.SERVICE_NAME}"
        #     )

    async def register(self):
        """
        Register the matrix user to the bridge service.

        Registering with the whatsapp bridge assignes a bridge instance to the matrix user
        and creates a bridge management room for the user to communicate with the bridge bot.

        Args:
            mx_username (_type_): _description_
        """

        if self.bridge.bridge_management_room_id:
            raise BridgeUserRegistrationAlreadyExists(
                f"Bridge management room already exists for user {self.bridge.owner_matrix_username}"
            )

        room_id = await self.matrix_service.create_room(
            username=self.bridge.owner_matrix_username,
            room_name=self.bridge.matrix_bot_username,
            is_direct=True,
            invite_usernames=[self.bridge.matrix_bot_username],
        )

        self.bridges_repository.update(
            self.bridge.id, bridge_management_room_id=room_id
        )

    async def login(self, phone_number: str) -> str:
        """
        Create a login request with the whatsapp bridge service for the matrix user.

        The current login method relies on sending the bot a message through the bridge management room
        setup. The login request is sent with the user's full international phone number. The message looks something like
        "!wa login +4413412341234". It uses the users international phone number to send a whatsapp login request. A code is
        given by the whatsapp bridge bot, this code needs to be entered into the whatsapp login request.

        Args:
            mx_username (str): matrix username
            phone_number (str): user's full international phone number

        Returns:
            str: login code
        """

        # check if the user is already logged in
        if await self.is_user_logged_in():
            raise UserAlreadyLoggedIn(
                f"user {self.bridge_model.owner_matrix_username} is already logged into the {self.SERVICE_NAME}"
            )

        # send login message
        message_event_id = await self.message_bot(
            message_body=f"login phone {phone_number}",
        )

        # wait for 1 second to give the bridge bot to respond to the message
        time.sleep(5)

        # get response
        message_responses = self.get_response_to_message(event_id=message_event_id)

        # Regex to match codes like 98HG-9QC3 (alphanumeric, 4 chars, dash, 4 chars)
        login_code_pattern = "`([A-Z0-9]{4}-[A-Z0-9]{4})`"

        for response in message_responses:
            # Scan the code below or enter the following code on your phone to log in: **98HG-9QC3**
            # responses come back with '*' around the code, so I need to remove them first
            match = re.match(login_code_pattern, response.message_body.replace("*", ""))
            if match:
                return match.group(1)

        # if no login code is returned then there's probably an issue with the phone number
        # throw error with messages returned
        response_message_bodies = [
            response.message_body for response in message_responses
        ]
        raise LoginFailed(
            f"Login failed for user {self.bridge.owner_matrix_username} with phone number {phone_number}. "
            "The following messages were returned from the whatsapp bot: "
            f"{response_message_bodies}"
        )

    async def message_bot(self, message_body: str) -> str:
        """
        Send a message to the whatsapp bot for the matrix user using the registrations in the
        bridge manager database.

        Args:
            mx_username (str): matrix user
            message_body (str): message body
        """
        # append the bot message prefix to the message body
        message_body = f"{self.BOT_MESSAGE_PREFIX} {message_body}"

        # send message to bridge management room using the MatrixClient
        event_id = await self.matrix_service.send_message(
            username=self.bridge.owner_matrix_username,
            room_id=self.bridge.bridge_management_room_id,
            message_body=message_body,
        )

        return event_id

    def get_response_to_message(self, event_id: str):
        """
        Get messages in the bridge management room after a certain event_id. This helps get
        responses to messages sent to the bridge bot.

        Args:
            mx_username (str): _description_
            event_id (str): _description_
        """

        # get messages from the matrix client that were made after the given event_id
        response_messages = self.matrix_service.get_messages(
            matrix_username=self.bridge.owner_matrix_username,
            room_id=self.bridge.bridge_management_room_id,
            after_event_id=event_id,
        )

        return response_messages

    async def is_user_logged_in(self) -> bool:
        # get the current status of the connection to whatsapp through the bridge bot

        message_event_id = await self.message_bot(message_body="list-logins")

        # wait for 1 second to give the bridge bot to respond to the message
        time.sleep(2)

        response_messages = self.get_response_to_message(event_id=message_event_id)

        response = response_messages[0]
        response = response.message_body

        pattern = r"Logged in as \+[0-9]+ \(device #[0-9]+\), connection to WhatsApp OK \(probably\)"
        return bool(re.match(pattern, response))
