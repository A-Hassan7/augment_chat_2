from openai import OpenAI

from .config import OpenAIConfig


class OpenAIProvider:

    def __init__(self):
        # credentials n stuff
        self.client = OpenAI(api_key=OpenAIConfig.API_KEY)
        self.embeddings_model = "text-embedding-3-small"

    def create_embedding(self, text):
        result = self.client.embeddings.create(
            input=[text], model=self.embeddings_model
        )
        return result.data[0].embedding

    def generate(self):
        pass
