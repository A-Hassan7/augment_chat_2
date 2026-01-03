from abc import ABC, abstractmethod

from sqlalchemy import select, update, text
from sqlalchemy.orm import sessionmaker

from .models import Base, User
from .engine import DatabaseEngine

Base.metadata.create_all(bind=DatabaseEngine())


class BaseRepository(ABC):

    def __init__(self):
        self.Session = sessionmaker(bind=DatabaseEngine())

    def get_all(self):
        with self.Session() as session:
            statement = select(self.model)
            return session.execute(statement).scalars().all()

    @abstractmethod
    def get_by_user_id(self):
        pass

    @abstractmethod
    def create(self):
        pass


class UsersRepository(BaseRepository):

    model = User

    def get_by_user_id(self, user_id: str):
        with self.Session() as session:
            statement = select(self.model).where(self.model.id == user_id)
            return session.execute(statement).scalar()

    def get_by_username(self, username: str):
        with self.Session() as session:
            statement = select(self.model).where(self.model.username == username)
            return session.execute(statement).scalar()

    def get_by_matrix_username(self, matrix_username: str):
        with self.Session() as session:
            statement = select(self.model).where(
                self.model.matrix_username == matrix_username
            )
            return session.execute(statement).scalar()

    def create(self, user: User):
        with self.Session() as session:
            session.add(user)
            session.commit()

    def update(self, user_id, **kwargs):
        """
        Update values in the for a specific user_id

        Args:
            user_id (int): _description_
        """

        with self.Session() as session:
            statement = (
                update(self.model).where(self.model.id == user_id).values(**kwargs)
            )
            session.execute(statement)
            session.commit()
