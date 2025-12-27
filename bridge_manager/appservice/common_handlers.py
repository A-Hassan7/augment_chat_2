"""Common Matrix Client API handlers that can be reused across bridge types.

These handlers implement standard Matrix API endpoints that behave the same
way for most bridges, reducing duplication when adding new bridge services.
"""

from __future__ import annotations
from typing import TYPE_CHECKING
import httpx

from fastapi.responses import JSONResponse
from logger import Logger

if TYPE_CHECKING:
    from .models import RequestContext
    from .homeserver_service import HomeserverService
    from fastapi import Response

logger = Logger().get_logger(__name__)


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
    async def room_state_event(
        request_ctx: RequestContext, homeserver: HomeserverService
    ) -> Response:
        """
        Handle GET /_matrix/client/v3/rooms/{roomId}/state/{eventType}/{stateKey} endpoint.

        Get a specific state event from a room (e.g., m.room.power_levels).

        Per Matrix spec:
        - Returns the content of the specified state event
        - eventType: The type of state to look up (e.g., m.room.power_levels)
        - stateKey: The state_key of the event (often empty string "")
        - User must have access to the room
        - Supports user_id query parameter for AS impersonation

        Flow:
        1. Bridge sends GET /rooms/{roomId}/state/{eventType}/{stateKey}?user_id={bridged_user}
        2. Bridge Manager forwards to homeserver with proper authentication
        3. Homeserver returns the state event content
        4. Bridge Manager passes response back to bridge
        """
        import re

        path = request_ctx.request.path_params.get("path")

        # Extract room_id and event_type from path for logging
        match = re.search(r"/rooms/([^/]+)/state/([^/]+)(?:/(.*))?$", path)
        if match:
            room_id = match.group(1)
            event_type = match.group(2)
            state_key = match.group(3) if match.group(3) is not None else ""
        else:
            room_id = "unknown"
            event_type = "unknown"
            state_key = ""

        # Preserve query parameters (user_id for AS impersonation)
        query_params = (
            request_ctx.query_params.copy() if request_ctx.query_params else {}
        )

        # Extract user_id from query params for logging
        user_id = query_params.get("user_id", "not specified")
        logger.info(
            f"Room state event: room={room_id}, type={event_type}, key='{state_key}', user={user_id}"
        )

        # Prepare headers and remove content-length for GET requests
        headers = (
            request_ctx.headers.copy()
            if request_ctx and request_ctx.headers is not None
            else dict(request_ctx.request.headers).copy()
        )
        headers.pop("content-length", None)

        # Forward to homeserver (GET request, no body)
        return await homeserver.send_request(
            request_ctx=request_ctx,
            method=request_ctx.request.method,
            path=path,
            headers=headers,
            query_params=query_params,
        )

    @staticmethod
    async def room_invite(
        request_ctx: RequestContext, homeserver: HomeserverService
    ) -> Response:
        """
        Handle POST /_matrix/client/v3/rooms/{roomId}/invite endpoint.

        Invite a user to a room.

        Per Matrix spec:
        - Invites a user to participate in a particular room
        - Body must contain: {"user_id": "@user:homeserver.com"}
        - Supports user_id query parameter for AS impersonation
        - User making the invite must have appropriate permissions

        Flow:
        1. Bridge sends POST /rooms/{roomId}/invite?user_id={inviter}
           with body: {"user_id": "@invitee:homeserver.com"}
        2. Bridge Manager forwards to homeserver with proper authentication
        3. Homeserver sends invite and returns {}
        4. Bridge Manager passes response back to bridge
        """
        import json
        import re

        path = request_ctx.request.path_params.get("path")

        # Extract room_id from path for logging
        match = re.search(r"/rooms/([^/]+)/invite", path)
        room_id = match.group(1) if match else "unknown"

        # Get invitee from body
        body_json = request_ctx.body_json if request_ctx else None
        invitee = body_json.get("user_id") if body_json else "unknown"

        # Preserve query parameters (user_id for AS impersonation - the inviter)
        query_params = (
            request_ctx.query_params.copy() if request_ctx.query_params else {}
        )
        inviter = query_params.get("user_id", "not specified")

        logger.info(
            f"Room invite: room={room_id}, inviter={inviter}, invitee={invitee}"
        )

        # Prepare headers
        headers = (
            request_ctx.headers.copy()
            if request_ctx and request_ctx.headers is not None
            else dict(request_ctx.request.headers).copy()
        )
        headers.pop("content-length", None)

        # Prepare body
        body = json.dumps(body_json) if body_json else None

        # Forward to homeserver
        return await homeserver.send_request(
            request_ctx=request_ctx,
            method=request_ctx.request.method,
            path=path,
            headers=headers,
            query_params=query_params,
            data=body,
        )

    @staticmethod
    async def room_join(
        request_ctx: RequestContext, homeserver: HomeserverService
    ) -> Response:
        """
        Handle POST /_matrix/client/v3/rooms/{roomId}/join endpoint.

        Join a room.

        Per Matrix spec:
        - Joins a user to a particular room
        - Body is optional (can be empty {} or contain third_party_signed)
        - Supports user_id query parameter for AS impersonation
        - User must be invited or room must allow joining

        Flow:
        1. Bridge sends POST /rooms/{roomId}/join?user_id={user}
           with body: {} or {"third_party_signed": {...}}
        2. Bridge Manager forwards to homeserver with proper authentication
        3. Homeserver adds user to room and returns {"room_id": "..."}
        4. Bridge Manager passes response back to bridge
        """
        import json
        import re
        from urllib.parse import unquote

        path = request_ctx.request.path_params.get("path")

        # Extract room_id from path for logging
        # match = re.search(r"/rooms/([^/]+)/join", path)
        # room_id = unquote(match.group(1)) if match else "unknown"

        # Preserve query parameters (user_id for AS impersonation)
        query_params = (
            request_ctx.query_params.copy() if request_ctx.query_params else {}
        )
        # user_id = query_params.get("user_id", "not specified")

        # Extract server name from room ID and add to query params if not present
        # Room IDs are in format !localpart:server.name
        # The server_name param tells Matrix which server(s) know about this room
        # if "server_name" not in query_params and ":" in room_id:
        #     server_from_room = room_id.split(":", 1)[1]
        #     query_params["server_name"] = server_from_room
        #     logger.info(f"Added server_name={server_from_room} to join request")

        # logger.info(
        #     f"Room join: room={room_id}, user={user_id}, query_params={query_params}"
        # )

        # Prepare headers
        headers = (
            request_ctx.headers.copy()
            if request_ctx and request_ctx.headers is not None
            else dict(request_ctx.request.headers).copy()
        )
        headers.pop("content-length", None)

        # Prepare body (may be empty)
        body_json = request_ctx.body_json if request_ctx else None
        body = json.dumps(body_json) if body_json is not None else None

        # Forward to homeserver
        return await homeserver.send_request(
            request_ctx=request_ctx,
            method=request_ctx.request.method,
            path=path,
            headers=headers,
            query_params=query_params,
            data=body,
        )

    @staticmethod
    async def room_members(
        request_ctx: RequestContext, homeserver: HomeserverService
    ) -> Response:
        """
        Handle GET /_matrix/client/v3/rooms/{roomId}/members endpoint.

        Get the list of members for a room.

        Per Matrix spec:
        - Returns list of m.room.member state events
        - Supports user_id query parameter for AS impersonation
        - Optional 'at', 'membership', 'not_membership' query parameters

        Flow:
        1. Bridge sends GET /rooms/{roomId}/members?user_id={bridge_user}
        2. Bridge Manager forwards to homeserver with proper authentication
        3. Homeserver returns member list
        4. Bridge Manager passes response back to bridge
        """
        import re

        path = request_ctx.request.path_params.get("path")

        # Extract room_id from path for logging
        match = re.search(r"/rooms/([^/]+)/members", path)
        room_id = match.group(1) if match else "unknown"

        # Preserve query parameters (user_id for AS impersonation, plus filters)
        query_params = (
            request_ctx.query_params.copy() if request_ctx.query_params else {}
        )
        user_id = query_params.get("user_id", "not specified")

        logger.info(f"Room members: room={room_id}, user={user_id}")

        # Prepare headers and remove content-length for GET requests
        headers = (
            request_ctx.headers.copy()
            if request_ctx and request_ctx.headers is not None
            else dict(request_ctx.request.headers).copy()
        )
        headers.pop("content-length", None)

        # Forward to homeserver (GET request, no body)
        return await homeserver.send_request(
            request_ctx=request_ctx,
            method=request_ctx.request.method,
            path=path,
            headers=headers,
            query_params=query_params,
        )

    @staticmethod
    async def capabilities(
        request_ctx: RequestContext, homeserver: HomeserverService
    ) -> Response:
        """
        Handle GET /capabilities - Returns server capabilities
        https://spec.matrix.org/v1.11/client-server-api/#get_matrixclientv3capabilities
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

    @staticmethod
    async def room_create(
        request_ctx: RequestContext, homeserver: HomeserverService
    ) -> Response:
        """
        Handle POST /_matrix/client/v3/createRoom endpoint.

        Bridges use this to create new Matrix rooms (DMs, group chats, etc.).

        Per Matrix spec:
        - POST request with room configuration in body
        - Returns {room_id: "!roomid:homeserver"}
        - Supports extensive configuration:
          - visibility: public/private
          - initial_state: array of state events to set
          - preset: private_chat, public_chat, trusted_private_chat
          - is_direct: boolean for DM indication
          - power_level_content_override: custom power levels
          - invite: array of user IDs to invite
          - name, topic, room_alias_name, etc.
        - Supports user_id query parameter for AS impersonation

        Flow:
        1. Bridge sends POST /createRoom?user_id={bridged_user}
        2. Bridge Manager forwards to homeserver with proper authentication
        3. Homeserver creates room and returns {room_id}
        4. Bridge Manager stores room-bridge mapping
        5. Response passed back to bridge
        """
        path = request_ctx.request.path_params.get("path")

        # Preserve query parameters (user_id for AS impersonation)
        query_params = (
            request_ctx.query_params.copy() if request_ctx.query_params else {}
        )

        # Extract user_id from query params for logging
        user_id = query_params.get("user_id", "not specified")

        # Extract room name from body for logging
        room_name = "unnamed"
        if request_ctx.body_json and isinstance(request_ctx.body_json, dict):
            initial_state = request_ctx.body_json.get("initial_state", [])
            for state_event in initial_state:
                if state_event.get("type") == "m.room.name":
                    room_name = state_event.get("content", {}).get("name", "unnamed")
                    break
            # Fallback to direct name field
            if room_name == "unnamed" and "name" in request_ctx.body_json:
                room_name = request_ctx.body_json["name"]

        is_direct = (
            request_ctx.body_json.get("is_direct", False)
            if request_ctx.body_json
            else False
        )
        room_type = "DM" if is_direct else "room"

        logger.info(f"Create {room_type}: name='{room_name}', user={user_id}")

        headers = (
            request_ctx.headers
            if request_ctx and request_ctx.headers is not None
            else dict(request_ctx.request.headers)
        )
        headers.pop("content-length", None)

        # Forward to homeserver (POST request with JSON body)
        response = await homeserver.send_request(
            request_ctx=request_ctx,
            method=request_ctx.request.method,
            path=path,
            headers=headers,
            json=request_ctx.body_json if request_ctx.body_json else None,
            query_params=query_params,
        )

        # Extract room_id from response and store mapping
        try:
            # Parse response to get room_id
            import json

            response_body = response.body
            if isinstance(response_body, bytes):
                response_body = response_body.decode("utf-8")
            response_data = json.loads(response_body) if response_body else {}

            room_id = response_data.get("room_id")

            if (
                room_id
                and request_ctx.bridge
                and hasattr(request_ctx.bridge, "bridge_id")
            ):
                from ..database.repositories import RoomBridgeMappingRepository

                try:
                    RoomBridgeMappingRepository().upsert(
                        room_id=room_id, bridge_id=request_ctx.bridge.bridge_id
                    )
                    logger.info(
                        f"✓ Created {room_type} and stored mapping: room={room_id}, name='{room_name}'"
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to store room-bridge mapping for {room_id}: {e}"
                    )
        except Exception as e:
            logger.warning(f"Failed to parse createRoom response for mapping: {e}")

        return response

    @staticmethod
    async def capabilities(
        request_ctx: RequestContext, homeserver: HomeserverService
    ) -> Response:
        """
        Handle GET /capabilities - Returns server capabilities
        https://spec.matrix.org/v1.11/client-server-api/#get_matrixclientv3capabilities
        """
        logger.info("Get capabilities")

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
