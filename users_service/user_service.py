from .database.models import User
from .database.repositories import UsersRepository

class UsersService:
    
    def __init__(self):
        self.users_repository = UsersRepository()

    def register(self, username):
        user = User(username=username)
        self.users_repository.create(user)
