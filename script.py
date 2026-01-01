from user_management_service.register import UserRegister
from user_management_service.bridge_manager import UserBridgeManager

register = UserRegister()
bm = UserBridgeManager()

user = register.register("test4")
bridge = bm.create_bridge(user.matrix_username, "whatsapp")


print(user)
print(bridge)
