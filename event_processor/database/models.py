from sqlalchemy import Column, Integer, Text
from sqlalchemy.orm import DeclarativeBase, Mapped


#### EVENT PROCESSOR TABLES
class Base(DeclarativeBase):
    __table_args__ = {"schema": "event_processor"}


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
