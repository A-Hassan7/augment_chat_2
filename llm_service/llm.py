from logger import Logger

from .database.models import Request
from .database.repositories import RequestsRepository
from .providers import OpenAIProvider


class LLM:
    """
    TODO: log requests sent in the database
    """

    def __init__(self):
        logger_instance = Logger()
        self.logger = logger_instance.get_logger(name=__class__.__name__)
        self.provider = OpenAIProvider()
        self.requests_repository = RequestsRepository()

    @staticmethod
    def create_embedding(text, request_reference_type: str, request_reference: str):
        self = LLM()

        self.logger.info(f"Creating embedding request")
        try:
            # get embedding
            result = self.provider.create_embedding(text)
            self.logger.info(f"Embedding result returned")

            # insert request and result into database
            request = Request(
                requesting_user_id=None,  # TODO: implement
                request_type="embedding",
                request_reference=request_reference,
                request_reference_type=request_reference_type,
                input=text,
                output=result,
            )
            self.requests_repository.create(request)
            self.logger.info(
                "Embedding request log created with reference type: {reference_type} and reference: {request_reference}"
            )

            return result
        except Exception as e:
            self.logger.critical(f"Embedding request failed: {e}")
            raise e

    @staticmethod
    def create_completion(prompt, request_reference_type: str, request_reference: str):
        self = LLM()

        self.logger.info(f"Creating completion request")
        try:
            result = self.provider.create_completion(prompt)
            self.logger.info(f"Completion result returned")

            # insert request and result into database
            request = Request(
                requesting_user_id=None,  # TODO: implement
                request_type="completion",
                request_reference=request_reference,
                request_reference_type=request_reference_type,
                input=prompt,
                output=result,
            )
            self.requests_repository.create(request)
            self.logger.info(
                "Completion request log created with reference type: {reference_type} and reference: {request_reference}"
            )

            return result
        except Exception as e:
            self.logger.critical(f"Completion request failed: {e}")
            raise e
