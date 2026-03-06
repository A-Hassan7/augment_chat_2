"""
Bridge Manager Appservice - Pure proxy layer for Matrix bridges.

This service acts as a transparent proxy between the homeserver and bridge instances.
It handles authentication, bridge discovery, token management, and request forwarding.

No orchestration or management logic - just routing and proxying.

Key responsibilities:
- Log all incoming requests, outgoing requests, and responses
- Proxy requests between bridges and homeserver with token adjustment
- Identify which bridge a request should be routed to
"""

import asyncio
from typing import Optional
import httpx
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import JSONResponse

from config import BRIDGE_MANAGER_CONFIG
from bridge_manager.logger import BridgeLogger, RequestTracker
from bridge_manager.appservice.models import RequestSource
from bridge_manager.appservice.router import BridgeRouter
from bridge_manager.appservice.registry import BridgeRegistry
from bridge_manager.appservice.token_manager import TokenManager
from bridge_manager.appservice.handlers import (
    ProxyContext,
    BridgeHandlerRegistry,
    HomeserverHandlerRegistry,
)
from bridge_manager.database.repositories import BridgeManagerWorkerRepository
from bridge_manager.errors import (
    BridgeNotFoundError,
    BridgeRoutingError,
    AuthenticationError,
)

# How often (in seconds) each instance updates its heartbeat in the DB
_HEARTBEAT_INTERVAL = 30


app = FastAPI(
    title="Bridge Manager Appservice",
    description="Proxy layer for Matrix bridge traffic",
    version="1.0.0",
)

# Initialize components
logger = BridgeLogger()
token_manager = TokenManager()

# Background task handle
_heartbeat_task: Optional[asyncio.Task] = None


async def _heartbeat_loop():
    """Periodically refresh last_heartbeat for this instance."""
    while True:
        await asyncio.sleep(_HEARTBEAT_INTERVAL)
        try:
            BridgeManagerWorkerRepository.update_heartbeat(
                BRIDGE_MANAGER_CONFIG.INSTANCE_ID
            )
        except Exception as e:
            logger.log_error(f"Heartbeat update failed: {e}")


@app.on_event("startup")
async def startup_event():
    """Initialize appservice on startup."""
    global _heartbeat_task
    logger.log_info("Bridge Manager Appservice starting...")
    logger.log_info(
        f"Listening on {BRIDGE_MANAGER_CONFIG.HOST}:{BRIDGE_MANAGER_CONFIG.PORT}"
    )

    # Register this instance in bridge_manager_workers
    try:
        BridgeManagerWorkerRepository.get_or_create(
            instance_id=BRIDGE_MANAGER_CONFIG.INSTANCE_ID,
            host=BRIDGE_MANAGER_CONFIG.HOST,
            port=BRIDGE_MANAGER_CONFIG.PORT,
            homeserver_id=BRIDGE_MANAGER_CONFIG.HOMESERVER_ID,
        )
        logger.log_info(f"Worker registered: {BRIDGE_MANAGER_CONFIG.INSTANCE_ID}")
    except Exception as e:
        logger.log_error(f"Failed to register worker in DB: {e}")

    # Start periodic heartbeat
    _heartbeat_task = asyncio.create_task(_heartbeat_loop())


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    global _heartbeat_task
    logger.log_info("Bridge Manager Appservice shutting down...")

    # Stop heartbeat loop
    if _heartbeat_task:
        _heartbeat_task.cancel()
        try:
            await _heartbeat_task
        except asyncio.CancelledError:
            pass

    # Mark this instance as inactive
    try:
        BridgeManagerWorkerRepository.update_status(
            BRIDGE_MANAGER_CONFIG.INSTANCE_ID, "inactive"
        )
        logger.log_info(f"Worker deregistered: {BRIDGE_MANAGER_CONFIG.INSTANCE_ID}")
    except Exception as e:
        logger.log_error(f"Failed to deregister worker in DB: {e}")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "bridge_manager_appservice"}


