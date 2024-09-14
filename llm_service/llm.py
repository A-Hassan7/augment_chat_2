from .providers import OpenAIProvider


class LLM:

    def __init__(self):
        self.provider = OpenAIProvider()

    @staticmethod
    def create_embedding(text):
        self = LLM()
        return self.provider.create_embedding(text)

    def generate(self):
        pass
