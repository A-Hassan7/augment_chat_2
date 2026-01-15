# homeserver catchall
# catches all requests from the homesever and sends them to the appropriate bridge
# bridge catch all
# catches all requests from the bridges and sends them to the homeserver
# bridge register
# recognises which bridge the request is from/to
# keeps track of registered bridges
# create/remove bridges

import json

from fastapi import Request, FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

from .homeserver_service import HomeserverService
from .bridge_resolver import BridgeNotFoundError
from ..bridge_registry import BridgeRegistry
from ..config import BridgeManagerConfig
from .models import RequestContext


app = FastAPI()

config = BridgeManagerConfig()
homeserver_service = HomeserverService(bridge_manager_config=config)
bridge_registry = BridgeRegistry(bridge_manager_config=config)


@app.api_route(
    "/homeserver/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
)
async def homeserver_catchall(path, request: Request):
    """
    Catchall endpoint to receive all requests from the homeserver
    """
    request_ctx = None

    # Build RequestContext for the incoming homeserver request and pass it to the service
    try:
        request_ctx = await RequestContext.create(
            request=request,
            bridge_manager_config=config,
            source="homeserver",
        )

        response = await homeserver_service.handle_request(request_ctx)

        # Log the response
        if request_ctx and request_ctx.request_id:
            request_ctx.log_response(response)

        return response

    except BridgeNotFoundError as e:
        # Handle case where bridge cannot be identified
        # For transaction endpoints with no events, return empty success response
        if path.startswith("_matrix/app/v1/transactions/"):
            body = await request.body()
            body = json.loads(body.decode("utf-8"))
            events = body.get("events")
            if not events:
                error_response = JSONResponse(content={}, status_code=200)

                # Log the response if we have a request_ctx
                if request_ctx and request_ctx.request_id:
                    request_ctx.log_response(error_response)

                return error_response

        # Otherwise, return error
        error_response = JSONResponse(content={"error": str(e)}, status_code=404)

        # Log the error response if we have a request_ctx
        if request_ctx and request_ctx.request_id:
            request_ctx.log_response(error_response)

        return error_response

    except Exception as e:
        # Log any other unexpected errors
        error_response = JSONResponse(
            content={"error": f"Internal error: {str(e)}"}, status_code=500
        )

        if request_ctx and request_ctx.request_id:
            request_ctx.log_response(error_response)

        return error_response


@app.api_route(
    "/bridge/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
)
async def bridge_catchall(path, request: Request):
    """
    Catchall endpoint to receive all requests from the bridges
    """
    request_ctx = None

    try:
        # Build RequestContext for the incoming bridge request and pass it to the service
        request_ctx = await RequestContext.create(
            request=request,
            bridge_manager_config=config,
            source="bridge",
        )

        response = await request_ctx.bridge.handle_request(request_ctx)

        # Log the response
        if request_ctx and request_ctx.request_id:
            request_ctx.log_response(response)

        return response

    except BridgeNotFoundError as e:
        error_response = JSONResponse(
            content={"error": f"Bridge not found: {str(e)}"}, status_code=404
        )

        # Log the error response if we have a request_ctx
        if request_ctx and request_ctx.request_id:
            request_ctx.log_response(error_response)

        return error_response

    except Exception as e:
        # Log any other unexpected errors
        error_response = JSONResponse(
            content={"error": f"Internal error: {str(e)}"}, status_code=500
        )

        if request_ctx and request_ctx.request_id:
            request_ctx.log_response(error_response)

        return error_response


if __name__ == "__main__":
    uvicorn.run(
        app="bridge_manager.appservice.appservice:app",
        host=BridgeManagerConfig.HOST,
        port=BridgeManagerConfig.PORT,
    )
