import uuid
import asyncio

from matrix_service.interface import MatrixServiceInterface
from .database.models import User
from .database.repositories import UsersRepository
from .errors import MatrixUserRegistrationError


class UsersService:

    def __init__(self):
        self.users_repository = UsersRepository()
        self.matrix = MatrixServiceInterface()

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
