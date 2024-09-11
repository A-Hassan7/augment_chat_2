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
            statement = (
                select(self.model)
                .where(self.model.room_id == room_id)
                .order_by(self.model.message_timestamp.asc())
            )
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


class UnprocessedEventsViewRepository:

    def __init__(self):
        self.Session = sessionmaker(bind=DatabaseEngine())

    def get_unprocessed_events(self):
        """
        Return a list of events that haven't been processed.

        This compares the processed_events table with the matrix event_json table to find events that exist
        in the matrix event_json table but not the processed_events table.
        """
        with self.Session() as session:
            query = """
            select events.event_id, events.json::jsonb as event_json
            from public.event_json events
            left join event_processor.processed_events processed
                on events.event_id = processed.event_id
            where processed.event_id is null
            """
            return session.execute(text(query)).all()
