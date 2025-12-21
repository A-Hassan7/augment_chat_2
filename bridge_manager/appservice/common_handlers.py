"""
Common Matrix Client API handlers that can be reused across bridge types.

These handlers implement standard Matrix API endpoints that behave the same
way for most bridges, reducing duplication when adding new bridge services.
"""

from __future__ import annotations
import logging
from typing import TYPE_CHECKING

from fastapi.responses import JSONResponse

if TYPE_CHECKING:
    from .models import RequestContext
    from .homeserver_service import HomeserverService
    from fastapi import Response

logger = logging.getLogger(__name__)


class MatrixClientAPIHandlers:
    """
    Reusable handlers for standard Matrix Client API endpoints.

    These are bridge-agnostic implementations that can be used by any
    bridge service. Override specific handlers in bridge subclasses
    if custom behavior is needed.
    """

    @staticmethod
    async def versions(
        request_ctx: RequestContext, homeserver: HomeserverService
    ) -> Response:
        """
        Handle /_matrix/client/versions endpoint.

        Returns Matrix protocol versions supported by the homeserver.
        This is typically the first request bridges make.
        """
        return await homeserver.send_request(
            request_ctx=request_ctx,
            method=request_ctx.request.method,
            path=request_ctx.request.path_params["path"],
            headers=(
                request_ctx.headers
                if request_ctx and request_ctx.headers is not None
                else dict(request_ctx.request.headers)
            ),
        )

    @staticmethod
    async def whoami(
        request_ctx: RequestContext, homeserver: HomeserverService
    ) -> Response:
        """
        Handle /_matrix/client/v3/account/whoami endpoint.

        Bridges use this to verify their identity on the homeserver.
        Returns the user_id of the authenticated user (the bridge bot).
        """
        response = await homeserver.send_request(
            request_ctx=request_ctx,
            method=request_ctx.request.method,
            path=request_ctx.request.path_params["path"],
            headers=(
                request_ctx.headers
                if request_ctx and request_ctx.headers is not None
                else dict(request_ctx.request.headers)
            ),
            query_params=request_ctx.query_params,
        )
        return response

    @staticmethod
    async def media_config(
        request_ctx: RequestContext, homeserver: HomeserverService
    ) -> Response:
        """
        Handle /_matrix/client/v1/media/config endpoint.

        Returns media repository configuration (upload limits, etc.).
        """
        return await homeserver.send_request(
            request_ctx=request_ctx,
            method=request_ctx.request.method,
            path=request_ctx.request.path_params["path"],
            headers=(
                request_ctx.headers
                if request_ctx and request_ctx.headers is not None
                else dict(request_ctx.request.headers)
            ),
        )

    @staticmethod
    async def register(
        request_ctx: RequestContext, homeserver: HomeserverService
    ) -> Response:
        """
        Handle /_matrix/client/v3/register endpoint.

        Allows bridges to register new users on the homeserver.
        Typically used with m.login.application_service type.
        """
        headers = (
            request_ctx.headers.copy()
            if request_ctx and request_ctx.headers is not None
            else dict(request_ctx.request.headers).copy()
        )
        headers.pop("content-length", None)

        return await homeserver.send_request(
            request_ctx=request_ctx,
            method=request_ctx.request.method,
            path=request_ctx.request.path_params["path"],
            headers=headers,
            query_params=request_ctx.query_params,
            json=request_ctx.body_json,
        )

    @staticmethod
    async def profile_avatar_url(
        request_ctx: RequestContext, homeserver: HomeserverService
    ) -> Response:
        """
        Handle /_matrix/client/v3/profile/{userId}/avatar_url endpoint.

        Get or set user avatar URLs.

        For PUT requests, adds the user_id query parameter to enable
        Application Service impersonation per Matrix AS API spec.
        """
        import re

        path = request_ctx.request.path_params.get("path")

        # Extract user_id from path: /profile/{userId}/avatar_url
        match = re.search(r"/profile/(@[^/]+)/", path)
        user_id = match.group(1) if match else None

        headers = (
            request_ctx.headers.copy()
            if request_ctx and request_ctx.headers is not None
            else dict(request_ctx.request.headers).copy()
        )
        headers.pop("content-length", None)

        # Add user_id query parameter for AS impersonation
        query_params = (
            request_ctx.query_params.copy() if request_ctx.query_params else {}
        )
        if user_id and request_ctx.request.method.upper() == "PUT":
            query_params["user_id"] = user_id
            logger.info(f"Adding user_id query param for avatar_url: {user_id}")

        return await homeserver.send_request(
            request_ctx=request_ctx,
            method=request_ctx.request.method,
            path=path,
            headers=headers,
            json=request_ctx.body_json,
            query_params=query_params,
        )

    @staticmethod
    async def profile_displayname(
        request_ctx: RequestContext, homeserver: HomeserverService
    ) -> Response:
        """
        Handle /_matrix/client/v3/profile/{userId}/displayname endpoint.

        Get or set user display names.
        """
        path = request_ctx.request.path_params.get("path")

        query_params = (
            request_ctx.query_params.copy()
            if request_ctx and request_ctx.query_params is not None
            else dict(request_ctx.request.query_params)
        )

        headers = (
            request_ctx.headers.copy()
            if request_ctx and request_ctx.headers is not None
            else dict(request_ctx.request.headers).copy()
        )
        headers.pop("content-length", None)

        return await homeserver.send_request(
            request_ctx=request_ctx,
            method=request_ctx.request.method,
            path=path,
            headers=headers,
            query_params=query_params,
            json=request_ctx.body_json,
        )

    @staticmethod
    async def sync(
        request_ctx: RequestContext, homeserver: HomeserverService
    ) -> Response:
        """
        Handle /_matrix/client/v3/sync endpoint.

        Long-polling endpoint for receiving events.
        """
        return await homeserver.send_request(
            request_ctx=request_ctx,
            method=request_ctx.request.method,
            path=request_ctx.request.path_params["path"],
            headers=(
                request_ctx.headers
                if request_ctx and request_ctx.headers is not None
                else dict(request_ctx.request.headers)
            ),
            query_params=request_ctx.query_params,
        )

    @staticmethod
    async def room_send(
        request_ctx: RequestContext, homeserver: HomeserverService
    ) -> Response:
        """
        Handle /_matrix/client/v3/rooms/{roomId}/send/{eventType}/{txnId} endpoint.

        Send events to rooms.
        """
        headers = (
            request_ctx.headers.copy()
            if request_ctx and request_ctx.headers is not None
            else dict(request_ctx.request.headers).copy()
        )
        headers.pop("content-length", None)

        return await homeserver.send_request(
            request_ctx=request_ctx,
            method=request_ctx.request.method,
            path=request_ctx.request.path_params["path"],
            headers=headers,
            json=request_ctx.body_json,
        )

    @staticmethod
    async def room_state(
        request_ctx: RequestContext, homeserver: HomeserverService
    ) -> Response:
        """
        Handle /_matrix/client/v3/rooms/{roomId}/state/{eventType} endpoint.

        Get or send state events.
        """
        headers = (
            request_ctx.headers.copy()
            if request_ctx and request_ctx.headers is not None
            else dict(request_ctx.request.headers).copy()
        )
        headers.pop("content-length", None)

        return await homeserver.send_request(
            request_ctx=request_ctx,
            method=request_ctx.request.method,
            path=request_ctx.request.path_params["path"],
            headers=headers,
            json=request_ctx.body_json,
        )

    # i
    @staticmethod
    async def media_download(
        request_ctx: RequestContext, homeserver: HomeserverService
    ) -> Response:
        """
        Handle /_matrix/client/v1/media/download/{serverName}/{mediaId} endpoint.

        Bridges use this to download media from the homeserver's media repository.
        The response is typically binary data (image, video, file, etc.).
        """
        path = request_ctx.request.path_params.get("path")

        return await homeserver.send_request(
            request_ctx=request_ctx,
            method=request_ctx.request.method,
            path=path,
            headers=(
                request_ctx.headers
                if request_ctx and request_ctx.headers is not None
                else dict(request_ctx.request.headers)
            ),
            query_params=request_ctx.query_params,
        )

    @staticmethod
    async def media_upload(
        request_ctx: RequestContext, homeserver: HomeserverService
    ) -> Response:
        """
        Handle /_matrix/client/v1/media/upload endpoint.

        Bridges use this to upload media to the homeserver.
        """
        path = request_ctx.request.path_params.get("path")

        headers = (
            request_ctx.headers.copy()
            if request_ctx and request_ctx.headers is not None
            else dict(request_ctx.request.headers).copy()
        )
        # Keep content-type for media uploads, but remove content-length
        headers.pop("content-length", None)

        # Get raw body bytes for media upload
        body_bytes = await request_ctx.request.body()

        return await homeserver.send_request(
            request_ctx=request_ctx,
            method=request_ctx.request.method,
            path=path,
            headers=headers,
            data=body_bytes,
            query_params=request_ctx.query_params,
        )

    @staticmethod
    async def room_join(
        request_ctx: RequestContext, homeserver: HomeserverService
    ) -> Response:
        """
        Handle /_matrix/client/v3/rooms/{roomId}/join endpoint.

        Bridges use this to join rooms on behalf of their users.

        Per Matrix spec:
        - This endpoint starts a user participating in a particular room
        - Optional body fields: reason (string), third_party_signed (object)
        - Returns: {"room_id": "!room:example.org"}
        - Supports user_id query parameter for AS impersonation

        Flow:
        1. Bridge sends POST /rooms/{roomId}/join?user_id={bridged_user}
        2. Bridge Manager forwards to homeserver with proper authentication
        3. Homeserver processes join and returns room_id
        4. Bridge Manager passes response back to bridge
        """
        import re

        path = request_ctx.request.path_params.get("path")

        # Extract room_id from path for logging
        match = re.search(r"/rooms/([^/]+)/join", path)
        room_id = match.group(1) if match else "unknown"

        # Prepare headers (remove content-length for recomputation)
        headers = (
            request_ctx.headers.copy()
            if request_ctx and request_ctx.headers is not None
            else dict(request_ctx.request.headers).copy()
        )
        headers.pop("content-length", None)

        # Preserve query parameters (user_id for AS impersonation)
        query_params = (
            request_ctx.query_params.copy() if request_ctx.query_params else {}
        )

        # Extract user_id from query params for logging
        user_id = query_params.get("user_id", "not specified")
        logger.info(f"Room join request: room={room_id}, user={user_id}")

        # Forward to homeserver with optional body (reason, third_party_signed)
        return await homeserver.send_request(
            request_ctx=request_ctx,
            method=request_ctx.request.method,
            path=path,
            headers=headers,
            json=request_ctx.body_json if request_ctx.body_json else None,
            query_params=query_params,
        )

    @staticmethod
    async def room_state_all(
        request_ctx: RequestContext, homeserver: HomeserverService
    ) -> Response:
        """
        Handle GET /_matrix/client/v3/rooms/{roomId}/state endpoint.

        Bridges use this to get all state events for a room.

        Per Matrix spec:
        - Returns array of state events (m.room.member, m.room.name, etc.)
        - User must be joined to the room or have previously been joined
        - Supports user_id query parameter for AS impersonation

        Flow:
        1. Bridge sends GET /rooms/{roomId}/state?user_id={bridged_user}
        2. Bridge Manager forwards to homeserver with proper authentication
        3. Homeserver returns array of all state events
        4. Bridge Manager passes response back to bridge
        """
        import re

        path = request_ctx.request.path_params.get("path")

        # Extract room_id from path for logging
        match = re.search(r"/rooms/([^/]+)/state$", path)
        room_id = match.group(1) if match else "unknown"

        # Preserve query parameters (user_id for AS impersonation)
        query_params = (
            request_ctx.query_params.copy() if request_ctx.query_params else {}
        )

        # Extract user_id from query params for logging
        user_id = query_params.get("user_id", "not specified")
        logger.info(f"Room state request: room={room_id}, user={user_id}")

        # Forward to homeserver (GET request, no body)
        return await homeserver.send_request(
            request_ctx=request_ctx,
            method=request_ctx.request.method,
            path=path,
            headers=(
                request_ctx.headers
                if request_ctx and request_ctx.headers is not None
                else dict(request_ctx.request.headers)
            ),
            query_params=query_params,
        )

    @staticmethod
    async def room_members(
        request_ctx: RequestContext, homeserver: HomeserverService
    ) -> Response:
        """
        Handle GET /_matrix/client/v3/rooms/{roomId}/members endpoint.

        Bridges use this to get member list for a room.

        Per Matrix spec:
        - Returns chunk array of m.room.member events
        - User must be joined to the room or have previously been joined
        - Supports optional query parameters:
          - at: server_name or event ID to get historical membership
          - membership: filter by membership state (join, invite, leave, ban)
          - not_membership: exclude membership state
          - user_id: for AS impersonation

        Flow:
        1. Bridge sends GET /rooms/{roomId}/members?user_id={bridged_user}
        2. Bridge Manager forwards to homeserver with proper authentication
        3. Homeserver returns {chunk: [m.room.member events]}
        4. Bridge Manager passes response back to bridge
        """
        import re

        path = request_ctx.request.path_params.get("path")

        # Extract room_id from path for logging
        match = re.search(r"/rooms/([^/]+)/members", path)
        room_id = match.group(1) if match else "unknown"

        # Preserve all query parameters
        query_params = (
            request_ctx.query_params.copy() if request_ctx.query_params else {}
        )

        # Extract user_id from query params for logging
        user_id = query_params.get("user_id", "not specified")
        membership_filter = query_params.get("membership", "all")
        logger.info(
            f"Room members request: room={room_id}, user={user_id}, filter={membership_filter}"
        )

        # Forward to homeserver (GET request, no body)
        return await homeserver.send_request(
            request_ctx=request_ctx,
            method=request_ctx.request.method,
            path=path,
            headers=(
                request_ctx.headers
                if request_ctx and request_ctx.headers is not None
                else dict(request_ctx.request.headers)
            ),
            query_params=query_params,
        )

    @staticmethod
    async def room_send_event(
        request_ctx: RequestContext, homeserver: HomeserverService
    ) -> Response:
        """
        Handle PUT /_matrix/client/v3/rooms/{roomId}/send/{eventType}/{txnId} endpoint.

        Bridges use this to send events (messages, reactions, etc.) to rooms.

        Per Matrix spec:
        - PUT request with event content in body
        - Returns {event_id: "$event_id"}
        - txnId must be unique per sender to enable idempotency
        - Supports user_id query parameter for AS impersonation
        - Event types include: m.room.message, m.reaction, m.room.redaction, etc.

        Flow:
        1. Bridge sends PUT /rooms/{roomId}/send/{eventType}/{txnId}?user_id={bridged_user}
        2. Bridge Manager forwards to homeserver with proper authentication
        3. Homeserver creates event and returns {event_id}
        4. Bridge Manager passes response back to bridge
        """
        import re

        path = request_ctx.request.path_params.get("path")

        # Extract room_id, event_type, and txnId from path for logging
        match = re.search(r"/rooms/([^/]+)/send/([^/]+)/(.+)$", path)
        if match:
            room_id = match.group(1)
            event_type = match.group(2)
            txn_id = match.group(3)
        else:
            room_id = event_type = txn_id = "unknown"

        # Preserve query parameters (user_id for AS impersonation)
        query_params = (
            request_ctx.query_params.copy() if request_ctx.query_params else {}
        )

        # Extract user_id from query params for logging
        user_id = query_params.get("user_id", "not specified")

        # Log basic info about the message being sent
        body_preview = ""
        if request_ctx.body_json and isinstance(request_ctx.body_json, dict):
            if "body" in request_ctx.body_json:
                body_text = request_ctx.body_json["body"]
                body_preview = (
                    f", body='{body_text[:50]}...'"
                    if len(body_text) > 50
                    else f", body='{body_text}'"
                )

        logger.info(
            f"Send event: room={room_id}, type={event_type}, txn={txn_id}, user={user_id}{body_preview}"
        )

        # Store room-bridge mapping for future discovery
        # This allows us to route transaction events back to the correct bridge
        if (
            request_ctx.bridge
            and hasattr(request_ctx.bridge, "bridge_id")
            and room_id != "unknown"
        ):
            from ..database.repositories import RoomBridgeMappingRepository

            try:
                RoomBridgeMappingRepository().upsert(
                    room_id=room_id, bridge_id=request_ctx.bridge.bridge_id
                )
                logger.debug(
                    f"Stored room-bridge mapping: room={room_id}, bridge_id={request_ctx.bridge.bridge_id}"
                )
            except Exception as e:
                logger.warning(f"Failed to store room-bridge mapping: {e}")

        headers = (
            request_ctx.headers
            if request_ctx and request_ctx.headers is not None
            else dict(request_ctx.request.headers)
        )
        headers.pop("content-length", None)

        # Forward to homeserver (PUT request with JSON body)
        return await homeserver.send_request(
            request_ctx=request_ctx,
            method=request_ctx.request.method,
            path=path,
            headers=headers,
            json=request_ctx.body_json if request_ctx.body_json else None,
            query_params=query_params,
        )


