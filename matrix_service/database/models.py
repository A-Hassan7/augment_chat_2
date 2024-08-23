from sqlalchemy import Column, Integer, Text
from sqlalchemy.orm import DeclarativeBase, Mapped


class Base(DeclarativeBase):
    pass


class AccessTokens(Base):
    __tablename__ = "access_tokens"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)
    token = Column(Text)
    device_id = Column(Text)
    user_id = Column(Text)


class Users(Base):
    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}

    name = Column(Text, primary_key=True)
    password_hash = Column(Text)


class LocalCurrentMembership(Base):
    __tablename__ = "local_current_membership"
    __table_args__ = {"extend_existing": True}

    room_id = Column(Text)
    user_id = Column(Text)
    event_id = Column(Text, primary_key=True)
    membership = Column(Text)


class Events(Base):
    __tablename__ = "events"
    __table_args__ = {"extend_existing": True}

    event_id = Column(Text, primary_key=True)
    room_id = Column(Text)
    type = Column(Text)
    received_ts = Column(Integer)
    sender = Column(Text)


class EventJson(Base):
    __tablename__ = "event_json"
    __table_args__ = {"extend_existing": True}

    event_id = Column(Text, primary_key=True)
    room_id = Column(Text)
    json = Column(Text)



