"""
User Management API Routes.
All operations go through the UserManagementInterface ONLY.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Path
from fastapi.responses import JSONResponse

from user_management_service.interface import UserManagementInterface
from user_management_service.errors import (
    UserAlreadyExistsError,
    BridgeAccessDeniedError,
    BridgeCreationError,
    BridgeLoginError,
    InvalidBridgeServiceError,
)

from .models import (
    LoginRequest,
    LoginResponse,
    CreateUserRequest,
    UserListItem,
    UserProfile,
    UserStatus,
    CreateBridgeRequest,
    BridgeLoginRequest,
    BridgeResponse,
    BridgeStatusResponse,
    RoomListItem,
    RoomDetails,
    MessagesResponse,
    MessageItem,
    GenerateSuggestionRequest,
    SuggestionResponse,
    SuccessResponse,
    ErrorResponse,
)

router = APIRouter(prefix="/api", tags=["user-management"])

# Single interface instance
user_mgmt = UserManagementInterface()


# ============================================================
# AUTHENTICATION ROUTES
# ============================================================


@router.post("/auth/login", response_model=LoginResponse)
def login(request: LoginRequest):
    """
    Simple username-only login for testing.
    Returns user info if user exists.
    """
    user = user_mgmt.get_user_by_username(request.username)

    if not user:
        raise HTTPException(
            status_code=404, detail=f"User '{request.username}' not found"
        )

    return LoginResponse(
        user_id=user.id,
        username=user.username,
        matrix_user_id=user.matrix_username,
        message="Login successful",
    )


@router.get("/auth/users", response_model=List[UserListItem])
def list_users():
    """Get list of all users for quick switching."""
    users = user_mgmt.list_users()

    return [
        UserListItem(
            id=user.id,
            username=user.username,
            matrix_user_id=user.matrix_username,
            created_at=getattr(user, "created_at", None),
        )
        for user in users
    ]


@router.post("/auth/users", response_model=LoginResponse)
def create_user(request: CreateUserRequest):
    """Create a new user."""
    try:
        user = user_mgmt.create_user(username=request.username)

        return LoginResponse(
            user_id=user.id,
            username=user.username,
            matrix_user_id=user.matrix_username,
            message="User created successfully",
        )
    except UserAlreadyExistsError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create user: {str(e)}")


# ============================================================
# USER ROUTES
# ============================================================


@router.get("/users/{user_id}", response_model=UserProfile)
def get_user_profile(user_id: int = Path(..., description="User ID")):
    """Get user profile information."""
    user = user_mgmt.get_user(user_id)

    if not user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    # Get bridge count
    bridges = user_mgmt.list_bridges(user_id)

    # TODO: Get room count from interface
    room_count = 0

    return UserProfile(
        id=user.id,
        username=user.username,
        matrix_user_id=user.matrix_username,
        matrix_password=user.matrix_password,
        bridge_count=len(bridges),
        room_count=room_count,
        created_at=getattr(user, "created_at", None),
    )


@router.get("/users/{user_id}/status", response_model=UserStatus)
def get_user_status(user_id: int = Path(..., description="User ID")):
    """Get comprehensive user status including bridges and rooms."""
    try:
        status = user_mgmt.get_user_status(user_id)
        if not status:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")

        return UserStatus(**status)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get user status: {str(e)}"
        )


@router.delete("/users/{user_id}", response_model=SuccessResponse)
def delete_user(user_id: int = Path(..., description="User ID")):
    """Delete a user and all associated data."""
    try:
        user_mgmt.delete_user(user_id)
        return SuccessResponse(message="User deleted successfully")
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete user: {str(e)}")


@router.get("/users/{user_id}/export")
def export_user_data(user_id: int = Path(..., description="User ID")):
    """Export all user data (GDPR compliance)."""
    try:
        data = user_mgmt.export_user_data(user_id)
        return data
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to export user data: {str(e)}"
        )


# ============================================================
# BRIDGE ROUTES
# ============================================================


@router.get("/users/{user_id}/bridges", response_model=List[BridgeResponse])
def list_user_bridges(user_id: int = Path(..., description="User ID")):
    """List all bridges for a user."""
    try:
        bridges = user_mgmt.list_bridges(user_id)

        return [
            BridgeResponse(
                bridge_id=str(b.id),
                orchestrator_id=b.orchestrator_id,
                service=b.bridge_service,
                status=b.live_status or "unknown",
                matrix_bot_username=b.matrix_bot_username,
                owner_matrix_username=b.owner_matrix_username,
                created_at=b.created_at,
            )
            for b in bridges
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list bridges: {str(e)}")


@router.post("/users/{user_id}/bridges", response_model=BridgeResponse)
def create_bridge(
    user_id: int = Path(..., description="User ID"), request: CreateBridgeRequest = None
):
    """Create a new bridge for a user."""
    try:
        bridge = user_mgmt.create_bridge(
            user_id, service=request.service, credentials=request.credentials
        )

        return BridgeResponse(
            bridge_id=str(bridge.id),
            orchestrator_id=bridge.orchestrator_id,
            service=bridge.bridge_service,
            status=bridge.live_status or "created",
            matrix_bot_username=bridge.matrix_bot_username,
            owner_matrix_username=bridge.owner_matrix_username,
            created_at=bridge.created_at,
            connection_data=request.credentials,
        )
    except (BridgeCreationError, InvalidBridgeServiceError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to create bridge: {str(e)}"
        )


@router.post("/users/{user_id}/bridges/{bridge_id}/login", response_model=dict)
def login_to_bridge(
    user_id: int = Path(..., description="User ID"),
    bridge_id: str = Path(..., description="Bridge orchestrator ID"),
    request: BridgeLoginRequest = None,
):
    """Login to a bridge (e.g., WhatsApp with phone number)."""
    try:
        result = user_mgmt.login_bridge(
            user_id, bridge_id, phone_number=request.phone_number
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except BridgeAccessDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except BridgeLoginError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to login to bridge: {str(e)}"
        )


@router.get(
    "/users/{user_id}/bridges/{bridge_id}/status", response_model=BridgeStatusResponse
)
def get_bridge_status(
    user_id: int = Path(..., description="User ID"),
    bridge_id: str = Path(..., description="Bridge orchestrator ID"),
):
    """Get current status of a bridge."""
    try:
        status = user_mgmt.get_bridge_status(user_id, bridge_id)
        return BridgeStatusResponse(**status)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get bridge status: {str(e)}"
        )


@router.delete("/users/{user_id}/bridges/{bridge_id}", response_model=SuccessResponse)
def delete_bridge(
    user_id: int = Path(..., description="User ID"),
    bridge_id: str = Path(..., description="Bridge orchestrator ID"),
):
    """Delete a bridge."""
    try:
        user_mgmt.delete_bridge(user_id, bridge_id)
        return SuccessResponse(message="Bridge deleted successfully")
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to delete bridge: {str(e)}"
        )


# ============================================================
# ROOM ROUTES
# ============================================================


@router.get("/users/{user_id}/rooms", response_model=List[RoomListItem])
def list_user_rooms(
    user_id: int = Path(..., description="User ID"),
    platform: Optional[str] = Query(None, description="Filter by platform"),
):
    """List all rooms for a user."""
    try:
        rooms = user_mgmt.list_rooms(user_id, platform=platform)
        return rooms
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list rooms: {str(e)}")


@router.get("/users/{user_id}/rooms/{room_id}", response_model=RoomDetails)
def get_room_details(
    user_id: int = Path(..., description="User ID"),
    room_id: str = Path(..., description="Room ID"),
):
    """Get details for a specific room."""
    try:
        details = user_mgmt.get_room_details(user_id, room_id)
        return details
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get room details: {str(e)}"
        )


@router.get(
    "/users/{user_id}/rooms/{room_id}/messages", response_model=MessagesResponse
)
def get_room_messages(
    user_id: int = Path(..., description="User ID"),
    room_id: str = Path(..., description="Room ID"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Messages per page"),
):
    """Get messages for a room with pagination."""
    try:
        messages = user_mgmt.get_room_messages(
            user_id, room_id, page=page, page_size=page_size
        )
        return MessagesResponse(**messages)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get messages: {str(e)}")


@router.post(
    "/users/{user_id}/rooms/{room_id}/backfill", response_model=SuccessResponse
)
def backfill_room(
    user_id: int = Path(..., description="User ID"),
    room_id: str = Path(..., description="Room ID"),
):
    """Trigger transcript backfill for a room."""
    try:
        user_mgmt.backfill_room(user_id, room_id)
        return SuccessResponse(message="Room backfill started")
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to backfill room: {str(e)}"
        )


# ============================================================
# SUGGESTION ROUTES
# ============================================================


@router.post(
    "/users/{user_id}/rooms/{room_id}/suggestions", response_model=SuggestionResponse
)
def generate_suggestion(
    user_id: int = Path(..., description="User ID"),
    room_id: str = Path(..., description="Room ID"),
    request: GenerateSuggestionRequest = None,
):
    """Generate a suggestion for a room."""
    try:
        result = user_mgmt.generate_suggestion(
            user_id,
            room_id,
            suggestion_type=request.suggestion_type,
            until_event_id=request.until_message_event_id,
        )
        return result
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to generate suggestion: {str(e)}"
        )


@router.get(
    "/users/{user_id}/rooms/{room_id}/suggestions",
    response_model=List[SuggestionResponse],
)
def get_room_suggestions(
    user_id: int = Path(..., description="User ID"),
    room_id: str = Path(..., description="Room ID"),
):
    """Get recent suggestions for a room."""
    try:
        suggestions = user_mgmt.get_room_suggestions(user_id, room_id)
        return suggestions
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get suggestions: {str(e)}"
        )


@router.get("/suggestions/job/{job_id}", response_model=SuggestionResponse)
def get_suggestion_job_status(job_id: str = Path(..., description="Job ID")):
    """Poll status of a suggestion generation job."""
    try:
        status = user_mgmt.get_suggestion_job_status(job_id)
        return status
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get job status: {str(e)}"
        )
