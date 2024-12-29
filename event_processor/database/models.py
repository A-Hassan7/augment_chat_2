from sqlalchemy import Column, Integer, Text, DateTime, func
from sqlalchemy.orm import DeclarativeBase


#### EVENT PROCESSOR TABLES
class Base(DeclarativeBase):
    __table_args__ = {"schema": "event_processor"}


# add timestamp columns to model
class TimestampMixin:
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )


class ParsedMessage(Base, TimestampMixin):
    __tablename__ = "parsed_messages"

    event_id = Column(Text, primary_key=True)
    room_id = Column(Text, nullable=False)
    message_timestamp = Column(DateTime, nullable=False)
    matrix_server_hostname = Column(Text, nullable=False)
    message_type = Column(Text, nullable=False)
    sender = Column(Text, nullable=False)
    body = Column(Text)
    in_reply_to_event_id = Column(Text)
    resource_url = Column(Text)
    depth = Column(Integer)


class ProcessedEvent(Base, TimestampMixin):
    __tablename__ = "processed_events"

    event_id = Column(Text, primary_key=True)


#### MATRIX LOGICAL REPLICATION TABLE
class MatrixBase(DeclarativeBase):
    # this is for tables that are replicated from the matrix synapse server
    # the schema needs to be public because postgresql logical replication can only
    # replicate using fully qualified table names (inc. the schema) and the synapse database
    # has all it's tables stored in the public schema.
    __table_args__ = {"schema": "public"}


class MatrixEventJson(MatrixBase):
    __tablename__ = "event_json"

    event_id = Column(Text, primary_key=True, nullable=False)
    room_id = Column(Text, nullable=False)
    internal_metadata = Column(Text, nullable=False)
    json = Column(Text, nullable=False)
    format_version = Column(Integer, nullable=True)
