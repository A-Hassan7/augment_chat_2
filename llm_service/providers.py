from openai import OpenAI

from .config import OpenAIConfig


class OpenAIProvider:

    def __init__(self):
        # credentials n stuff
        self.client = OpenAI(api_key=OpenAIConfig.API_KEY)
        self.embeddings_model = "text-embedding-3-small"
        self.completions_model = "gpt-4o"

    def create_embedding(self, text):
        result = self.client.embeddings.create(
            input=[text], model=self.embeddings_model
        )
        return result.data[0].embedding

    def create_completion(self, prompt):
        completion = self.client.chat.completions.create(
            model=self.completions_model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
        )
        return completion.choices[0].message.content
