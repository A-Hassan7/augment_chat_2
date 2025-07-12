from sqlalchemy import Column, Integer, Text, DateTime, func, ARRAY, JSON, text
from sqlalchemy.orm import DeclarativeBase
from .engine import DatabaseEngine

SCHEMA_NAME = "llm"

with DatabaseEngine().connect() as conn:
    conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_NAME}"))


class Base(DeclarativeBase):
    __table_args__ = {"schema": SCHEMA_NAME}


# add timestamp columns to model
class TimestampMixin:
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )


class Request(Base, TimestampMixin):
    __tablename__ = "requests"

    # TODO: MAJOR I want to keep a log of all llm requests and know where they came from
    # I'll need to link all llm requests to a source i.e. room_id/user_id
    id = Column(Integer, primary_key=True, autoincrement=True)
    requesting_user_id = Column(
        Text, nullable=True
    )  # HOW DO I GET THE USER ID HERE????
    request_type = Column(Text, nullable=False)
    request_reference = Column(
        Text, nullable=False
    )  # could be an event id/room id etc.
    request_reference_type = Column(Text, nullable=False)  # message_event_id/room_id
    input = Column(Text, nullable=False)
    output = Column(JSON, nullable=False)
