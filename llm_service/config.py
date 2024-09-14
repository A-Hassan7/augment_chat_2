import os

from dotenv import load_dotenv

load_dotenv("llm_service/.env.llm_service")


class OpenAIConfig:

    API_KEY = os.environ.get("OPENAI_API_KEY")
