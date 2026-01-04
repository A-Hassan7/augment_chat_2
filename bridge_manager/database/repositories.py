from datetime import datetime, UTC
from abc import ABC, abstractmethod

from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, and_, insert

from .models import (
    Bridges,
    Homeserver,
    # BridgeUserRegistrations,
    Base,
    TransactionMappings,
    Request,
    RoomBridgeMapping,
)
from .engine import DatabaseEngine

Base.metadata.create_all(DatabaseEngine())


class BaseRepository(ABC):
    def __init__(self, session_factory=None):
        # Allow dependency injection for easier testing
        self.Session = session_factory or sessionmaker(bind=DatabaseEngine())

    @property
    @abstractmethod
    def model(self):
        # Force subclasses to define the model
        pass

    @abstractmethod
    def get_all(self):
        with self.Session() as session:
            statement = select(self.model)
            return session.execute(statement).scalars().all()

    def create(self, **kwargs):
        with self.Session() as session:
            obj = self.model(**kwargs)
            session.add(obj)
            session.commit()
            session.refresh(obj)
            return obj

    def get_by_id(self, id_):
        with self.Session() as session:
            return session.get(self.model, id_)

    def update(self, id_, **kwargs):
        with self.Session() as session:
            obj = session.get(self.model, id_)
            if not obj:
                return None
            for key, value in kwargs.items():
                setattr(obj, key, value)
            session.commit()
            session.refresh(obj)
            return obj


class BridgesRepository(BaseRepository):
    """Repository for bridge database operations with caching."""

    model = Bridges

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cache = {}

    def get_all(self):
        with self.Session() as session:
            statement = select(self.model)
            return session.execute(statement).scalars().all()

    def get_by_bridge_service(self, bridge_service: str):
        with self.Session() as session:
            statement = select(self.model).where(
                self.model.bridge_service == bridge_service
            )
            return session.execute(statement).scalars().all()

    def get_by_as_token(self, as_token: str):
        cache_key = f"as_token:{as_token}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        with self.Session() as session:
            statement = select(self.model).where(self.model.as_token == as_token)
            result = session.execute(statement).scalar_one_or_none()
            if result:
                self._cache[cache_key] = result
            return result

    def get_by_owner_username_and_service(
        self, owner_matrix_username: str, bridge_service: str
    ):
        with self.Session() as session:
            statement = select(self.model).where(
                and_(
                    self.model.owner_matrix_username == owner_matrix_username,
                    self.model.bridge_service == bridge_service,
                )
            )
            return session.execute(statement).scalar_one_or_none()

    def get_by_owner_username(self, owner_matrix_username: str):
        with self.Session() as session:
            statement = select(self.model).where(
                self.model.owner_matrix_username == owner_matrix_username,
            )
            return session.execute(statement).scalars().all()

    def get_by_orchestrator_id(self, orchestrator_id: str):
        cache_key = f"orchestrator_id:{orchestrator_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        with self.Session() as session:
            statement = select(self.model).where(
                self.model.orchestrator_id == orchestrator_id
            )
            result = session.execute(statement).scalar_one_or_none()
            if result:
                self._cache[cache_key] = result
            return result


class HomeserversRepository(BaseRepository):

    model = Homeserver

    def get_all(self):
        with self.Session() as session:
            statement = select(self.model)
            return session.execute(statement).scalars().all()

    def get_by_hs_token(self, hs_token: str):
        with self.Session() as session:
            statement = select(self.model).where(self.model.hs_token == hs_token)
            return session.execute(statement).scalar_one_or_none()


class RequestsRepository(BaseRepository):

    model = Request

    def get_all(self):
        with self.Session() as session:
            statement = select(self.model)
            return session.execute(statement).scalars().all()

    def delete_by_bridge_id(self, bridge_id: int):
        """Delete all request records for a specific bridge."""
        with self.Session() as session:
            deleted_count = (
                session.query(self.model)
                .filter(self.model.bridge_id == bridge_id)
                .delete()
            )
            session.commit()
            return deleted_count


# class BridgeUserRegistrationsRepository(BaseRepository):

