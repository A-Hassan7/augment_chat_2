from rq import Callback
from .llm_queue import LLMQueue


class LLMInterface:

    def __init__(self):
        self.llm_queue = LLMQueue()

    def enqueue_embedding_request(self, text, on_success, meta=None):
        """
        Send an embedding request to the queue

        Args:
            text (str): text to embedd
            on_success (func): function to execute when the job is completed
        """
        # turn on success function into RQ callback object
        if not isinstance(on_success, Callback):
            on_success = Callback(on_success)

        return self.llm_queue.enqueue_embedding_request(
            text, on_success=on_success, meta=meta
        )

    def enqueue_completion_request(
        self, prompt, on_success, on_failure=None, meta=None
    ):
        """
        Send completion request to the queue

        Args:
            prompt (str): the prompt
            on_success (func): function to execute when the job is completed
            meta (dict): metadata to pass to the job
        """
        # turn on success function into RQ callback object
        if not isinstance(on_success, Callback):
            on_success = Callback(on_success)

        return self.llm_queue.enqueue_completion_request(
            prompt, on_success=on_success, on_failure=on_failure, meta=meta
        )
