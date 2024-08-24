import uuid
import asyncio

from matrix_service.interface import MatrixServiceInterface
from bridge_manager.interface import BridgeManagerInterface
from .database.models import User
from .database.repositories import UsersRepository
from .errors import MatrixUserRegistrationError


class UsersService:

    def __init__(self):
        self.users_repository = UsersRepository()
        self.matrix = MatrixServiceInterface()
        self.bridge_manager = BridgeManagerInterface()

    def register(self, username):
        user = User(username=username)
        self.users_repository.create(user)

    def register_with_matrix(self, user_id):
        """
        Register a user with the matrix server and add the matrix id to the users table.

        Args:
            user_id (_type_): _description_
        """

        # check if the user already has a matrix registration
        user = self.users_repository.get_by_user_id(user_id)
        if user.matrix_username:
            raise MatrixUserRegistrationError(
                f"Matrix registration for user_id {user_id} already exists"
            )

        # register with matrix service using random username
        random_username = str(uuid.uuid4())
        matrix_username = asyncio.run(self.matrix.register_user(random_username))

        # insert matrix user id into the users table
        self.users_repository.update(user_id, matrix_username=matrix_username)

    def create_whatsapp_bridge(self, user_id, phone_number):
        """
        Create a whatsapp bridge for the user so messages can be retrieved from the platform.
        The phone number needs to be in international format.

        Args:
            user_id (_type_): _description_
            phone_number (str): international phone number
        """

        user = self.users_repository.get_by_user_id(user_id)
        matrix_username = user.matrix_username

        # register with the whatsapp bridge
        # if the user is already registered then a login request will be created
        try:
            self.bridge_manager.whatsapp_register_user(matrix_username)
        except Exception as e:
            if e.__class__.__name__ == 'BridgeUserRegistrationAlreadyExists':
                pass
            else:
                print(e)

        # log into the whatsapp bridge
        login_code = self.bridge_manager.whatsapp_login_user(
            matrix_username, phone_number
        )

        return login_code