@app.api_route(
    "/homeserver/_matrix/app/v1/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
)
async def proxy_from_homeserver_to_bridge(path: str, request: Request):
    """
    Proxy all Matrix appservice requests to the appropriate bridge.

    Flow:
    1. Authenticate the request (validate hs_token)
    2. Identify which bridge should handle this request
    3. Adjust authentication token (hs_token → as_token)
    4. Forward request to the bridge
    5. Log request/response
    6. Return bridge's response

    Args:
        path: The path after /_matrix/app/v1/
        request: The incoming FastAPI request

    Returns:
        Response from the bridge
    """
    # Get request body
    body = await request.body()

    # Extract components for routing
    method = request.method
    headers = dict(request.headers)
    query_params = dict(request.query_params)

    # Log every incoming request immediately — before any auth or routing
    request_tracker = RequestTracker(
        source="homeserver",
        method=method,
        path=path,
        query_params=query_params or {},
        headers=headers,
        body=body,
    )

    # Step 1: Authenticate the request
    auth_header = headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        logger.log_error("Missing or invalid Authorization header")
        request_tracker.log_response(
            status_code=401,
            error="Missing or invalid Authorization header",
            response_source="appservice",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )

    incoming_token = auth_header.replace("Bearer ", "")

    # Step 2: Identify which bridge should handle this request
    router = BridgeRouter()

    try:
        bridge, _method = router.identify_bridge(
            source=RequestSource.HOMESERVER,
            headers=headers,
            path=path,
            body=body.decode("utf-8") if body else None,
            query_params=query_params,
        )
    except BridgeNotFoundError as e:
        logger.log_error(f"Bridge identification failed: {e}")
        request_tracker.log_response(
            status_code=404,
            error=f"Bridge identification failed: {e}",
            response_source="appservice",
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Could not identify bridge for this request: {e}",
        )
    except BridgeRoutingError as e:
        logger.log_error(f"Bridge routing error: {e}")
        request_tracker.log_response(
            status_code=500,
            error=f"Bridge routing error: {e}",
            response_source="appservice",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bridge routing error: {e}",
        )

    # Update the log row with bridge context now that we've identified it
    request_tracker.set_bridge_context(bridge_id=bridge.id, discovery_method="router")

    bridge_id = bridge.orchestrator_id

    # Validate incoming token matches the expected hs_token for this bridge
    if not token_manager.validate_hs_token(incoming_token, bridge.hs_token):
        logger.log_error(f"Invalid hs_token for bridge {bridge_id}")
        request_tracker.log_response(
            status_code=403,
            error=f"Invalid hs_token for bridge {bridge_id}",
            response_source="appservice",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid homeserver token",
        )

    # Step 3: Adjust authentication token (hs_token → as_token)
    headers["authorization"] = f"Bearer {bridge.as_token}"

    # Build target URL
    bridge_url = f"http://{BRIDGE_MANAGER_CONFIG.BRIDGE_HOST}:{bridge.port}"
    target_url = f"{bridge_url}/_matrix/app/v1/{path}"

    # Step 4: Apply path-specific transforms via the homeserver request handler
    context = ProxyContext(
        method=method,
        path=path,
        headers=headers,
        query_params=query_params,
        body=body,
        target_url=target_url,
    )
    context = await HomeserverHandlerRegistry.get_handler(bridge.bridge_type).handle(
        context
    )

    # Log the outgoing (forwarded) request, including which handler processed it
    request_tracker.log_outgoing_request(
        method=context.method,
        url=context.target_url,
        headers=context.headers,
        body=context.body,
        query_params=context.query_params,
        handler_name=context.handler_name,
    )

    # Step 5: Forward request to bridge
    logger.log_info(
        f"Proxying {context.method} request to bridge {bridge_id} at {context.target_url}"
    )

    async with httpx.AsyncClient() as client:
        try:
            # Forward the request
            response = await client.request(
                method=context.method,
                url=context.target_url,
                params=context.query_params,
                headers=context.headers,
                content=context.body,
                timeout=30.0,
            )

            # Log response and return
            request_tracker.log_response(
                status_code=response.status_code,
                response_body=response.content,
                response_source="upstream",
            )

            logger.log_info(
                f"Successfully proxied {context.method} request to bridge {bridge_id}, "
                f"status: {response.status_code}"
            )

            return JSONResponse(
                content=response.json(),
                status_code=response.status_code,
            )

        except httpx.ConnectError as e:
            logger.log_error(f"Failed to connect to bridge {bridge_id}: {e}")
            request_tracker.log_response(
                status_code=503, error=str(e), response_source="appservice"
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Bridge {bridge_id} is unavailable",
            )
        except httpx.TimeoutException as e:
            logger.log_error(f"Timeout connecting to bridge {bridge_id}: {e}")
            request_tracker.log_response(
                status_code=504, error=str(e), response_source="appservice"
            )
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"Bridge {bridge_id} timed out",
            )
        except Exception as e:
            logger.log_error(f"Error forwarding request to bridge {bridge_id}: {e}")
            request_tracker.log_response(
                status_code=500, error=str(e), response_source="appservice"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error forwarding request: {e}",
            )


