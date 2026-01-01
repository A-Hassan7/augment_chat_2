from sqlalchemy import Column, Integer, Text, text, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped
from .engine import DatabaseEngine

SCHEMA_NAME = "users"

with DatabaseEngine().connect() as conn:
    conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_NAME}"))
    conn.commit()


class Base(DeclarativeBase):
    __table_args__ = {"schema": SCHEMA_NAME}


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(Text, nullable=False)
    matrix_username = Column(Text)
    matrix_password = Column(Text)
