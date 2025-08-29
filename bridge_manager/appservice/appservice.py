# homeserver catchall
# catches all requests from the homesever and sends them to the appropriate bridge
# bridge catch all
# catches all requests from the bridges and sends them to the homeserver
# bridge register
# recognises which bridge the request is from/to
# keeps track of registered bridges
# create/remove bridges

from fastapi import Request, FastAPI
import uvicorn

from .homeserver_service import HomeserverService
from .bridge_registry import BridgeRegistry
from ..config import BridgeManagerConfig

"""

+---------------------+
|   FastAPI App       |
+---------------------+
        |
        | 1. Request from Homeserver
        v
+---------------------+
| /homeserver/{path}  |  <--- Catchall endpoint for homeserver
+---------------------+
        |
        v
+---------------------+
| HomeserverService   |  <--- Handles homeserver requests
+---------------------+
        |
        v
+---------------------+
| BridgeRegistry      |  <--- Finds the correct bridge service
+---------------------+
        |
        v
+---------------------+
| BridgeService       |  <--- Base class (e.g. WhatsappBridgeService)
+---------------------+
        |
        v
+---------------------+
| Proxy to Bridge     | 
+---------------------+

------------------------------------------------------------

        |
        | 2. Request from Bridge
        v
+---------------------+
| /bridge/{path}      |  <--- Catchall endpoint for bridges
+---------------------+
        |
        v
+---------------------+
| BridgeRegistry      |  <--- Finds the correct bridge service
+---------------------+
        |
        v
+---------------------+
| BridgeService       |  <--- Base class (e.g. WhatsappBridgeService)
+---------------------+
        |
        v
+---------------------+
| Proxy to Homeserver | 
+---------------------+

"""


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
    return await homeserver_service.handle_request(request)


@app.api_route(
    "/bridge/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
)
async def homeserver_catchall(path, request: Request):
    """
    Catchall endpoint to receive all requests from the bridges
    """
    as_token = request._headers["authorization"]
    as_token = as_token.replace("Bearer ", "")

    # find the bridge service based on the AS token in the request
    bridge_service = bridge_registry.get_bridge(as_token)
    return await bridge_service.handle_request(request)


if __name__ == "__main__":
    uvicorn.run("bridge_manager.appservice.appservice:app")
