# Defines the interface for other modules to interact with the matrix service
# this helps abstract things away from the actual logic and create a public facing interface

from matrix_service.matrix_client import MatrixClient


class MatrixServiceInterface:

    def __init__(self):
        self.matrix_client = MatrixClient()

    async def register_user(self, username):
        user = await self.matrix_client.register_user(username)
        return user.user_id
