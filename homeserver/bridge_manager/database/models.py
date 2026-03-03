"""
SQLAlchemy models for bridge manager.

Tables:
- bridges: Bridge instances (containers)
- bridge_manager_workers: Bridge manager instances
- room_bridge_mappings: Room -> Bridge mappings for fast lookup
- transaction_mappings: Transaction ID -> Bridge mappings
- request_logs: Comprehensive request/response logs
- homeservers: Homeserver information
"""

from enum import Enum
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Index
from sqlalchemy.orm import DeclarativeBase, relationship
from datetime import datetime, timezone


SCHEMA_NAME = "bridge_manager"


class BridgeType(str, Enum):
    """Supported bridge types."""

    WHATSAPP = "whatsapp"
    META = "meta"
    DISCORD = "discord"
    TELEGRAM = "telegram"


class BridgeStatus(str, Enum):
    """Bridge lifecycle statuses."""

    CREATING = "creating"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    UNHEALTHY = "unhealthy"
    ERROR = "error"
    DELETED = "deleted"


class Base(DeclarativeBase):
    """Base class for all models."""

    __table_args__ = {"schema": SCHEMA_NAME}


class Homeserver(Base):
    """Homeserver configuration."""

    __tablename__ = "homeservers"

    id = Column(String(50), primary_key=True)  # e.g., "hs-001"
    name = Column(String(255), nullable=False)  # e.g., "matrix.example.com"
    url = Column(String(255), nullable=False)  # e.g., "http://localhost:8008"
    hs_token = Column(
        String(255), nullable=False
    )  # Token HS uses to auth to appservice
    created_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(DateTime, onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    bridges = relationship("Bridge", back_populates="homeserver")


class BridgeManagerWorker(Base):
    """Bridge manager worker instances for tracking multiple instances."""

    __tablename__ = "bridge_manager_workers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    instance_id = Column(String(50), nullable=False, unique=True)  # e.g., "bm-001"
    host = Column(String(255), nullable=False)
    port = Column(Integer, nullable=False)
    homeserver_id = Column(
        String(50), ForeignKey(f"{SCHEMA_NAME}.homeservers.id"), nullable=False
    )
    status = Column(String(50), nullable=False, default="active")  # active/inactive
    last_heartbeat = Column(DateTime)
    created_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(DateTime, onupdate=lambda: datetime.now(timezone.utc))


class Bridge(Base):
    """Bridge container instances."""

    __tablename__ = "bridges"

    id = Column(Integer, primary_key=True, autoincrement=True)
    orchestrator_id = Column(
        String(50), nullable=False, unique=True
    )  # Unique ID assigned by orchestrator
    bridge_type = Column(String(50), nullable=False)  # whatsapp, meta, discord, etc.

    # Container info
    container_id = Column(String(255), nullable=False)
    container_name = Column(String(255), nullable=False)
    volume_name = Column(String(255), nullable=False)
    host = Column(String(255), nullable=False)  # IP/hostname where container runs
    port = Column(Integer, nullable=False)

    # Auth tokens
    as_token = Column(String(255), nullable=False, unique=True)  # Bridge's AS token
    hs_token = Column(String(255), nullable=False)  # HS token bridge uses

    # Associations
    homeserver_id = Column(
        String(50), ForeignKey(f"{SCHEMA_NAME}.homeservers.id"), nullable=False
    )
    bridge_manager_id = Column(String(50), nullable=False)  # Which BM manages this

    # Matrix identifiers
    matrix_bot_username = Column(
        String(255), nullable=False, unique=True
    )  # @_bm_wa_123__bot:hs.com
    owner_matrix_username = Column(
        String(255), nullable=False
    )  # User who owns this bridge
    bridge_management_room_id = Column(String(255))  # Management room

    # Status
    status = Column(
        String(50), nullable=False, default="active"
    )  # active/inactive/provisioning/error

    # Timestamps
    created_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(DateTime, onupdate=lambda: datetime.now(timezone.utc))
    deleted_at = Column(DateTime)

    # Relationships
    homeserver = relationship("Homeserver", back_populates="bridges")
    room_mappings = relationship("RoomBridgeMapping", back_populates="bridge")
    transaction_mappings = relationship("TransactionMapping", back_populates="bridge")
    request_logs = relationship("RequestLog", back_populates="bridge")

    # Indexes
    __table_args__ = (
        Index("ix_bridges_as_token", "as_token"),
        Index("ix_bridges_orchestrator_id", "orchestrator_id"),
        Index("ix_bridges_owner", "owner_matrix_username"),
        Index("ix_bridges_homeserver", "homeserver_id"),
        {"schema": SCHEMA_NAME},
    )


class RoomBridgeMapping(Base):
    """Room to bridge mappings for fast lookup."""

    __tablename__ = "room_bridge_mappings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    room_id = Column(String(255), nullable=False, unique=True)  # Matrix room ID
    bridge_id = Column(Integer, ForeignKey(f"{SCHEMA_NAME}.bridges.id"), nullable=False)
    created_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(DateTime, onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    bridge = relationship("Bridge", back_populates="room_mappings")

    # Indexes
    __table_args__ = (
        Index("ix_room_bridge_mappings_room_id", "room_id"),
        {"schema": SCHEMA_NAME},
    )


class TransactionMapping(Base):
    """Transaction ID to bridge mappings for caching."""

    __tablename__ = "transaction_mappings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    transaction_id = Column(String(255), nullable=False, unique=True)
    bridge_id = Column(Integer, ForeignKey(f"{SCHEMA_NAME}.bridges.id"), nullable=False)
    created_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    bridge = relationship("Bridge", back_populates="transaction_mappings")

    # Indexes
    __table_args__ = (
        Index("ix_transaction_mappings_txn_id", "transaction_id"),
        {"schema": SCHEMA_NAME},
    )


class RequestLog(Base):
    """Comprehensive request/response logging."""

    __tablename__ = "request_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String(50), nullable=False, unique=True)  # UUID

    # Request context
    source = Column(String(50), nullable=False)  # homeserver/bridge
    direction = Column(String(50), nullable=False)  # inbound/outbound
    bridge_id = Column(Integer, ForeignKey(f"{SCHEMA_NAME}.bridges.id"))
    discovery_method = Column(String(50))  # How bridge was identified

    # Request details
    method = Column(String(10), nullable=False)  # GET, POST, etc.
    path = Column(Text, nullable=False)
    query_params = Column(JSON)
    headers = Column(JSON)
    body = Column(JSON)

    # Raw request snapshots for debugging
    raw_incoming_request = Column(
        JSON
    )  # Full request as received (method, url, headers, body)
    raw_outgoing_request = Column(
        JSON
    )  # Full request as forwarded (method, url, headers, body)

    # Response details
    status_code = Column(Integer)
    response_body = Column(JSON)
    error = Column(Text)
    duration_ms = Column(Integer)
    response_source = Column(String(20))  # "appservice" | "upstream"

    # Forwarding info
    forwarded_to = Column(String(255))  # "host:port" where request was forwarded

    # Timestamps
    timestamp = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    bridge = relationship("Bridge", back_populates="request_logs")

    # Indexes
    __table_args__ = (
        Index("ix_request_logs_request_id", "request_id"),
        Index("ix_request_logs_bridge_id", "bridge_id"),
        Index("ix_request_logs_timestamp", "timestamp"),
        {"schema": SCHEMA_NAME},
    )


def create_schema_and_tables():
    """Create schema and all tables."""
    from .engine import DatabaseEngine
    from sqlalchemy import text

    engine = DatabaseEngine.get_engine()

    # Create schema
    with engine.connect() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_NAME}"))
        conn.commit()

    # Create all tables
    Base.metadata.create_all(engine)
    print(f"Schema '{SCHEMA_NAME}' and tables created successfully")


if __name__ == "__main__":
    create_schema_and_tables()
