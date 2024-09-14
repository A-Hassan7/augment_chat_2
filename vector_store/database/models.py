from sqlalchemy import Column, Integer, Text, DateTime, func, ARRAY, Float
from sqlalchemy.orm import DeclarativeBase

# from pgvector.sqlalchemy import Vector


#### VECTOR STORE TABLES
class Base(DeclarativeBase):
    __table_args__ = {"schema": "vector_store"}


# add timestamp columns to model
class TimestampMixin:
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )


class Transcript(Base, TimestampMixin):
    __tablename__ = "transcripts"

    event_id = Column(Text, nullable=False, primary_key=True)
    room_id = Column(Text, nullable=False)
    sender_matrix_user_id = Column(Text, nullable=False)
    message_timestamp = Column(DateTime, nullable=False)
    depth = Column(Integer)
    transcript = Column(Text, nullable=False)


class TranscriptChunk(Base, TimestampMixin):
    __tablename__ = "transcript_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    room_id = Column(Text, nullable=False)
    event_ids = Column(ARRAY(Text), nullable=False, unique=True)
    min_message_depth = Column(Integer, nullable=False)
    max_message_depth = Column(Integer, nullable=False)
    min_message_timestamp = Column(DateTime, nullable=False)
    max_message_timestamp = Column(DateTime, nullable=False)
    num_transcripts = Column(Integer, nullable=False)
    document = Column(Text, nullable=False)
    embedding = Column(ARRAY(Float))  # TODO: use Vector type instead


#### MATRIX LOGICAL REPLICATION TABLE
class MatrixBase(DeclarativeBase):
    # this is for tables that are replicated from the matrix synapse server
    # the schema needs to be public because postgresql logical replication can only
    # replicate using fully qualified table names (inc. the schema) and the synapse database
    # has all it's tables stored in the public schema.
    __table_args__ = {"schema": "public"}


class MatrixProfile(MatrixBase):
    __tablename__ = "profiles"

    user_id = Column(Text, primary_key=True, nullable=False)
    displayname = Column(Text)
    avatar_url = Column(Text)
    full_user_id = Column(Text, nullable=False)
