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
            "m.notice": NoticeMessageContent,
            "m.video": VideoMessageContent,
        }

        content_model = msgtype_mapper.get(msgtype)
        if not content_model:
            raise UnsupportedMessageContentType(
                f"Unsupported message content type {msgtype}"
            )

        return content_model(**content)


# different types of contents
class TextMessageContent(BaseModel):
    body: str
    msgtype: str


class AudioMessageContent(BaseModel):
    url: str
    body: str
    msgtype: str


class ImageMessageContent(BaseModel):
    url: str
    body: str
    msgtype: str


class NoticeMessageContent(BaseModel):
    body: str
    msgtype: str


class VideoMessageContent(BaseModel):
    url: str
    body: str
    msgtype: str
