from vector_store import VectorStoreInterface
from llm_service import LLMInterface

from logger import Logger
from .prompts import JokeSuggestionPrompt
from .database import models
from .database.repositories import SuggestionsRepository


class Suggestions:

    def __init__(self):
        logger_instance = Logger()
        self.logger = logger_instance.get_logger(name=__class__.__name__)
        self.vector_store = VectorStoreInterface()
        self.llm = LLMInterface()

        self.suggestions_repository = SuggestionsRepository()

    def generate_jokes(self, room_id: str, until_message_event_id: str = None):

        self.logger.info(f"Generating joke for room id: {room_id}")

        # TODO: replace with enum class
        suggestion_type = "joke"

        # get most recent message transcripts
        # ordering by timestamp desc returns the most recent messages on top
        transcript = self.vector_store.get_transcripts_by_room_id(
            room_id,
            order_by_timestamp_asc=False,
            limit=30,
            until_message_event_id=until_message_event_id,
        )
        # order transcripts in the right direction
        transcript = sorted(transcript, key=lambda x: x.message_timestamp)
        most_recent_message_event_id = transcript[-1].event_id

        most_recent_messages = "\n".join([message.transcript for message in transcript])

        # pass most recent messages to prompt
        prompt = JokeSuggestionPrompt()
        formatted_prompt = prompt.format(transcript=most_recent_messages)

        # send the prompt to the llm queue
        job = self.llm.enqueue_completion_request(
            formatted_prompt,
            request_reference_type="most_recent_message_event_id",
            request_reference=most_recent_message_event_id,
            on_success=self.process_suggestion_on_success,
            on_failure=self.report_failure,
            meta={
                "most_recent_message_event_id": most_recent_message_event_id,
                "room_id": room_id,
                "suggestion_type": suggestion_type,
                "input_prompt": formatted_prompt,
                "prompt_class": prompt,
                "request_reference_type": "most_recent_message_event_id",
                "request_reference": most_recent_message_event_id,
            },
        )
        self.logger.info(
            f"Joke prompt completion request enqueued for room id: {room_id} and job id: {job.id}"
        )

        return job

    @staticmethod
    def process_suggestion_on_success(job, connection, result, *args, **kawargs):
        """
        Insert suggestion into the database once the job is returned from the llm.
        I'm using RQ's on_success feature so when the embedding task is done, this function will trigger

        https://python-rq.org/docs/#success-callback
        """

        logger_instance = Logger()
        logger = logger_instance.get_logger(__class__.__name__)

        logger.info(
            f"Received suggestion result for room id: {job.meta['room_id']} and job id: {job.id}"
        )

        # insert into the database
        # send to wheverever it needs to be sent
        print(result)

        suggestions_repository = SuggestionsRepository()

        prompt_class = job.meta["prompt_class"]
        parsed_suggestions = prompt_class.parse_response(result)

        #### TODO: JOKES DON'T SEEM FUNNY TRY INSERTING THE INPUT PROMPT INTO CHATGPT AND OPTIMISE
        # insert suggestion into the database
        suggestions_object = models.Suggestions(
            room_id=job.meta["room_id"],
            most_recent_message_event_id=job.meta["most_recent_message_event_id"],
            input_prompt=job.meta["input_prompt"],
            llm_request_reference=job.meta["request_reference"],
            llm_request_reference_type=job.meta["request_reference_type"],
            suggestion_type=job.meta["suggestion_type"],
            suggestions=parsed_suggestions,
        )

        suggestions_repository.create(suggestions_object)
        logger.info(f"Suggestion inserted for room id: {job.meta['room_id']}")

    @staticmethod
    def report_failure(job, connection, type, value, traceback):
        # log failed suggestion requests
        # add them to the database?
        logger_instance = Logger()
        logger = logger_instance.get_logger(__class__.__name__)

        logger.error(f"Suggestion task failed with error message: {traceback}")
