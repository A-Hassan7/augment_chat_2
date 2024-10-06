from .providers import OpenAIProvider


class LLM:
    """
    TODO: log requests sent in the database
    """

    def __init__(self):
        self.provider = OpenAIProvider()

    @staticmethod
    def create_embedding(text):
        self = LLM()
        return self.provider.create_embedding(text)

    @staticmethod
    def create_completion(prompt):
        self = LLM()
        return self.provider.create_completion(prompt)
