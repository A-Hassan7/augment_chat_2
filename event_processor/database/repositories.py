from abc import ABC, abstractmethod

from sqlalchemy import select, update, text, delete
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

    def get_by_event_id(self, event_id: str):
        with self.Session() as session:
            statement = select(self.model).where(self.model.event_id == event_id)
            return session.execute(statement).scalar()

    def get_by_room_id(self, room_id: str):
        with self.Session() as session:
            statement = (
                select(self.model)
                .where(self.model.room_id == room_id)
                .order_by(self.model.message_timestamp.asc())
            )
            return session.execute(statement).scalars().all()

    def get_unique_room_ids(self):
        with self.Session() as session:
            statement = select(self.model.room_id).distinct()
            return session.execute(statement).scalars().all()

    def create(self, parsed_message: ParsedMessage):
        with self.Session() as session:

            # need to prevent the session from expiring so that the parsed_message
            # can still be accessed in the event_processor. Without this the following error is created
            # sqlalchemy.orm.exc.DetachedInstanceError
            session.expire_on_commit = False

            session.add(parsed_message)
            session.commit()

    def delete_by_event_id(self, event_id: str):
        with self.Session() as session:
            statement = delete(self.model).where(self.model.event_id == event_id)
            session.execute(statement)
            session.commit()


class ProcessedEventsRepository(BaseRepository):

    model = ProcessedEvent

    def delete_by_event_id(self, event_id: str):
        with self.Session() as session:
            statement = delete(self.model).where(self.model.event_id == event_id)
            session.execute(statement)
            session.commit()

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

    def get_unprocessed_events(self, room_id: str = None):
        """
        Return a list of events that haven't been processed.

        This compares the processed_events table with the matrix event_json table to find events that exist
        in the matrix event_json table but not the processed_events table.

        Args:
            room_id (str, optional): Get unprocessed events for a specific room_id if provided
        """
        with self.Session() as session:
            query = """
            select events.event_id, events.json::jsonb as event_json
            from public.event_json events
            left join event_processor.processed_events processed
                on events.event_id = processed.event_id
            where processed.event_id is null
            """

            if room_id:
                query += f" and events.room_id = '{room_id}'"

            return session.execute(text(query)).all()
