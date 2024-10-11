from abc import ABC, abstractmethod
from ast import literal_eval

from logger import Logger


class BasePrompt(ABC):
    prompt: str
    input_variables: list

    def format(self, **kwargs):
        for key in self.input_variables:
            if key not in kwargs:
                raise ValueError(f"Missing required input variable: {key}")
        return self.prompt.format(**kwargs)

    @abstractmethod
    def parse_response(self, response):
        """
        Parse the response from the LLM for this prompt

        Args:
            response (str): response string
        """
        pass


class JokeSuggestionPrompt(BasePrompt):
    prompt = """I want you to provide conversational joke suggestions as a responses to the most recent messages. I want to jokes to sound like they are coming from one of the participants and are part of the conversation. I don't want the jokes to sound like dad jokes from the internet, rather the jokes should be witty, sarcastic and unexpected.

Here is an example of a conversation:

{transcript}

Use my instructions to provide 5 joke suggestions based on the most recent message. Return the suggestions a json object with "jokes" as the key. Do not include the author label in the suggestions.
    """
    input_variables = ["transcript"]

    def parse_response(self, response):

        logger_instance = Logger()
        logger = logger_instance.get_logger(__class__.__name__)

        try:
            json = literal_eval(response.replace("```json", "").replace("```", ""))
            jokes = json["jokes"]
        except ValueError as e:
            logger.error(f"Response could not be parsed, try re-generating. {e}")
            raise ValueError("Response could not be parsed, try re-generating")

        return jokes
