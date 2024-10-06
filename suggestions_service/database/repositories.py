from abc import ABC

from sqlalchemy import select, update, text, func, delete, asc, desc
from sqlalchemy.orm import sessionmaker

from .models import Base, Suggestions
from .engine import DatabaseEngine

Base.metadata.create_all(bind=DatabaseEngine())


class BaseRepository(ABC):

    def __init__(self):
        self.Session = sessionmaker(bind=DatabaseEngine())

    def get_all(self):
        with self.Session() as session:
            statement = select(self.model)
            return session.execute(statement).scalars().all()


class SuggestionsRepository(BaseRepository):

    model = Suggestions

    def create(self, suggestions: Suggestions):
        with self.Session() as session:
            session.add(suggestions)
            session.commit()

    def get_by_room_id(self, room_id: str):
        with self.Session() as session:
            # order transcripts by timestamp in specified order
            statement = select(self.model).where(self.model.room_id == room_id)
            return session.execute(statement).scalars().all()

    def delete_by_room_id(self, room_id: str):
        with self.session() as session:
            statement = delete(self.model).where(self.model.room_id == room_id)
            session.execute(statement)
            session.commit()
