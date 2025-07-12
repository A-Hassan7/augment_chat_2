from sqlalchemy import Column, Integer, Text, DateTime, func, ARRAY, text
from sqlalchemy.orm import DeclarativeBase
from .engine import DatabaseEngine

SCHEMA_NAME = "suggestions"

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


class Suggestions(Base, TimestampMixin):
    __tablename__ = "suggestions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    room_id = Column(Text, nullable=False)
    most_recent_message_event_id = Column(Text, nullable=False)
    input_prompt = Column(Text, nullable=False)
    llm_request_reference = Column(Text, nullable=False)
    llm_request_reference_type = Column(Text, nullable=False)
    suggestion_type = Column(Text, nullable=False)
    suggestions = Column(ARRAY(Text), nullable=False)
