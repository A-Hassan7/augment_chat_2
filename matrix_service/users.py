# TODO: load the relevent data needed from the matrix synapse database
# username
# access_tokens
# bridges

from matrix_service.database.repositories import AccessTokensRepository


class MatrixUser:

    def __init__(self, user_id: str):
        """
        Initialise an instance of the user using the full user_id including the matrix homserver name

        Args:
            username (str): username
        """

        self.user_id = user_id

    @property
    def access_token(self):
        """_description_
        Get an access token for this user from the matrix database
        """
        access_token_repository = AccessTokensRepository()
        access_tokens = access_token_repository.get_by_user_id(self.user_id)
        if not access_tokens:
            return

        return access_tokens[0].token
