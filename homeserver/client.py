"""
Homeserver Client - Simplified Matrix client for homeserver operations.

Handles:
- User registration
- User login (with password reset)
- Room creation
- Message sending
- Direct database access for password management

Input Format Standards:
- Usernames: Accept with or without '@' prefix, WITHOUT domain (e.g., "alice" or "@alice")
- User IDs: ALWAYS full Matrix IDs internally (@username:homeserver.com)
- Room IDs: ALWAYS full Room IDs internally (!roomid:homeserver.com)
- Methods normalize inputs automatically
"""

import secrets
import logging
from typing import Optional, List, Dict, Any

import bcrypt
from nio import (
    AsyncClient,
    RegisterResponse,
    LoginResponse,
    RoomSendResponse,
    RoomCreateResponse,
    RoomInviteResponse,
)
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)


class HomeserverClientError(Exception):
    """Base exception for homeserver client errors."""

    pass


class RegistrationError(HomeserverClientError):
    """Raised when user registration fails."""

    pass


class LoginError(HomeserverClientError):
    """Raised when user login fails."""

    pass


class RoomCreationError(HomeserverClientError):
    """Raised when room creation fails."""

    pass


class MessageSendError(HomeserverClientError):
    """Raised when message sending fails."""

    pass


class HomeserverClient:
    """
    Client for interacting with Matrix Synapse homeserver.

    Provides methods for:
    - User management (register, login)
    - Room operations (create, invite)
    - Messaging (send text messages)

    Uses direct database access for password management (following Synapse's bcrypt approach).
    """

    def __init__(
        self,
        homeserver_url: str,
        homeserver_name: str,
        database_url: str,
    ):
        """
        Initialize homeserver client.

        Args:
            homeserver_url: Full URL to homeserver (e.g., "http://localhost:8008")
            homeserver_name: Domain name of homeserver (e.g., "matrix.example.com")
            database_url: PostgreSQL connection string for Synapse database
        """
        self.homeserver_url = homeserver_url
        self.homeserver_name = homeserver_name
        self.database_url = database_url

        # Create database engine for direct access
        self.db_engine = create_engine(database_url)
        self.SessionLocal = sessionmaker(bind=self.db_engine)

    async def register_user(self, username: str) -> Dict[str, str]:
        """
        Register a new user on the homeserver.

        Creates user with random password. Password is returned but not stored.
        To login later, use login() which will reset the password.

        Args:
            username: Username (without @ or domain)

        Returns:
            Dict with user_id and password

        Raises:
            RegistrationError: If registration fails
        """
        # Generate random password
        password = secrets.token_urlsafe(16)

        # Create client for registration
        client = self._create_client()

        try:
            response = await client.register(username=username, password=password)

            if not isinstance(response, RegisterResponse):
                error_msg = f"Registration failed for {username}: {response}"
                logger.error(error_msg)
                raise RegistrationError(error_msg)

            user_id = response.user_id
            logger.info(f"Successfully registered user: {user_id}")

            return {
                "user_id": user_id,
                "password": password,
            }

        finally:
            await client.close()

    async def login(self, username: str) -> Dict[str, str]:
        """
        Login user and return access token.

        Resets password directly in database (since passwords aren't stored).

        Args:
            username: Username (without @ or domain)

        Returns:
            Dict with user_id, access_token, and device_id

        Raises:
            LoginError: If login fails
        """
        # Generate new password
        password = secrets.token_urlsafe(16)

        # Reset password in database
        user_id = self._make_user_id(username)
        self._reset_password(user_id, password)

        # Create client and login
        client = self._create_client(username)

        try:
            response = await client.login(password)

            if not isinstance(response, LoginResponse):
                error_msg = f"Login failed for {username}: {response}"
                logger.error(error_msg)
                raise LoginError(error_msg)

            logger.info(f"Successfully logged in: {user_id}")

            return {
                "user_id": response.user_id,
                "access_token": response.access_token,
                "device_id": response.device_id,
            }

        finally:
            await client.close()

    async def create_room(
        self,
        username: str,
        access_token: str,
        name: Optional[str] = None,
        is_direct: bool = False,
        invite: Optional[List[str]] = None,
        initial_state: Optional[List[Dict]] = None,
    ) -> str:
        """
        Create a Matrix room.

        Args:
            username: Username creating the room
            access_token: User's access token
            name: Room name
            is_direct: Whether this is a direct message room
            invite: List of user IDs to invite
            initial_state: Initial state events for room

        Returns:
            Room ID (without homeserver domain)

        Raises:
            RoomCreationError: If room creation fails
        """
        client = self._create_client(username)
        client.access_token = access_token

        try:
            # Convert invite usernames to full IDs if needed
            invite_ids = None
            if invite:
                invite_ids = [
                    self._make_user_id(u) if not u.startswith("@") else u
                    for u in invite
                ]

            response = await client.room_create(
                name=name,
                is_direct=is_direct,
                invite=invite_ids,
                initial_state=initial_state,
            )

            if not isinstance(response, RoomCreateResponse):
                error_msg = f"Room creation failed: {response}"
                logger.error(error_msg)
                raise RoomCreationError(error_msg)

            # Extract room ID without homeserver domain
            room_id = response.room_id.split(":")[0]
            logger.info(f"Created room: {room_id}")

            return room_id

        finally:
            await client.close()

    async def send_message(
        self,
        username: str,
        access_token: str,
        room_id: str,
        message: str,
        msgtype: str = "m.text",
    ) -> str:
        """
        Send a text message to a room.

        Args:
            username: Username sending the message
            access_token: User's access token
            room_id: Room ID (with or without homeserver domain)
            message: Message text
            msgtype: Message type (default: m.text)

        Returns:
            Event ID of sent message

        Raises:
            MessageSendError: If message sending fails
        """
        client = self._create_client(username)
        client.access_token = access_token

        try:
            # Ensure room_id includes homeserver domain
            if ":" not in room_id:
                room_id = f"{room_id}:{self.homeserver_name}"

            response = await client.room_send(
                room_id=room_id,
                message_type="m.room.message",
                content={"msgtype": msgtype, "body": message},
            )

            if not isinstance(response, RoomSendResponse):
                error_msg = f"Message send failed: {response}"
                logger.error(error_msg)
                raise MessageSendError(error_msg)

            logger.debug(f"Sent message to {room_id}: {response.event_id}")
            return response.event_id

        finally:
            await client.close()

    async def invite_to_room(
        self,
        username: str,
        access_token: str,
        room_id: str,
        user_id: str,
    ) -> bool:
        """
        Invite a user to a room.

        Args:
            username: Username doing the inviting
            access_token: User's access token
            room_id: Room ID
            user_id: User ID to invite

        Returns:
            True if successful
        """
        client = self._create_client(username)
        client.access_token = access_token

        try:
            # Ensure room_id includes homeserver domain
            if ":" not in room_id:
                room_id = f"{room_id}:{self.homeserver_name}"

            # Ensure user_id is full Matrix ID
            if not user_id.startswith("@"):
                user_id = self._make_user_id(user_id)

            response = await client.room_invite(room_id, user_id)

            if not isinstance(response, RoomInviteResponse):
                logger.error(f"Invite failed: {response}")
                return False

            logger.info(f"Invited {user_id} to {room_id}")
            return True

        finally:
            await client.close()

    def get_access_token(self, username: str) -> Optional[str]:
        """
        Get user's access token from database.

        Args:
            username: Username (without @ or domain)

        Returns:
            Access token if found, None otherwise
        """
        user_id = self._make_user_id(username)

        with self.SessionLocal() as session:
            result = session.execute(
                text(
                    "SELECT token FROM access_tokens WHERE user_id = :user_id LIMIT 1"
                ),
                {"user_id": user_id},
            ).fetchone()

            if result:
                return result[0]
            return None

    def is_user_registered(self, username: str) -> bool:
        """
        Check if user exists in database.

        Args:
            username: Username (without @ or domain)

        Returns:
            True if user exists
        """
        user_id = self._make_user_id(username)

        with self.SessionLocal() as session:
            result = session.execute(
                text("SELECT 1 FROM users WHERE name = :user_id LIMIT 1"),
                {"user_id": user_id},
            ).fetchone()

            return result is not None

    def _create_client_for_user(self, localpart: str) -> AsyncClient:
        """
        Create AsyncClient instance for a specific user.

        Args:
            localpart: Local username part (no @ or domain), e.g., "alice"

        Returns:
            Configured AsyncClient with user set
        """
        return AsyncClient(
            homeserver=self.homeserver_url,
            user=localpart,  # nio accepts localpart and constructs full ID
            device_id="bridge_manager_client",
        )

    def _extract_localpart(self, username: str) -> str:
        """
        Extract local username from various input formats.

        Accepts:
        - "alice" → "alice"
        - "@alice" → "alice"
        - "@alice:server.com" → "alice"

        Args:
            username: Username in any format

        Returns:
            Local part only (no @ or domain)
        """
        # Already just localpart
        if not username.startswith("@") and ":" not in username:
            return username

        # Has @ prefix
        if username.startswith("@"):
            # Extract localpart from full ID: @alice:server.com → alice
            if ":" in username:
                return username[1:].split(":")[0]
            # Just @alice → alice
            return username[1:]

        # Shouldn't happen, but return as-is
        return username

    def _to_full_user_id(self, username: str) -> str:
        """
        Convert username to full Matrix user ID.

        Accepts:
        - "alice" → "@alice:homeserver.com"
        - "@alice" → "@alice:homeserver.com"
        - "@alice:homeserver.com" → "@alice:homeserver.com" (unchanged)

        Args:
            username: Username in any format

        Returns:
            Full user ID: @username:homeserver.name
        """
        # Already a full user ID
        if self._is_full_user_id(username):
            return username

        # Get localpart and construct full ID
        localpart = self._extract_localpart(username)
        return f"@{localpart}:{self.homeserver_name}"

    def _is_full_user_id(self, user_id: str) -> bool:
        """
        Check if string is a full Matrix user ID.

        Args:
            user_id: String to check

        Returns:
            True if format is @username:homeserver.name
        """
        return user_id.startswith("@") and ":" in user_id

    def _to_full_room_id(self, room_id: str) -> str:
        """
        Convert room ID to full format.

        Accepts:
        - "!abc123" → "!abc123:homeserver.com"
        - "!abc123:homeserver.com" → "!abc123:homeserver.com" (unchanged)

        Args:
            room_id: Room ID with or without domain

        Returns:
            Full room ID: !roomid:homeserver.com
        """
        # Already has domain
        if ":" in room_id:
            return room_id

        # Add domain
        return f"{room_id}:{self.homeserver_name}"

    def _reset_password(self, user_id: str, password: str):
        """
        Reset user password by updating password hash in database.

        Uses bcrypt hashing as required by Synapse.

        Args:
            user_id: Full Matrix user ID
            password: New password
        """
        password_hash = self._hash_password(password)

        with self.SessionLocal() as session:
            session.execute(
                text(
                    "UPDATE users SET password_hash = :password_hash WHERE name = :user_id"
                ),
                {"password_hash": password_hash, "user_id": user_id},
            )
            session.commit()

        logger.debug(f"Reset password for {user_id}")

    def _hash_password(self, password: str) -> str:
        """
        Hash password using bcrypt (Synapse's method).

        Args:
            password: Plain text password

        Returns:
            Bcrypt hash
        """
        password_bytes = password.encode("utf-8")
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password_bytes, salt).decode("utf-8")
