from pydantic import BaseModel, Field, field_validator


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

        msgtype = content.get("msgtype")
        if msgtype == "m.text":
            return TextMessageContent(**content)
        if msgtype == "m.audio":
            return AudioMessageContent(**content)
        if msgtype == "m.image":
            return ImageMessageContent(**content)
        if msgtype == "m.notice":
            return NoticeMessageContent(**content)
        else:
            raise ValueError(f"Unsupported message content type {msgtype}")


# different types of contents
class TextMessageContent(BaseModel):
    body: str
    msgtype: str
    m_mentions: dict = Field(alias="m.mentions")


class AudioMessageContent(BaseModel):
    url: str
    body: str
    info: dict
    msgtype: str
    m_mentions: dict = Field(alias="m.mentions")


class ImageMessageContent(BaseModel):
    url: str
    body: str
    info: dict
    msgtype: str
    m_mentions: dict = Field(alias="m.mentions")


class NoticeMessageContent(BaseModel):
    body: str
    format: str
    msgtype: str
    formatted_body: str
