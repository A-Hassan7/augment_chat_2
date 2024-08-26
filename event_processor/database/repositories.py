from abc import ABC, abstractmethod

from sqlalchemy import select, update, text
from sqlalchemy.orm import sessionmaker

from .models import Base, ParsedMessage, ProcessedEvent
from .engine import DatabaseEngine

Base.metadata.create_all(bind=DatabaseEngine())


class BaseRepository(ABC):

    def __init__(self):
        self.Session = sessionmaker(bind=DatabaseEngine())

    def get_all(self):
        with self.Session() as session:
            statement = select(self.model)
            return session.execute(statement).scalars().all()


class ParsedMessagesRepository(BaseRepository):

    model = ParsedMessage

    def get_by_room_id(self, room_id: str):
        with self.Session() as session:
            statement = select(self.model).where(self.model.room_id == room_id)
            return session.execute(statement).scalars().all()

    def create(self, parsed_message: ParsedMessage):
        with self.Session() as session:
            session.add(parsed_message)
            session.commit()


class ProcessedEventsRepository(BaseRepository):

    model = ProcessedEvent

    def get_by_event_id(self, event_id: str):
        with self.Session() as session:
            statement = select(self.model).where(self.model.event_id == event_id)
            return session.execute(statement).scalar()

    def create(self, processed_event: ProcessedEvent):
        with self.Session() as session:
            session.add(processed_event)
            session.commit()
