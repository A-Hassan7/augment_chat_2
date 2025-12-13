# homeserver catchall
# catches all requests from the homesever and sends them to the appropriate bridge
# bridge catch all
# catches all requests from the bridges and sends them to the homeserver
# bridge register
# recognises which bridge the request is from/to
# keeps track of registered bridges
# create/remove bridges

from fastapi import Request, FastAPI, HTTPException
import uvicorn

from .homeserver_service import HomeserverService
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
    # Build RequestContext for the incoming homeserver request and pass it to the service
    request_ctx = await RequestContext.create(
        request=request,
        bridge_manager_config=config,
        source="homeserver",
    )

    return await homeserver_service.handle_request(request_ctx)


@app.api_route(
    "/bridge/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
)
async def bridge_catchall(path, request: Request):
    """
    Catchall endpoint to receive all requests from the bridges
    """

    # Build RequestContext for the incoming bridge request and pass it to the service
    request_ctx = await RequestContext.create(
        request=request,
        bridge_manager_config=config,
        source="bridge",
    )

    return await request_ctx.bridge.handle_request(request_ctx)


if __name__ == "__main__":
    uvicorn.run(
        app="bridge_manager.appservice.appservice:app",
        host=BridgeManagerConfig.HOST,
        port=BridgeManagerConfig.PORT,
    )
