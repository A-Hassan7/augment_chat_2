"""
Pydantic models for API request/response validation.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


# ============================================================
# Authentication Models
# ============================================================


class LoginRequest(BaseModel):
    username: str = Field(..., description="Username for login")


class LoginResponse(BaseModel):
    user_id: int
    username: str
    matrix_user_id: Optional[str]
    message: str = "Login successful"


class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)


class UserListItem(BaseModel):
    id: int
    username: str
    matrix_user_id: Optional[str]
    created_at: Optional[datetime]


# ============================================================
# User Models
# ============================================================


class UserProfile(BaseModel):
    id: int
    username: str
    matrix_user_id: Optional[str]
    matrix_password: Optional[str]
    bridge_count: int = 0
    room_count: int = 0
    created_at: Optional[datetime]


class UserStatus(BaseModel):
    user_id: int
    username: str
    matrix_user_id: Optional[str]
    bridge_count: int
    room_count: int
    bridges: List[Dict[str, Any]]
    recent_activity: List[Dict[str, Any]] = []


# ============================================================
# Bridge Models
# ============================================================


class CreateBridgeRequest(BaseModel):
    service: str = Field(
        ..., description="Bridge service type (whatsapp, discord, etc.)"
    )
    credentials: Optional[Dict[str, Any]] = Field(
        default={}, description="Service-specific credentials"
    )


class BridgeLoginRequest(BaseModel):
    phone_number: str = Field(..., description="Phone number in international format")


class BridgeResponse(BaseModel):
    bridge_id: str
    orchestrator_id: str
    service: str
    status: str
    matrix_bot_username: Optional[str]
    owner_matrix_username: str
    created_at: Optional[datetime]
    connection_data: Optional[Dict[str, Any]] = None


class BridgeStatusResponse(BaseModel):
    bridge_id: str
    service: str
    live_status: Optional[str]
    ready_status: Optional[str]
    last_status_update: Optional[datetime]
    matrix_bot_username: Optional[str]
    created_at: Optional[datetime]


# ============================================================
# Room Models
# ============================================================


class RoomListItem(BaseModel):
    room_id: str
    platform: str
    bridge_id: str
    last_message_at: Optional[datetime]
    message_count: Optional[int] = 0
    transcript_backfilled: bool = False


class RoomDetails(BaseModel):
    room_id: str
    platform: str
    bridge_id: str
    last_message_at: Optional[datetime]
    transcript_backfilled: bool


class MessageItem(BaseModel):
    event_id: str
    room_id: str
    sender: str
    body: str
    timestamp: datetime
    message_type: str = "m.text"


class MessagesResponse(BaseModel):
    room_id: str
    messages: List[MessageItem]
    total_count: int
    page: int
    page_size: int


# ============================================================
# Suggestion Models
# ============================================================


class GenerateSuggestionRequest(BaseModel):
    suggestion_type: str = Field(
        default="joke", description="Type of suggestion (joke, sarcasm, context)"
    )
    until_message_event_id: Optional[str] = None


class SuggestionItem(BaseModel):
    id: int
    text: str
    score: Optional[float] = None


class SuggestionResponse(BaseModel):
    job_id: str
    status: str
    room_id: str
    suggestion_type: str
    suggestions: Optional[List[SuggestionItem]] = None


# ============================================================
# Generic Response Models
# ============================================================


class SuccessResponse(BaseModel):
    status: str = "success"
    message: str
    data: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    status: str = "error"
    message: str
    detail: Optional[str] = None
