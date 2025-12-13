from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey
from datetime import datetime, timezone
from sqlalchemy import func
from sqlalchemy import Boolean, LargeBinary, JSON, String, Index, text
import uuid

from .engine import DatabaseEngine

SCHEMA_NAME = "bridge_manager"

with DatabaseEngine().connect() as conn:
    conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_NAME}"))
    conn.commit()


class Base(DeclarativeBase):
    __table_args__ = {"schema": "bridge_manager"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.now(timezone.utc))
    deleted_at = Column(DateTime, nullable=True)


class Homeserver(Base):
    __tablename__ = "homeservers"

    url = Column(Text, nullable=False)
    name = Column(Text, nullable=False)
    hs_token = Column(Text, nullable=False)


class Bridges(Base):
    __tablename__ = "bridges"

    bridge_service = Column(Text, nullable=False)  # (whatsapp/discord etc.)
    matrix_bot_username = Column(Text, unique=True)
    as_token = Column(Text, nullable=False)
    hs_token = Column(Text, nullable=True)
    ip = Column(Text, nullable=False)
    port = Column(Text, nullable=False)
    owner_matrix_username = Column(Text, nullable=False)
    live_status = Column(Text, nullable=True)
    ready_status = Column(Text, nullable=True)
    status_updated_at = Column(
        DateTime,
        nullable=True,
    )

    # use this instead of the one in BridgeUserRegistrations
    bridge_management_room_id = Column(Text, unique=True)


class Request(Base):
    __tablename__ = "requests"

    inbound_at = Column(DateTime, nullable=False)
    outbound_at = Column(DateTime, nullable=True)
    response_at = Column(DateTime, nullable=True)

    source = Column(Text, nullable=False)
    bridge_id = Column(Integer, ForeignKey("bridge_manager.bridges.id"))
    homeserver_id = Column(Integer, ForeignKey("bridge_manager.homeservers.id"))

    method = Column(Text, nullable=False)
    path = Column(Text, nullable=False)

    inbound_request = Column(JSON, nullable=False)
    outbound_request = Column(JSON, nullable=True)
    response = Column(JSON, nullable=True)
    response_status = Column(Integer, nullable=True)


class BridgeUserRegistrations(Base):
    __tablename__ = "bridge_user_registrations"

    bridge_id = Column(Integer, ForeignKey("bridge_manager.bridges.id"))
    matrix_username = Column(Text, nullable=False)
    bridge_management_room_id = Column(Text, nullable=False, unique=True)


class TransactionMappings(Base):
    __tablename__ = "transaction_mappings"
    __table_args__ = (
        Index("idx_transaction_mappings_transaction_id", "transaction_id"),
        {"schema": "bridge_manager"},
    )

    # unique transaction identifier (no longer a primary key to avoid composite PK with Base.id)
    transaction_id = Column(Text, nullable=False, unique=True)
    bridge_as_token = Column(Text, nullable=True)
    bridge_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
