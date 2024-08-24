# Defines the interface for other modules to interact with the matrix service
# this helps abstract things away from the actual logic and create a public facing interface

from matrix_service.matrix_client import MatrixClient

class MatrixServiceInterface:

    def __init__(self):
        self.matrix_client = MatrixClient()

    async def register_user(self, username):
        user = await self.matrix_client.register_user(username)
        return user.user_id

    async def create_room(self, username, room_name, is_direct, invite_usernames):
        room_id = await self.matrix_client.create_room(
            username=username,
            room_name=room_name,
            is_direct=is_direct,
            invite_usernames=invite_usernames,
        )
        return room_id

    def get_messages(self, matrix_username, room_id, after_event_id, limit=10):
        messages = self.matrix_client.get_messages(
            mx_username=matrix_username,
            room_id=room_id,
            after_event_id=after_event_id,
            limit=limit
        )
        return messages

    async def send_message(self, username, room_id, message_body):
        event_id = await self.matrix_client.send_message(
            username=username,
            room_id=room_id,
            message_body=message_body
        )
        return event_id
