import uuid
import asyncio

from logger import Logger
from matrix_service.interface import MatrixServiceInterface
from .database.repositories import UsersRepository
from .database.models import User
from .errors import MatrixUserRegistrationError, UserAlreadyExistsError


class UserRegister:
    """
    Handles user registration for the augment chat application.
    Creates both application user and Matrix homeserver account.

    TODO: Manage deletions
    """

    def __init__(self):
        self.users_repo = UsersRepository()
        self.matrix = MatrixServiceInterface()

        logger_instance = Logger()
        self.logger = logger_instance.get_logger(name=__class__.__name__)

    def register(self, username: str):
        """
        Create user in augment chat and Matrix homeserver.

        Args:
            username: Unique username for the application

        Returns:
            User object with matrix credentials

        Raises:
            UserAlreadyExistsError: If username already exists
            MatrixUserRegistrationError: If Matrix account creation fails
        """
        self.logger.info(f"Registering user: {username}")

        # Check for existing user
        existing_user = self.users_repo.get_by_username(username)
        if existing_user:
            raise UserAlreadyExistsError(f"Username '{username}' already exists")

        # Create application user
        user_obj = User(username=username)
        self.users_repo.create(user_obj)

        # Retrieve created user with ID
        user = self.users_repo.get_by_username(username)

        try:
            # Create Matrix account
            self._create_matrix_user(user_id=user.id)

            # Refresh to get Matrix credentials
            user = self.users_repo.get_by_user_id(user.id)

            self.logger.info(
                f"User registered successfully: {username} (ID: {user.id}, "
                f"Matrix: {user.matrix_username})"
            )

            return user

        except Exception as e:
            self.logger.error(f"Matrix registration failed for {username}: {str(e)}")
            # Matrix registration failed but user exists in DB
            raise MatrixUserRegistrationError(
                f"Failed to create Matrix account for user {username}: {str(e)}"
            )

    def _create_matrix_user(self, user_id: int):
        """
        Register a user with the Matrix homeserver and store credentials.

        Args:
            user_id: Application user ID

        Raises:
            MatrixUserRegistrationError: If user already has Matrix account
                or if Matrix registration fails
        """
        # Check if user already has Matrix account
        user = self.users_repo.get_by_user_id(user_id)
        if user.matrix_username:
            raise MatrixUserRegistrationError(
                f"Matrix registration for user_id {user_id} already exists: "
                f"{user.matrix_username}"
            )

        self.logger.info(f"Creating Matrix account for user_id {user_id}")

        # Generate unique Matrix username
        random_username = str(uuid.uuid4())

        try:
            # Register with Matrix homeserver
            matrix_user = asyncio.run(self.matrix.register_user(random_username))

            # Store Matrix credentials
            self.users_repo.update(
                user_id,
                matrix_username=matrix_user.user_id,
                matrix_password=matrix_user.password,
            )

            self.logger.info(
                f"Matrix account created for user_id {user_id}: "
                f"{matrix_user.user_id}"
            )

        except Exception as e:
            self.logger.error(
                f"Failed to register Matrix user for user_id {user_id}: {str(e)}"
            )
            raise

    def get_user_by_matrix_username(self, matrix_username: str):
        """
        Retrieve a user by their Matrix username.

        Args:
            matrix_username: The Matrix username to search for

        Returns:
            User object if found, None otherwise
        """
        return self.users_repo.get_by_matrix_username(matrix_username)
