from datetime import datetime, UTC
from abc import ABC, abstractmethod

from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, and_, insert

from .models import BridgeBots, BridgeUserRegistrations, Base
from .engine import DatabaseEngine

Base.metadata.create_all(DatabaseEngine())


class BaseRepository(ABC):

    def __init__(self):
        self.Session = sessionmaker(bind=DatabaseEngine())

    @abstractmethod
    def get_all(self):
        pass


class BridgeBotsRepository(BaseRepository):

    model = BridgeBots

    def get_all(self):
        with self.Session() as session:
            statement = select(self.model)
            return session.execute(statement).scalars().all()

    def get_by_bridge_service(self, bridge_service: str):
        with self.Session() as session:
            statement = select(self.model).where(
                self.model.bridge_service == bridge_service
            )
            return session.execute(statement).scalars().all()


class BridgeUserRegistrationsRepository(BaseRepository):

    model = BridgeUserRegistrations

    def get_all(self):
        with self.Session() as session:
            statement = select(self.model)
            return session.execute(statement).scalars().all()

    def get_by_matrix_username_and_bot_ids(self, matrix_username: str, bot_ids: list):
        with self.Session() as session:
            statement = select(self.model).where(
                and_(
                    self.model.matrix_username == matrix_username,
                    self.model.bridge_bot_id.in_(bot_ids),
                )
            )
            # return a single scalar value and raise error if more than results are found
            # importantly scalar doesn't raise an error if no results are found
            return session.execute(statement).scalar()

    def create(self, bridge_bot_id, matrix_username, bridge_management_room_id):
        with self.Session() as session:
            statement = insert(self.model).values(
                bridge_bot_id=bridge_bot_id,
                matrix_username=matrix_username,
                bridge_management_room_id=bridge_management_room_id,
                created_at=datetime.now(UTC),
            )
            session.execute(statement)
            session.commit()
