import os

from dotenv import load_dotenv

load_dotenv(".env")


class OpenAIConfig:

    API_KEY = os.environ.get("OPENAI_API_KEY")