class AppserviceAPIHandlers:
    """
    Handlers for Application Service API endpoints.

    These endpoints are called by bridges to interact with the homeserver
    as an application service.
    """

    @staticmethod
    async def ping(
        request_ctx: RequestContext,
        homeserver: HomeserverService,
        bridge_config,
    ) -> Response:
        """
        Handle /_matrix/client/v1/appservice/{appserviceId}/ping endpoint.

        Bridges send pings to verify connectivity with the homeserver.
        The transaction_id in the ping is stored for routing future requests.
        """
        import json
        from ..database.repositories import TransactionMappingsRepository

        body_json = request_ctx.body_json if request_ctx else None
        if not body_json:
            raise ValueError("Missing or invalid JSON body")

        transaction_id = body_json.get("transaction_id")
        if not transaction_id:
            raise ValueError("Transaction ID missing")

        body = json.dumps(body_json)

        # Replace bridge-specific appservice ID with bridge_manager ID
        path = request_ctx.request.path_params.get("path")
        import re

        path = re.sub(r"(_bridge_manager__)[^/]+", rf"{bridge_config.ID}", path)

        headers = (
            request_ctx.headers.copy()
            if request_ctx and request_ctx.headers is not None
            else dict(request_ctx.request.headers).copy()
        )
        headers.pop("content-length", None)

        # Store transaction mapping for future routing
        bridge = request_ctx.bridge
        TransactionMappingsRepository().upsert(
            transaction_id, bridge_as_token=bridge.as_token, bridge_id=bridge.bridge_id
        )

        return await homeserver.send_request(
            request_ctx=request_ctx,
            method=request_ctx.request.method,
            path=path,
            headers=headers,
            data=body,
        )
