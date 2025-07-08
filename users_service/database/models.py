from sqlalchemy import Column, Integer, Text
from sqlalchemy.orm import DeclarativeBase, Mapped


class Base(DeclarativeBase):
    __table_args__ = {"schema": "users_service"}


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(Text)
    matrix_username = Column(Text)
    matrix_password = Column(Text)
