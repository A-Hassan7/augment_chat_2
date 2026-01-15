from abc import ABC

from sqlalchemy import select, update, text, func, delete, asc, desc
from sqlalchemy.orm import sessionmaker

from .models import Base, Request
from .engine import DatabaseEngine

Base.metadata.create_all(bind=DatabaseEngine())


class BaseRepository(ABC):

    def __init__(self):
        self.Session = sessionmaker(bind=DatabaseEngine())

    def get_all(self):
        with self.Session() as session:
            statement = select(self.model)
            return session.execute(statement).scalars().all()


class RequestsRepository(BaseRepository):

    model = Request

    def create(self, request: Request):
        with self.Session() as session:
            session.add(request)
            session.commit()

    def get_by_request_reference(self, request_type: str, request_reference: str):
        with self.Session() as session:
            # order transcripts by timestamp in specified order
            statement = select(self.model).where(
                self.model.request_reference == request_reference
                and self.model.request_type == request_type
            )
            return session.execute(statement).scalars().all()
