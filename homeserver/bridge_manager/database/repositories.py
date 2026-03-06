"""
Repository classes for database access.

Provides CRUD operations and queries for all bridge manager entities.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from sqlalchemy import select, and_
from sqlalchemy.orm import Session, joinedload

from .models import (
    Bridge,
    BridgeManagerWorker,
    Homeserver,
    RoomBridgeMapping,
    TransactionMapping,
    RequestLog,
)
from .engine import DatabaseEngine


class HomeserverRepository:
    """Repository for homeserver operations."""

    @staticmethod
    def create(
        id: str,
        name: str,
        url: str,
        hs_token: str,
    ) -> Homeserver:
        """Create a new homeserver."""
        with DatabaseEngine.get_session() as session:
            homeserver = Homeserver(
                id=id,
                name=name,
                url=url,
                hs_token=hs_token,
            )
            session.add(homeserver)
            session.flush()
            return homeserver

    @staticmethod
    def get_by_id(homeserver_id: str) -> Optional[Homeserver]:
        """Get homeserver by ID."""
        with DatabaseEngine.get_session() as session:
            return session.get(Homeserver, homeserver_id)

    @staticmethod
    def get_by_hs_token(hs_token: str) -> Optional[Homeserver]:
        """Get homeserver by HS token."""
        with DatabaseEngine.get_session() as session:
            stmt = select(Homeserver).where(Homeserver.hs_token == hs_token)
            return session.execute(stmt).scalar_one_or_none()

    @staticmethod
    def list_all() -> List[Homeserver]:
        """List all homeservers."""
        with DatabaseEngine.get_session() as session:
            stmt = select(Homeserver)
            return list(session.execute(stmt).scalars().all())

    @staticmethod
    def get_or_create(
        id: str,
        name: str,
        url: str,
        hs_token: str,
    ) -> Homeserver:
        """Get existing homeserver or create if not exists."""
        with DatabaseEngine.get_session() as session:
            # Try to get existing
            homeserver = session.get(Homeserver, id)

            if homeserver:
                # Update fields in case they changed
                homeserver.name = name
                homeserver.url = url
                homeserver.hs_token = hs_token
                homeserver.updated_at = datetime.now(timezone.utc)
                session.flush()
            else:
                # Create new
                homeserver = Homeserver(
                    id=id,
                    name=name,
                    url=url,
                    hs_token=hs_token,
                )
                session.add(homeserver)
                session.flush()

            # No need to refresh - all attributes are already loaded
            return homeserver


class BridgeManagerWorkerRepository:
    """Repository for bridge manager worker operations."""

    @staticmethod
    def create(
        instance_id: str,
        host: str,
        port: int,
        homeserver_id: str,
    ) -> BridgeManagerWorker:
        """Create a new bridge manager worker."""
        with DatabaseEngine.get_session() as session:
            worker = BridgeManagerWorker(
                instance_id=instance_id,
                host=host,
                port=port,
                homeserver_id=homeserver_id,
                status="active",
            )
            session.add(worker)
            session.flush()
            return worker

    @staticmethod
    def get_or_create(
        instance_id: str,
        host: str,
        port: int,
        homeserver_id: str,
    ) -> BridgeManagerWorker:
        """
        Get existing worker record or create a new one, then mark it active.

        Called on instance startup so every run is reflected in the DB.
        If the instance previously existed (e.g. container restart) its host,
        port, and status are refreshed.
        """
        with DatabaseEngine.get_session() as session:
            stmt = select(BridgeManagerWorker).where(
                BridgeManagerWorker.instance_id == instance_id
            )
            worker = session.execute(stmt).scalar_one_or_none()
            if worker:
                worker.host = host
                worker.port = port
                worker.status = "active"
                worker.last_heartbeat = datetime.now(timezone.utc)
                session.flush()
            else:
                worker = BridgeManagerWorker(
                    instance_id=instance_id,
                    host=host,
                    port=port,
                    homeserver_id=homeserver_id,
                    status="active",
                    last_heartbeat=datetime.now(timezone.utc),
                )
                session.add(worker)
                session.flush()
            return worker

    @staticmethod
    def update_status(instance_id: str, status: str) -> bool:
        """
        Update the status of a worker instance.

        Args:
            instance_id: Worker instance ID
            status: New status (e.g. "active", "inactive")

        Returns:
            True if the record was found and updated, False otherwise
        """
        with DatabaseEngine.get_session() as session:
            stmt = select(BridgeManagerWorker).where(
                BridgeManagerWorker.instance_id == instance_id
            )
            worker = session.execute(stmt).scalar_one_or_none()
            if worker:
                worker.status = status
                session.flush()
                return True
            return False

    @staticmethod
    def update_heartbeat(instance_id: str) -> bool:
        """Update last heartbeat for a worker."""
        with DatabaseEngine.get_session() as session:
            stmt = select(BridgeManagerWorker).where(
                BridgeManagerWorker.instance_id == instance_id
            )
            worker = session.execute(stmt).scalar_one_or_none()
            if worker:
                worker.last_heartbeat = datetime.now(timezone.utc)
                return True
            return False

    @staticmethod
    def list_by_homeserver(homeserver_id: str) -> List[BridgeManagerWorker]:
        """List all workers for a homeserver."""
        with DatabaseEngine.get_session() as session:
            stmt = select(BridgeManagerWorker).where(
                BridgeManagerWorker.homeserver_id == homeserver_id
            )
            return list(session.execute(stmt).scalars().all())


class BridgeRepository:
    """Repository for bridge operations."""

    @staticmethod
    def create(
        orchestrator_id: str,
        bridge_type: str,
        container_id: str,
        container_name: str,
        volume_name: str,
        host: str,
        port: int,
        as_token: str,
        hs_token: str,
        homeserver_id: str,
        bridge_manager_id: str,
        matrix_bot_username: str,
        owner_matrix_username: str,
        bridge_management_room_id: Optional[str] = None,
    ) -> Bridge:
        """Create a new bridge."""
        with DatabaseEngine.get_session() as session:
            bridge = Bridge(
                orchestrator_id=orchestrator_id,
                bridge_type=bridge_type,
                container_id=container_id,
                container_name=container_name,
                volume_name=volume_name,
                host=host,
                port=port,
                as_token=as_token,
                hs_token=hs_token,
                homeserver_id=homeserver_id,
                bridge_manager_id=bridge_manager_id,
                matrix_bot_username=matrix_bot_username,
                owner_matrix_username=owner_matrix_username,
                bridge_management_room_id=bridge_management_room_id,
                status="active",
            )
            session.add(bridge)
            session.flush()
            return bridge

    @staticmethod
    def get_by_id(bridge_id: int) -> Optional[Bridge]:
        """Get bridge by ID."""
        with DatabaseEngine.get_session() as session:
            stmt = (
                select(Bridge)
                .where(Bridge.id == bridge_id)
                .options(joinedload(Bridge.homeserver))
            )
            bridge = session.execute(stmt).scalar_one_or_none()
            if bridge:
                session.expunge(bridge)
            return bridge

    @staticmethod
    def get_by_as_token(as_token: str) -> Optional[Bridge]:
        """Get bridge by AS token."""
        with DatabaseEngine.get_session() as session:
            stmt = (
                select(Bridge)
                .where(and_(Bridge.as_token == as_token, Bridge.deleted_at.is_(None)))
                .options(joinedload(Bridge.homeserver))
            )
            bridge = session.execute(stmt).scalar_one_or_none()
            if bridge:
                session.expunge(bridge)
            return bridge

    @staticmethod
    def get_by_orchestrator_id(orchestrator_id: str) -> Optional[Bridge]:
        """Get bridge by orchestrator ID."""
        with DatabaseEngine.get_session() as session:
            stmt = (
                select(Bridge)
                .where(
                    and_(
                        Bridge.orchestrator_id == orchestrator_id,
                        Bridge.deleted_at.is_(None),
                    )
                )
                .options(joinedload(Bridge.homeserver))
            )
            bridge = session.execute(stmt).scalar_one_or_none()
            if bridge:
                session.expunge(bridge)
            return bridge

    @staticmethod
    def get_by_port(port: int) -> Optional[Bridge]:
        """Get bridge by port number."""
        with DatabaseEngine.get_session() as session:
            stmt = (
                select(Bridge)
                .where(
                    and_(
                        Bridge.port == port,
                        Bridge.deleted_at.is_(None),
                    )
                )
                .options(joinedload(Bridge.homeserver))
            )
            bridge = session.execute(stmt).scalar_one_or_none()
            if bridge:
                session.expunge(bridge)
            return bridge

    @staticmethod
    def list_by_owner(owner_matrix_username: str) -> List[Bridge]:
        """List all bridges owned by a user."""
        with DatabaseEngine.get_session() as session:
            stmt = select(Bridge).where(
                and_(
                    Bridge.owner_matrix_username == owner_matrix_username,
                    Bridge.deleted_at.is_(None),
                )
            )
            return list(session.execute(stmt).scalars().all())

    @staticmethod
    def list_by_homeserver(homeserver_id: str) -> List[Bridge]:
        """List all bridges for a homeserver."""
        with DatabaseEngine.get_session() as session:
            stmt = select(Bridge).where(
                and_(
                    Bridge.homeserver_id == homeserver_id,
                    Bridge.deleted_at.is_(None),
                )
            )
            return list(session.execute(stmt).scalars().all())

    @staticmethod
    def update_status(bridge_id: int, status: str) -> bool:
        """Update bridge status."""
        with DatabaseEngine.get_session() as session:
            bridge = session.get(Bridge, bridge_id)
            if bridge:
                bridge.status = status
                return True
            return False

    @staticmethod
    def soft_delete(bridge_id: int) -> bool:
        """Soft delete a bridge."""
        with DatabaseEngine.get_session() as session:
            bridge = session.get(Bridge, bridge_id)
            if bridge:
                bridge.deleted_at = datetime.now(timezone.utc)
                bridge.status = "deleted"
                return True
            return False


class RoomBridgeMappingRepository:
    """Repository for room-bridge mappings."""

    @staticmethod
    def create(room_id: str, bridge_id: int) -> RoomBridgeMapping:
        """Create a new room-bridge mapping."""
        with DatabaseEngine.get_session() as session:
            mapping = RoomBridgeMapping(room_id=room_id, bridge_id=bridge_id)
            session.add(mapping)
            session.flush()
            return mapping

    @staticmethod
    def get_bridge_by_room_id(room_id: str) -> Optional[Bridge]:
        """Get bridge associated with a room."""
        with DatabaseEngine.get_session() as session:
            stmt = (
                select(Bridge)
                .join(RoomBridgeMapping)
                .where(
                    and_(
                        RoomBridgeMapping.room_id == room_id,
                        Bridge.deleted_at.is_(None),
                    )
                )
            )
            return session.execute(stmt).scalar_one_or_none()

    @staticmethod
    def delete_by_room_id(room_id: str) -> bool:
        """Delete room-bridge mapping."""
        with DatabaseEngine.get_session() as session:
            stmt = select(RoomBridgeMapping).where(RoomBridgeMapping.room_id == room_id)
            mapping = session.execute(stmt).scalar_one_or_none()
            if mapping:
                session.delete(mapping)
                return True
            return False


class TransactionMappingRepository:
    """Repository for transaction mappings (caching)."""

    @staticmethod
    def create(transaction_id: str, bridge_id: int) -> TransactionMapping:
        """Create a new transaction-bridge mapping."""
        with DatabaseEngine.get_session() as session:
            mapping = TransactionMapping(
                transaction_id=transaction_id, bridge_id=bridge_id
            )
            session.add(mapping)
            session.flush()
            return mapping

    @staticmethod
    def get_bridge_by_transaction_id(transaction_id: str) -> Optional[Bridge]:
        """Get bridge associated with a transaction."""
        with DatabaseEngine.get_session() as session:
            stmt = (
                select(Bridge)
                .join(TransactionMapping)
                .where(
                    and_(
                        TransactionMapping.transaction_id == transaction_id,
                        Bridge.deleted_at.is_(None),
                    )
                )
            )
            return session.execute(stmt).scalar_one_or_none()


class RequestLogRepository:
    """Repository for request logging."""

    @staticmethod
    def create(
        request_id: str,
        source: str,
        direction: str,
        method: str,
        path: str,
        bridge_id: Optional[int] = None,
        discovery_method: Optional[str] = None,
        query_params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, Any]] = None,
        body: Optional[Dict[str, Any]] = None,
        forwarded_to: Optional[str] = None,
        raw_incoming_request: Optional[Dict[str, Any]] = None,
    ) -> RequestLog:
        """Create a new request log entry."""
        with DatabaseEngine.get_session() as session:
            log = RequestLog(
                request_id=request_id,
                source=source,
                direction=direction,
                bridge_id=bridge_id,
                discovery_method=discovery_method,
                method=method,
                path=path,
                query_params=query_params,
                headers=headers,
                body=body,
                forwarded_to=forwarded_to,
                raw_incoming_request=raw_incoming_request,
            )
            session.add(log)
            session.flush()
            return log

    @staticmethod
    def update_response(
        request_id: str,
        status_code: int,
        response_body: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[int] = None,
        error: Optional[str] = None,
        raw_outgoing_request: Optional[Dict[str, Any]] = None,
        response_source: Optional[str] = None,
        handler_name: Optional[str] = None,
    ) -> bool:
        """Update request log with response details."""
        with DatabaseEngine.get_session() as session:
            stmt = select(RequestLog).where(RequestLog.request_id == request_id)
            log = session.execute(stmt).scalar_one_or_none()
            if log:
                log.status_code = status_code
                log.response_body = response_body
                log.duration_ms = duration_ms
                log.error = error
                if raw_outgoing_request is not None:
                    log.raw_outgoing_request = raw_outgoing_request
                if response_source is not None:
                    log.response_source = response_source
                if handler_name is not None:
                    log.handler_name = handler_name
                return True
            return False

    @staticmethod
    def update_bridge_context(
        request_id: str,
        bridge_id: int,
        discovery_method: Optional[str] = None,
    ) -> bool:
        """Update request log with bridge context once the bridge is identified."""
        with DatabaseEngine.get_session() as session:
            stmt = select(RequestLog).where(RequestLog.request_id == request_id)
            log = session.execute(stmt).scalar_one_or_none()
            if log:
                log.bridge_id = bridge_id
                if discovery_method is not None:
                    log.discovery_method = discovery_method
                return True
            return False

    @staticmethod
    def get_by_request_id(request_id: str) -> Optional[RequestLog]:
        """Get request log by request ID."""
        with DatabaseEngine.get_session() as session:
            stmt = select(RequestLog).where(RequestLog.request_id == request_id)
            return session.execute(stmt).scalar_one_or_none()

    @staticmethod
    def list_by_bridge(bridge_id: int, limit: int = 100) -> List[RequestLog]:
        """List recent logs for a bridge."""
        with DatabaseEngine.get_session() as session:
            stmt = (
                select(RequestLog)
                .where(RequestLog.bridge_id == bridge_id)
                .order_by(RequestLog.timestamp.desc())
                .limit(limit)
            )
            return list(session.execute(stmt).scalars().all())
