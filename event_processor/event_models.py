from typing import Optional
from pydantic import BaseModel, Field, field_validator, ValidationError

from .errors import NoContentInRoomMessageEvent, UnsupportedMessageContentType


class BaseEvent(BaseModel):
    event_id: str


class RoomMessageEvent(BaseEvent):
    type: str
    depth: int
    origin: str
    sender: str
    room_id: str
    origin_server_ts: int
    content: dict

    @field_validator("content")
    def create_content(content):

        if not content:
            raise NoContentInRoomMessageEvent(
                "RoomMessageEvent does not contain any content"
            )

        msgtype = content.get("msgtype")
        msgtype_mapper = {
            "m.text": TextMessageContent,
            "m.audio": AudioMessageContent,
            "m.image": ImageMessageContent,
            "m.video": VideoMessageContent,
        }

        content_model = msgtype_mapper.get(msgtype)
        if not content_model:
            raise UnsupportedMessageContentType(
                f"Unsupported message content type {msgtype}"
            )

        return content_model(**content)


class InReplyTo(BaseModel):
    event_id: str


class RelatesTo(BaseModel):
    in_reply_to: Optional[InReplyTo] = Field(default=None, alias="m.in_reply_to")


# different types of contents
class TextMessageContent(BaseModel):
    body: str
    msgtype: str
    relates_to: Optional[RelatesTo] = Field(default=None, alias="m.relates_to")


class AudioMessageContent(BaseModel):
    url: str
    body: str
    msgtype: str
    relates_to: Optional[RelatesTo] = Field(default=None, alias="m.relates_to")


class ImageMessageContent(BaseModel):
    url: str
    body: str
    msgtype: str
    relates_to: Optional[RelatesTo] = Field(default=None, alias="m.relates_to")


class NoticeMessageContent(BaseModel):
    body: str
    msgtype: str
    relates_to: Optional[RelatesTo] = Field(default=None, alias="m.relates_to")


class VideoMessageContent(BaseModel):
    url: str
    body: str
    msgtype: str
    relates_to: Optional[RelatesTo] = Field(default=None, alias="m.relates_to")
