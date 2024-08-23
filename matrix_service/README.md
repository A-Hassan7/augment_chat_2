# Matrix Client

This is a custom helper API that will help manage the matrix synapse server. Functions will include:

- Registering users
- Managing user credentials
- Creating bridge accounts

Done:
- [x] Register users on the homserver
- [x] Whatsapp Bridge Bot
  - [x] Create login request and return login code

Todo:
- [] Create API endpoints to register users externally
- [] Migrate to [https://github.com/beeper/bridge-manager](Beeper Bridge Manager)


### Create user and login into whatsapp bridge

```python
import asyncio
from matrix_client import MatrixClient
from whatsapp_bridge_client import WhatsappBridgeClient

matrix_client = MatrixClient()
whatsapp_client = WhatsappBridgeClient()

username = 'test_account'

# register the username with the matrix homserver
asyncio.run(matrix_client.register_user(username))

# create a login request with the whatsapp bridge
code = asyncio.run(whatsapp_client.login(username, '+447419787402'))

print(code)
```