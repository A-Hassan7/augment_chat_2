# transcribe a parsed message
# replace matrix usernames with profile names
# store transcribed messages into a table
import re

from event_processor import ParsedMessage
from .database.repositories import MatrixProfilesRepository, TranscriptsRepository
from .database.models import Transcript


class Transcriber:

    # used to replace matrix user_ids in message content
    MATRIX_USER_ID_REGEX = r"@[A-Za-z0-9]+:matrix\.localhost\.me"

    def __init__(self):

        self.matrix_profiles_repository = MatrixProfilesRepository()
        self.transcripts_repository = TranscriptsRepository()

        # cache matrix user_id to profiles mapping
        self.matrix_user_id_to_profile_map = {}

    def transcribe(
        self, parsed_message: ParsedMessage, insert_into_database=True
    ) -> str:
        """
        Convert a parsed message object into a transcript representation.

        Transcripts will be inserted into the database.

        Args:
            parsed_message (ParsedMessage): ParsedMessage object

        Returns:
            : _description_
        """

        # remove microseconds from timestamp
        timestamp = parsed_message.message_timestamp.replace(microsecond=0)

        # replace matrix user_id with profile name
        # e.g. user@matrix.localhost.me -> Bob
        author = (
            self._get_matrix_display_name_from_user_id(parsed_message.sender)
            or parsed_message.sender
        )

        # replace any references of the matrix user id with a profile displayname
        content = parsed_message.body
        matrix_user_ids = re.findall(self.MATRIX_USER_ID_REGEX, content)
        for matrix_user_id in matrix_user_ids:
            content = content.replace(
                matrix_user_id,
                self._get_matrix_display_name_from_user_id(matrix_user_id),
            )

        transcript = f"{timestamp} - {author}: {content}"

        if insert_into_database:
            self._insert_into_database(parsed_message, transcript)

        return transcript

    def _insert_into_database(self, parsed_message: ParsedMessage, transcript: str):
        """
        Insert transcript into the vector_store.transcripts table in the database

        Args:
            parsed_message (_type_): _description_
            transcript (_type_): _description_
        """

        # ignore if event_id already exists in database
        existing_transcript = self.transcripts_repository.get_by_event_id(
            parsed_message.event_id
        )
        if existing_transcript:
            return

        transcript_object = Transcript(
            event_id=parsed_message.event_id,
            room_id=parsed_message.room_id,
            sender_matrix_user_id=parsed_message.sender,
            message_timestamp=parsed_message.message_timestamp,
            depth=parsed_message.depth,
            transcript=transcript,
        )
        self.transcripts_repository.create(transcript_object)

    def _get_matrix_display_name_from_user_id(self, matrix_user_id: str) -> str:
        """
        Takes a matrix user_id and returns a profile display name using the replicated profiles table.

        The function will first check if the mapping between user_id and profile exists in cache.

        Args:
            matrix_user_id (str): matrix user id

        Returns:
            str: displayname
        """

        # check existing cached profile for user id
        profile = self.matrix_user_id_to_profile_map.get(matrix_user_id)
        if not profile:
            # get from replication of matrix profiles table
            profile = self.matrix_profiles_repository.get_by_matrix_user_id(
                matrix_user_id
            )
            # cache results
            self.matrix_user_id_to_profile_map[matrix_user_id] = profile

        return profile.displayname
