# Create a user
# login to the user account and generate access token if one doesn't already exist
# send a message to a room (make sure that room exists)

import secrets

import bcrypt
from nio import (
    AsyncClient,
    RegisterResponse,
    LoginResponse,
    RoomSendResponse,
    RoomCreateResponse,
)

from logger import Logger
from .config import MatrixConfig
from .users import MatrixUser
from .errors import (
    RegistrationError,
    UserNotRegisteredError,
    LoginError,
    MessageSendError,
    RoomCreateError,
    AuthorizationError,
    EventNotFound,
)
from matrix_service.database.repositories import (
    UsersRepository,
    LocalCurrentMembershipRepository,
    EventsRepository,
)


class MatrixClient:

    def __init__(self):

        self.config = MatrixConfig

        logger_instance = Logger(file="./logs.matrix.txt")
        self.logger = logger_instance.get_logger(self.__class__.__name__)

    async def register_user(self, username: str) -> MatrixUser:
        """
        Register a user on the matrix server using the username provided.
        A random password is used to register the user and is not cached. In order to login to the account in future, the password will be reset.

        Args:
            username (str): username to register the user as. Do not include the matrix domain (like matrix.example.me)

        Returns:
            User | None: Returns a User object if successful, otherwise returns None
        """

        # create a random password that doesn't get cached
        random_password = secrets.token_urlsafe(12)

        # create request to matrix server
        client = self._create_client()
        res = await client.register(username=username, password=random_password)

        # catch error
        if not isinstance(res, RegisterResponse):
            message = f"Registration failed for user {username}. Error: {res}"
            self.logger.critical(message)
            raise RegistrationError(message)

        self.logger.info(f"User {username} successfully registered")

        self.logger.info(f"password: {random_password}")

        return MatrixUser(username, password=random_password)

    async def login(self, username: str) -> MatrixUser:
        """
        Login the user. Since passwords are not cached at registration, this method will reset the password in order to login.

        Args:
            user_id (str): _description_

        Returns:
            User: _description_
        """

        # check the user exists
        if not self._is_user_registered(username):
            message = f"User {username} is not yet registered"
            self.logger.error(message)
            raise UserNotRegisteredError(message)

        # reset the password
        random_password = secrets.token_urlsafe(12)
        self._reset_user_password(username, random_password)

        # login
        # creating a client using the username of the user is required because
        # the AsyncClient.login function doesn't accept a username as an argument
        # therefore, I'm creating a new instance of the AyncClient for the user specifically
        client = self._create_client(username=username)
        res = await client.login(random_password)

        if not isinstance(res, LoginResponse):
            message = f"Login failed for user {username}. Error: {res}"
            self.logger.error(message)
            raise LoginError(message)

        return MatrixUser(username)

    async def send_message(self, username: str, room_id: str, message_body: str) -> str:
        """
        Sends a text message to a room from the given user

        Args:
            username (str): _description_
            room_id (str): _description_
            message_body (_type_): _description_

        Returns:
            event_id (str): event_id of the sent message
        """
        # check the user exists
        if not self._is_user_registered(username):
            message = f"User {username} is not yet registered"
            self.logger.error(message)
            raise UserNotRegisteredError(message)

        user = self.get_user(username)

        # if no access token exists then login the user
        # this will generate an access token
        if not user.access_token:
            self.login(username)

        client = self._create_client(username=username)
        client.access_token = user.access_token

        # create full matrix room id including the homserver name
        room_id = f"{room_id}:{self.config.MATRIX_HOMESERVER_NAME}"

        res = await client.room_send(
            room_id=room_id,
            message_type="m.room.message",
            content={"msgtype": "m.text", "body": message_body},
        )

        if not isinstance(res, RoomSendResponse):
            message = f"Message failed to send for user {username}: Error: {res}"
            self.logger.error(message)
            raise MessageSendError(message)

        return res.event_id

    def get_messages(
        self,
        mx_username: str,
        room_id: str,
        after_event_id: str = None,
        limit: int = 10,
    ):
        # TODO:
        # I need to get messages from a room after a certain event id. The synapse api doesn't support this
        # therefore, I'll use the AsyncClient.room_messages function to get a list of the last 10 messages
        # then filter those messages to messages after the after_event_id provided
        # OR I could just read them from the database and save myself the hassle
        # the only comfort with using the API is the permissions checking that would come with the API
        # i.e. I don't want to receive messages from a room that the matrix user doesn't have access to
        # I can easily check this myself though.
        # API OR Database? I like the database for simplicity.
        full_room_id = f"{room_id}:{self.config.MATRIX_HOMESERVER_NAME}"

        # check the user is a participent in the room
        local_current_membership_repository = LocalCurrentMembershipRepository()
        # BUG: returns duplicated rows and doesn't have distinct user_ids
        room_memberships = local_current_membership_repository.get_by_room_id(
            full_room_id
        )
        registered_members = [
            membership.user_id.split(":")[0].replace("@", "")
            for membership in room_memberships
        ]
        if not mx_username in registered_members:
            raise AuthorizationError(
                f"User {mx_username} is not a registered member of this room {room_id}"
            )

        # get all messages from the room that are after the event id provided
        events_repository = EventsRepository()
        messages = events_repository.get_messages_by_room_id(full_room_id, limit=limit)

        if after_event_id:
            # get the timestamp of the after_event_id and filter messages to events after that timestamp
            event = events_repository.get_by_event_id(after_event_id)
            if not event:
                raise EventNotFound(
                    f"Event with event_id {after_event_id} not found within the last {limit} messages in this room {room_id}"
                )

            after_received_timestamp = event.received_ts
            return [
                message
                for message in messages
                if message.received_ts > after_received_timestamp
            ]

        return messages

    async def create_room(
        self, username: str, room_name: str, is_direct: bool, invite_usernames: list
    ) -> str:
        """_summary_

        Args:
            username (str): _description_
            name (str): _description_
            is_direct (bool): _description_
            invite_user_ids (list): _description_

        Returns:
            str: _description_
        """

        if not self._is_user_registered(username):
            raise UserNotRegisteredError(
                f"User {username} is not registered with the matrix server"
            )

        # check invite users are registered
        if invite_usernames:
            for user in invite_usernames:
                if not self._is_user_registered(user):
                    raise UserNotRegisteredError(
                        f"Invited user {user} is not registered"
                    )

        # create client and add access token
        client = self._create_client(username)
        user = self.get_user(username)
        client.access_token = user.access_token

        # get full user ids for the invite usernames
        invite_user_ids = [self._create_full_user_id(user) for user in invite_usernames]

        res = await client.room_create(
            name=room_name, is_direct=is_direct, invite=invite_user_ids
        )

        if not isinstance(res, RoomCreateResponse):
            message = (
                f"Failed to create room {room_name} for user {username}. Error: {res}"
            )
            self.logger.error(message)
            raise RoomCreateError(message)

        # remove the matrix homserver name from the room
        # <room_id>:<homeserver name>
        room_id = res.room_id
        room_id = room_id.split(":")[0]

        return room_id

    def get_user(self, username: str) -> MatrixUser:
        """
        Return instance of User.

        Args:
            username (str): username

        Returns:
            User:
        """
        return MatrixUser(self._create_full_user_id(username))

    def _create_client(self, username: str = "") -> AsyncClient:
        """
        Return an instance of an AsyncClient.

        Returns:
            AsyncClient: Matrix nio async client
        """
        return AsyncClient(
            homeserver=self.config.MATRIX_HOMESERVER_URL,
            device_id="matrix_client",
            user=self._create_full_user_id(username),
        )

    def _reset_user_password(self, username, password):
        """
        Reset user password by changing the password hash in the users table.

        Args:
            username (str): username
            password (str): password string
        """
        password_hash = self._generate_password_hash(password)
        user_id = self._create_full_user_id(username)

        user_repository = UsersRepository()
        user_repository.update_password(user_id, password_hash)

    def _is_user_registered(self, username: str) -> bool:
        """
        Check if a user is registered on the matrix server.

        Args:
            user_id (str): _description_

        Returns:
            bool: Returns True if exists and False if not
        """
        users_repository = UsersRepository()
        results = users_repository.get_by_user_id(self._create_full_user_id(username))
        return bool(results)

    def _create_full_user_id(self, username: str) -> str:
        """
        Create the full matrix user id including the matrix homeserver name

        Args:
            username (str): username
        """
        return f"@{username}:{self.config.MATRIX_HOMESERVER_NAME}"

    def _generate_password_hash(self, password: str) -> str:
        """
        Generate password using bcrypt as used in matrix synapse:
        https://manpages.debian.org/testing/matrix-synapse/hash_password.1.en.html

        Args:
            password (str): password string

        Returns:
            str: hashed password
        """

        password = password.encode("utf-8")
        salt = bcrypt.gensalt()

        return bcrypt.hashpw(password, salt).decode()