#     model = BridgeUserRegistrations

#     def get_all(self):
#         with self.Session() as session:
#             statement = select(self.model)
#             return session.execute(statement).scalars().all()

#     def get_by_matrix_username_and_bot_ids(self, matrix_username: str, bot_ids: list):
#         with self.Session() as session:
#             statement = select(self.model).where(
#                 and_(
#                     self.model.matrix_username == matrix_username,
#                     self.model.bridge_bot_id.in_(bot_ids),
#                 )
#             )
#             # return a single scalar value and raise error if more than results are found
#             # importantly scalar doesn't raise an error if no results are found
#             return session.execute(statement).scalar()

#     def create(self, bridge_bot_id, matrix_username, bridge_management_room_id):
#         with self.Session() as session:
#             statement = insert(self.model).values(
#                 bridge_bot_id=bridge_bot_id,
#                 matrix_username=matrix_username,
#                 bridge_management_room_id=bridge_management_room_id,
#                 created_at=datetime.now(UTC),
#             )
#             session.execute(statement)
#             session.commit()


class TransactionMappingsRepository(BaseRepository):
    model = TransactionMappings

    def get_all(self):
        with self.Session() as session:
            statement = select(self.model)
            return session.execute(statement).scalars().all()

    def get_bridge_by_transaction(self, transaction_id: str):
        with self.Session() as session:
            statement = select(self.model).where(
                self.model.transaction_id == transaction_id
            )
            return session.execute(statement).scalar_one_or_none()

    def upsert(
        self, transaction_id: str, bridge_as_token: str = None, bridge_id: int = None
    ):
        with self.Session() as session:
            statement = select(self.model).where(
                self.model.transaction_id == transaction_id
            )
            existing = session.execute(statement).scalar_one_or_none()
            if existing:
                if bridge_as_token:
                    existing.bridge_as_token = bridge_as_token
                if bridge_id is not None:
                    existing.bridge_id = bridge_id
                session.commit()
                session.refresh(existing)
                return existing
            else:
                obj = self.model(
                    transaction_id=transaction_id,
                    bridge_as_token=bridge_as_token,
                    bridge_id=bridge_id,
                )
                session.add(obj)
                session.commit()
                session.refresh(obj)
                return obj

    def delete_by_bridge_id(self, bridge_id: int):
        """Delete all transaction mappings for a specific bridge."""
        with self.Session() as session:
            deleted_count = (
                session.query(self.model)
                .filter(self.model.bridge_id == bridge_id)
                .delete()
            )
            session.commit()
            return deleted_count


class RoomBridgeMappingRepository(BaseRepository):
    model = RoomBridgeMapping

    def get_all(self):
        with self.Session() as session:
            statement = select(self.model)
            return session.execute(statement).scalars().all()

    def get_bridge_by_room_id(self, room_id: str):
        """Get bridge_id associated with a room_id (uses indexed query)."""
        with self.Session() as session:
            # Optimized: only select bridge_id instead of full object
            statement = select(self.model.bridge_id).where(
                self.model.room_id == room_id
            )
            result = session.execute(statement).scalar_one_or_none()
            return result

    def upsert(self, room_id: str, bridge_id: int):
        """
        Create or update room-bridge mapping.
        Updates last_seen_at if mapping exists.
        """
        with self.Session() as session:
            statement = select(self.model).where(self.model.room_id == room_id)
            existing = session.execute(statement).scalar_one_or_none()

            if existing:
                existing.last_seen_at = datetime.now(UTC)
                existing.bridge_id = bridge_id  # Update in case it changed
                session.commit()
                session.refresh(existing)
                return existing
            else:
                obj = self.model(
                    room_id=room_id,
                    bridge_id=bridge_id,
                )
                session.add(obj)
                session.commit()
                session.refresh(obj)
                return obj

    def delete_by_bridge_id(self, bridge_id: int):
        """Delete all room-bridge mappings for a specific bridge."""
        with self.Session() as session:
            deleted_count = (
                session.query(self.model)
                .filter(self.model.bridge_id == bridge_id)
                .delete()
            )
            session.commit()
            return deleted_count
