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

from .database.repositories import (
    BridgeBotsRepository,
    BridgeUserRegistrationsRepository,
)
from .errors import (
    NoBridgeBotsFound,
    BridgeUserRegistrationAlreadyExists,
    NoBridgeUserRegistrationFound,
    UserAlreadyLoggedIn,
    LoginFailed,
)
from matrix_service.interface import MatrixServiceInterface


class BaseBridgeClient:
    pass


class WhatsappBridgeClient:

    SERVICE_NAME = "whatsapp_bridge"
    BOT_MESSAGE_PREFIX = "!wa"

    def __init__(self):
        self.matrix_service = MatrixServiceInterface()

        # raise error if no bridge bots are found
        if not self.bridge_bots:
            raise NoBridgeBotsFound(
                f"No bridge bots found for service {self.SERVICE_NAME}"
            )

    async def register(self, mx_username: str):
        """
        Register the matrix user to the bridge service.

        Registering with the whatsapp bridge simply assignes a bridge instance to the matrix user
        and creates a bridge management room for the user to communicate with the bridge bot.

        Args:
            mx_username (_type_): _description_
        """

        # check if a registration already exists
        existing_registration = self.get_registration_details(mx_username)
        if existing_registration:
            raise BridgeUserRegistrationAlreadyExists(
                f"User {mx_username} is already registered with this bridge service {self.SERVICE_NAME}. "
                f"The registered bridge management room is {existing_registration.bridge_management_room_id}"
            )

        # get a bridge bot to register this user to
        allocated_bridge_bot = self._select_bridge_bot_to_register_new_user()

        # create room
        room_id = await self.matrix_service.create_room(
            username=mx_username,
            room_name="whatsapp_bridge_management_room",
            is_direct=True,
            invite_usernames=[allocated_bridge_bot.matrix_bot_username],
        )

        # create registration in the database manager databse using the room_id
        bridge_user_registration_repository = BridgeUserRegistrationsRepository()
        bridge_user_registration_repository.create(
            bridge_bot_id=allocated_bridge_bot.id,
            matrix_username=mx_username,
            bridge_management_room_id=room_id,
        )

    async def login(self, mx_username: str, phone_number: str) -> str:
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

        # register user with the bridge if it's not currently registered
        if not self.get_registration_details(mx_username):
            await self.register(mx_username)

        # check if the user is already logged in
        if await self.is_user_logged_in(mx_username):
            raise UserAlreadyLoggedIn(
                f"user {mx_username} is already logged into the {self.SERVICE_NAME}"
            )

        # send login message
        message_event_id = await self.message_bot(
            mx_username=mx_username, message_body=f"login {phone_number}"
        )

        # wait for 1 second to give the bridge bot to respond to the message
        time.sleep(1)

        # get response
        message_responses = self.get_response_to_message(
            mx_username=mx_username, event_id=message_event_id
        )

        login_code_pattern = "Scan the code below or enter the following code on your phone to log in: ([A-Za-z0-9]+-[A-Za-z0-9]+)"
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
            f"Login failed for user {mx_username} with phone number {phone_number}. "
            "The following messages were returned from the whatsapp bot: "
            f"{response_message_bodies}"
        )

    async def message_bot(self, mx_username: str, message_body: str) -> str:
        """
        Send a message to the whatsapp bot for the matrix user using the registrations in the
        bridge manager database.

        Args:
            mx_username (str): matrix user
            message_body (str): message body
        """
        # get the bridge room
        user_registration = self.get_registration_details(mx_username)
        if not user_registration:
            raise NoBridgeUserRegistrationFound(
                f"Found no bridge management room registration for user {mx_username} and bridge service {self.SERVICE_NAME}"
            )
        bridge_management_room_id = user_registration.bridge_management_room_id

        # append the bot message prefix to the message body
        message_body = f"{self.BOT_MESSAGE_PREFIX} {message_body}"

        # send message to bridge management room using the MatrixClient
        event_id = await self.matrix_service.send_message(
            username=mx_username,
            room_id=bridge_management_room_id,
            message_body=message_body,
        )

        return event_id

    def get_response_to_message(self, mx_username: str, event_id: str):
        """
        Get messages in the bridge management room after a certain event_id. This helps get
        responses to messages sent to the bridge bot.

        Args:
            mx_username (str): _description_
            event_id (str): _description_
        """

        # get bridge registration details
        registration_details = self.get_registration_details(mx_username)

        # get messages from the matrix client that were made after the given event_id
        response_messages = self.matrix_service.get_messages(
            matrix_username=mx_username,
            room_id=registration_details.bridge_management_room_id,
            after_event_id=event_id,
        )

        return response_messages

    def get_registration_details(self, mx_username: str):
        """
        Get registration details for the matrix user to the whatsapp bridge service.

        Args:
            mx_username (str): _description_
        """
        bridge_user_registrations_repository = BridgeUserRegistrationsRepository()

        bot_ids = [int(bot.id) for bot in self.bridge_bots]
        user_registration = (
            bridge_user_registrations_repository.get_by_matrix_username_and_bot_ids(
                matrix_username=mx_username, bot_ids=bot_ids
            )
        )

        if not user_registration:
            return

        return user_registration

    @property
    def bridge_bots(self):
        """
        Get a list of bridge bots registered with the bridge manager for this service
        """

        bridge_bots_repository = BridgeBotsRepository()
        bridge_bots = bridge_bots_repository.get_by_bridge_service(self.SERVICE_NAME)

        return bridge_bots

    def _select_bridge_bot_to_register_new_user(self):
        """
        Select a bridge bot to allocate a new user to. In future this may be based on an allocation
        strategy that distributes the load between multiple bots evenly

        This will need to create a new bridge bot for each new user.
        """
        return random.choice(self.bridge_bots)

    async def is_user_logged_in(self, mx_username) -> bool:
        # get the current status of the connection to whatsapp through the bridge bot

        message_event_id = await self.message_bot(
            mx_username=mx_username, message_body="ping"
        )

        # wait for 1 second to give the bridge bot to respond to the message
        time.sleep(1)

        response_messages = self.get_response_to_message(
            mx_username=mx_username, event_id=message_event_id
        )

        response = response_messages[0]
        response = response.message_body

        pattern = r"Logged in as \+[0-9]+ \(device #[0-9]+\), connection to WhatsApp OK \(probably\)"
        return bool(re.match(pattern, response))
