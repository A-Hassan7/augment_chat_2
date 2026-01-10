from user_management_service.register import UserRegister
from user_management_service.bridge_manager import UserBridgeManager

register = UserRegister()
bm = UserBridgeManager()

# Create user and bridge
# user = register.register("whatsapp_test_1")
# user = register.get_user_by_matrix_username(
#     "@436419fe-d4b3-4468-b9ee-74a87c93063a:matrix.localhost.me"
# )
# bridge = bm.create_bridge(user=user, service="whatsapp")
# print(user)
# print(bridge)

# Get user
user = register.get_user_by_matrix_username(
    "@35205c39-d0c1-41be-b7f2-fba72c471012:matrix.localhost.me"
)
# bridge = bm.create_bridge(user=user, service="whatsapp")

# print(user)

# Get bridges for user
bridges = bm.list_bridges(user)
[
    print(bridge.id, bridge.orchestrator_id, bridge.bridge_service, bridge.as_token)
    for bridge in bridges
]

bridge = bridges[0]
# bm.delete_bridge(user, bridge)
bm.login(user=user, bridge=bridge, phone_number="+447419787402")
