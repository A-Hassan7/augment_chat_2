# transcribe a parsed message
# replace matrix usernames with profile names
# store transcribed messages into a table
import re

from event_processor import ParsedMessage, EventProcessorInterface
from .database.repositories import MatrixProfilesRepository, TranscriptsRepository
from .database.models import Transcript


class Transcriber:

    # used to replace matrix user_ids in message content
    MATRIX_USER_ID_REGEX = r"@.*?:matrix\.localhost\.me"

    def __init__(self):

        self.matrix_profiles_repository = MatrixProfilesRepository()
        self.transcripts_repository = TranscriptsRepository()
        self.event_processor = EventProcessorInterface()

        # cache matrix user_id to profiles mapping
        self.matrix_user_id_to_profile_map = {}

    def transcribe(
        self,
        parsed_message: ParsedMessage,
        insert_into_database=True,
        exclude_reply_thread=False,
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

        transcript = f"{author}: {content}"

        # handle messages that are replies to previous messages
        in_reply_to_event_id = parsed_message.in_reply_to_event_id
        if in_reply_to_event_id:

            # reply messages are structured awkwardly in synapse
            # filter the content for the response message
            reply_message = self._get_reply_message(content)
            content = reply_message

            if not exclude_reply_thread:
                # get the message to which the response is posted
                # this creates a chain if the reply is a reply to another reply ect.
                in_reply_to_prefix = self._get_in_reply_to_prefix(in_reply_to_event_id)

                # add prefix to the transcript
                # Example:
                # <Reply to> Bob: What time?
                # Dan: does 5 pm work?
                transcript = f"{in_reply_to_prefix}\n{author}: {reply_message}"

            else:
                transcript = f"{author}: {reply_message}"

        if insert_into_database:
            self._insert_into_database(
                parsed_message=parsed_message,
                transcript=transcript,
                sender_matrix_display_name=author,
                message_body=content,
            )

        return transcript

    def _get_reply_message(self, content):
        """
        Messages created in response to other messages are formatted differently by synapse
        the format includes the message that is being responded to

        e.g.
        > <Bob> Original message\n\nResponse message'

        the syntanx looks a bit like this -> <sender> <sender content>\n\n<response body>

        I need to filter out the other stuff and grab only the reply message

        Args:
            content (str): body of the reply message that needs fixing

        Returns:
            str: reply message
        """

        # ?P<name> is the syntax used to name groups in re
        # https://safjan.com/python-regex-named-groups/
        reply_message_pattern = (
            r"^> <(?P<og_author>.*?)> (?P<og_message>.*?)\n\n(?P<reply>.*)$"
        )
        reply_message_dict = re.match(reply_message_pattern, content)
        reply = reply_message_dict.group("reply")

        return reply

    def _get_in_reply_to_prefix(self, in_reply_to_event_id):
        """
        Create a prefix for a reply message.

        Example:

        Bob: What time?

        <Reply to> Bob: What time?
        Dan: does 5pm work?

        Args:
            in_reply_to_event_id (str): event_id of the message being replied to

        Returns:
            str: A prefix string for the reply message
        """

        transcript = self.transcripts_repository.get_by_event_id(in_reply_to_event_id)

        # transcribe the message if it hasn't been yet
        if not transcript:
            # get from event processor and create transcript
            parsed_message = self.event_processor.get_parsed_message_by_event_id(
                in_reply_to_event_id
            )
            transcript = self.transcribe(parsed_message, exclude_reply_thread=True)

        return f"<Reply to> {transcript.sender_matrix_display_name}: {transcript.body}"

    def _insert_into_database(
        self,
        parsed_message: ParsedMessage,
        transcript: str,
        sender_matrix_display_name: str,
        message_body: str,
    ):
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
            sender_matrix_display_name=sender_matrix_display_name,
            message_timestamp=parsed_message.message_timestamp,
            depth=parsed_message.depth,
            transcript=transcript,
            body=message_body,
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
