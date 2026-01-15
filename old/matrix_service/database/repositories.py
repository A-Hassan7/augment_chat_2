from abc import ABC, abstractmethod

from sqlalchemy import select, update, text
from sqlalchemy.orm import sessionmaker

from .models import AccessTokens, Users, LocalCurrentMembership, Events, EventJson
from .engine import MatrixDatabaseEngine


class BaseRepository(ABC):

    def __init__(self, model, session):
        pass

    @abstractmethod
    def get_all(self):
        pass

    @abstractmethod
    def get_by_user_id(self):
        pass


class AccessTokensRepository(BaseRepository):

    def __init__(self):
        self.model = AccessTokens
        self.Session = sessionmaker(bind=MatrixDatabaseEngine())

    def get_all(self):
        with self.Session() as session:
            statement = select(self.model)
            return session.execute(statement).scalars().all()

    def get_by_user_id(self, user_id: str):
        with self.Session() as session:
            statement = select(self.model).where(self.model.user_id == user_id)
            return session.execute(statement).scalars().all()


class UsersRepository(BaseRepository):

    def __init__(self):
        self.model = Users
        self.Session = sessionmaker(bind=MatrixDatabaseEngine())

    def get_all(self):
        with self.Session() as session:
            statement = select(self.model)
            return session.execute(statement).scalars().all()

    def get_by_user_id(self, user_id: str):
        with self.Session() as session:
            statement = select(self.model).where(self.model.name == user_id)
            return session.execute(statement).scalars().all()

    def update_password(self, user_id: str, password_hash: str):
        """
        Update the password has for a user

        Args:
            user_id (str): full matrix username including the homserver name
            password_hash (str): password hash encrypted using bcrypt
        """

        with self.Session() as session:
            statement = (
                update(self.model)
                .where(self.model.name == user_id)
                .values(password_hash=password_hash)
            )
            session.execute(statement)
            session.commit()


class LocalCurrentMembershipRepository(BaseRepository):

    def __init__(self):
        self.model = LocalCurrentMembership
        self.Session = sessionmaker(bind=MatrixDatabaseEngine())

    def get_all(self):
        with self.Session() as session:
            statement = select(self.model)
            return session.execute(statement).scalars().all()

    def get_by_room_id(self, room_id: str):
        with self.Session() as session:
            statement = select(self.model).where(self.model.room_id == room_id)
            return session.execute(statement).scalars().all()

    def get_by_user_id(self, user_id: str):
        with self.Session() as session:
            statement = select(self.model).where(self.model.user_id == user_id)
            return session.execute(statement).scalars().all()


class EventsRepository(BaseRepository):

    def __init__(self):
        self.model = Events
        self.Session = sessionmaker(bind=MatrixDatabaseEngine())

    def get_all(self):
        with self.Session() as session:
            statement = select(self.model)
            return session.execute(statement).scalars().all()

    def get_by_user_id(self, user_id: str):
        with self.Session() as session:
            statement = select(self.model).where(self.model.user_id == user_id)
            return session.execute(statement).scalars().all()

    def get_by_event_id(self, event_id: str):
        with self.Session() as session:
            statement = select(self.model).where(self.model.event_id == event_id)
            return session.execute(statement).scalar()

    def get_messages_by_room_id(self, room_id: str, limit: int = 10):
        with self.Session() as session:

            query = f"""
                select 
                    e.event_id,
                    e.type,
                    e.room_id,
                    sender,
                    received_ts,
                    j.json::jsonb -> 'content' ->> 'body' as message_body
                from events e
                left join event_json j
                    on e.event_id = j.event_id
                where 
                    e.type = 'm.room.message'
                    and e.room_id = '{room_id}'
                order by received_ts desc
                limit {limit}
            """
            return session.execute(text(query)).all()