@app.api_route(
    "/bridge/{bridge_id}/_matrix/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
)
async def proxy_from_bridge_to_homeserver(bridge_id: str, path: str, request: Request):
    """
    Proxy requests from bridges to the homeserver.

    Bridges send requests to: http://bridge-manager:5000/bridge/{bridge_id}/_matrix/{path}
    This proxies them to the homeserver after token adjustment.

    Flow:
    1. Authenticate the request (validate as_token from bridge)
    2. Identify which bridge is sending this request (by bridge_id in URL)
    3. Adjust authentication token (as_token → hs_token)
    4. Forward request to the homeserver
    5. Log request/response
    6. Return homeserver's response

    Args:
        bridge_id: The unique bridge identifier
        path: The path after /_matrix/
        request: The incoming FastAPI request

    Returns:
        Response from the homeserver
    """
    # Get request body
    body = await request.body()

    # Extract components
    method = request.method
    headers = dict(request.headers)
    query_params = dict(request.query_params)

    # Log every incoming request immediately — before any auth or routing
    request_tracker = RequestTracker(
        source="bridge",
        method=method,
        path=path,
        query_params=query_params or {},
        headers=headers,
        body=body,
    )

    # Step 1: Authenticate the request
    auth_header = headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        logger.log_error("Missing or invalid Authorization header from bridge")
        request_tracker.log_response(
            status_code=401,
            error="Missing or invalid Authorization header",
            response_source="appservice",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )

    incoming_token = auth_header.replace("Bearer ", "")

    # Step 2: Get bridge by orchestrator ID from URL
    registry = BridgeRegistry()
    bridge = registry.get_bridge_by_orchestrator_id(bridge_id)

    # Fallback: resolve by as_token if bridge_id lookup failed
    if not bridge:
        bridge = registry.get_bridge_by_as_token(incoming_token)
        if bridge:
            logger.log_info(
                f"Resolved bridge by token; URL bridge_id={bridge_id}, "
                f"orchestrator_id={bridge.orchestrator_id}"
            )

    if not bridge:
        logger.log_error(f"Bridge {bridge_id} not found")
        request_tracker.log_response(
            status_code=404,
            error=f"Bridge {bridge_id} not found",
            response_source="appservice",
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bridge {bridge_id} not found",
        )

    # Update the log row with bridge context now that we've identified it
    request_tracker.set_bridge_context(
        bridge_id=bridge.id, discovery_method="url_param"
    )

    # Validate incoming token matches the expected as_token for this bridge
    if not token_manager.validate_as_token(incoming_token, bridge.as_token):
        logger.log_error(f"Invalid as_token from bridge {bridge.id}")
        request_tracker.log_response(
            status_code=403,
            error=f"Invalid as_token from bridge {bridge.id}",
            response_source="appservice",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid bridge token",
        )

    # Step 3: Adjust authentication token (as_token → bridge_manager_as_token)
    # The bridge sends its own as_token; we replace it with the bridge manager's token
    # so the homeserver recognizes this as a legitimate appservice request
    homeserver = bridge.homeserver
    headers["authorization"] = f"Bearer {BRIDGE_MANAGER_CONFIG.AS_TOKEN}"

    # Build target URL to homeserver
    target_url = f"{homeserver.url}/_matrix/{path}"

    # Step 4: Apply path-specific transforms via the bridge request handler
    context = ProxyContext(
        method=method,
        path=path,
        headers=headers,
        query_params=query_params,
        body=body,
        target_url=target_url,
    )
    context = await BridgeHandlerRegistry.get_handler(bridge.bridge_type).handle(
        context
    )

    # Log the outgoing (forwarded) request, including which handler processed it
    request_tracker.log_outgoing_request(
        method=context.method,
        url=context.target_url,
        headers=context.headers,
        body=context.body,
        query_params=context.query_params,
        handler_name=context.handler_name,
    )

    # Step 5: Forward request to homeserver
    logger.log_info(
        f"Proxying {context.method} request from bridge {bridge.id} to homeserver at {context.target_url}"
    )

    async with httpx.AsyncClient() as client:
        try:
            # Forward the request
            response = await client.request(
                method=context.method,
                url=context.target_url,
                params=context.query_params,
                headers=context.headers,
                content=context.body,
                timeout=30.0,
            )

            # Log response and return
            request_tracker.log_response(
                status_code=response.status_code,
                response_body=response.content,
                response_source="upstream",
            )

            logger.log_info(
                f"Successfully proxied {context.method} request from bridge {bridge.id} to homeserver, "
                f"status: {response.status_code}"
            )

            logger.log_info(response.content)

            return JSONResponse(
                content=response.json(),
                status_code=response.status_code,
            )

        except httpx.ConnectError as e:
            logger.log_error(f"Failed to connect to homeserver: {e}")
            request_tracker.log_response(
                status_code=503, error=str(e), response_source="appservice"
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Homeserver is unavailable",
            )
        except httpx.TimeoutException as e:
            logger.log_error(f"Timeout connecting to homeserver: {e}")
            request_tracker.log_response(
                status_code=504, error=str(e), response_source="appservice"
            )
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Homeserver timed out",
            )
        except Exception as e:
            logger.log_error(f"Error forwarding request to homeserver: {e}")
            request_tracker.log_response(
                status_code=500, error=str(e), response_source="appservice"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error forwarding request: {e}",
            )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle any unhandled exceptions."""
    logger.log_error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Internal server error", "detail": str(exc)},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=BRIDGE_MANAGER_CONFIG.HOST,
        port=BRIDGE_MANAGER_CONFIG.PORT,
        log_level="info",
    )
