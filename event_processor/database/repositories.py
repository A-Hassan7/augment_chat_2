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
