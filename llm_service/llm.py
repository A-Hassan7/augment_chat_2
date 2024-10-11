from logger import Logger

from .providers import OpenAIProvider


class LLM:
    """
    TODO: log requests sent in the database
    """

    def __init__(self):
        logger_instance = Logger()
        self.logger = logger_instance.get_logger(name=__class__.__name__)
        self.provider = OpenAIProvider()

    @staticmethod
    def create_embedding(text):
        self = LLM()

        self.logger.info(f"Creating embedding request")
        try:
            result = self.provider.create_embedding(text)
            self.logger.info(f"Embedding result returned")
            return result
        except Exception as e:
            self.logger.critical(f"Embedding request failed: {e}")
            raise e

    @staticmethod
    def create_completion(prompt):
        self = LLM()

        self.logger.info(f"Creating completion request")
        try:
            result = self.provider.create_completion(prompt)
            self.logger.info(f"Completion result returned")
            return result
        except Exception as e:
            self.logger.critical(f"Completion request failed: {e}")
            raise e
