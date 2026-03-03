"""
Database engine configuration for bridge manager.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager


class DatabaseEngine:
    """Singleton database engine for bridge manager."""

    _engine = None
    _session_factory = None

    @classmethod
    def get_engine(cls):
        """Get or create database engine."""
        if cls._engine is None:
            # Import here to avoid circular dependency
            from config import BRIDGE_MANAGER_CONFIG

            database_url = BRIDGE_MANAGER_CONFIG.DATABASE_URL
            cls._engine = create_engine(database_url, echo=False)
            cls._session_factory = sessionmaker(
                bind=cls._engine, expire_on_commit=False
            )
        return cls._engine

    @classmethod
    def get_session_factory(cls):
        """Get session factory."""
        if cls._session_factory is None:
            cls.get_engine()
        return cls._session_factory

    @classmethod
    @contextmanager
    def get_session(cls):
        """Context manager for database sessions."""
        session = cls.get_session_factory()()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


def get_db_session():
    """
    Generator function for FastAPI dependency injection.

    Usage:
        @app.get("/endpoint")
        def endpoint(db: Session = Depends(get_db_session)):
            ...
    """
    with DatabaseEngine.get_session() as session:
        yield session
