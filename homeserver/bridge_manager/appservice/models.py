"""
Pydantic models for request/response validation and data transfer.
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class BridgeDiscoveryMethod(str, Enum):
    """Methods for identifying which bridge a request belongs to."""

    AUTH_TOKEN = "auth_token"
    PATH_USERNAME = "path_username"
    QUERY_USER_ID = "query_user_id"
    TRANSACTION_ID = "transaction_id"
    TRANSACTION_EVENTS = "transaction_events"
    ROOM_ID = "room_id"
    BODY_USERNAME = "body_username"
    OWNER_USERNAME = "owner_username"
    UNKNOWN = "unknown"


class RequestSource(str, Enum):
    """Source of a request."""

    HOMESERVER = "homeserver"
    BRIDGE = "bridge"


class BridgeStatus(str, Enum):
    """Bridge status states."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    PROVISIONING = "provisioning"
    ERROR = "error"
    DELETED = "deleted"


# Request/Response Models


class CreateBridgeRequest(BaseModel):
    """Request to create a new bridge."""

    bridge_type: str = Field(..., description="Type of bridge (whatsapp, meta, etc.)")
    owner_matrix_username: str = Field(
        ..., description="Matrix user who owns this bridge"
    )
    homeserver_id: str = Field(..., description="Homeserver ID this bridge belongs to")
    bridge_manager_id: Optional[str] = Field(
        None, description="Bridge manager instance ID"
    )
    docker_host: str = Field(default="local", description="Docker host to deploy on")


class BridgeResponse(BaseModel):
    """Response containing bridge information."""

    id: int
    orchestrator_id: str
    bridge_type: str
    container_name: str
    host: str
    port: int
    homeserver_id: str
    bridge_manager_id: str
    matrix_bot_username: str
    owner_matrix_username: str
    status: str
    created_at: datetime


class DeleteBridgeRequest(BaseModel):
    """Request to delete a bridge."""

    bridge_id: int


class BridgeLoginRequest(BaseModel):
    """Request to login to a bridge."""

    bridge_id: int
    credentials: Dict[str, Any] = Field(default_factory=dict)


class BridgeLoginResponse(BaseModel):
    """Response from bridge login attempt."""

    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class BridgeStatusResponse(BaseModel):
    """Response containing bridge status."""

    bridge_id: int
    bridge_type: str
    connected: bool
    logged_in: bool
    info: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class ListBridgesResponse(BaseModel):
    """Response containing list of bridges."""

    bridges: List[BridgeResponse]
    total: int


# Request Context Models


class RequestContextData(BaseModel):
    """Data for request context during proxying."""

    request_id: str
    source: RequestSource
    direction: str  # inbound/outbound
    bridge_id: Optional[int] = None
    discovery_method: Optional[BridgeDiscoveryMethod] = None
    method: str
    path: str
    query_params: Optional[Dict[str, Any]] = None
    headers: Optional[Dict[str, str]] = None
    body: Optional[Dict[str, Any]] = None
    forwarded_to: Optional[str] = None


# Homeserver Models


class CreateHomeserverRequest(BaseModel):
    """Request to register a homeserver."""

    id: str
    name: str
    url: str
    hs_token: str


class HomeserverResponse(BaseModel):
    """Response containing homeserver information."""

    id: str
    name: str
    url: str
    created_at: datetime


# Bridge Manager Worker Models


class RegisterWorkerRequest(BaseModel):
    """Request to register a bridge manager worker."""

    instance_id: str
    host: str
    port: int
    homeserver_id: str


class WorkerResponse(BaseModel):
    """Response containing worker information."""

    id: int
    instance_id: str
    host: str
    port: int
    homeserver_id: str
    status: str
    last_heartbeat: Optional[datetime]


# Error Models


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str
    detail: Optional[str] = None
    request_id: Optional[str] = None
