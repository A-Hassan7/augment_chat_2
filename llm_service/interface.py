from rq import Callback
from .llm_queue import LLMQueue


class LLMInterface:

    def __init__(self):
        self.llm_queue = LLMQueue()

    def enqueue_embedding_request(
        self,
        text,
        request_reference_type: str,
        request_reference: str,
        on_success,
        meta=None,
    ):
        """
        Send an embedding request to the queue

        Args:
            text (str): text to embedd
            request_reference_type (str): request reference type for the LLM module to log
            request_reference (str): request reference for the LLM module to log. This will help log where the results came from.
            on_success (func): function to execute when the job is completed
        """
        # turn on success function into RQ callback object
        if not isinstance(on_success, Callback):
            on_success = Callback(on_success)

        return self.llm_queue.enqueue_embedding_request(
            text,
            request_reference_type=request_reference_type,
            request_reference=request_reference,
            on_success=on_success,
            meta=meta,
        )

    def enqueue_completion_request(
        self,
        prompt,
        request_reference_type,
        request_reference,
        on_success,
        on_failure=None,
        meta=None,
    ):
        """
        Send completion request to the queue

        Args:
            prompt (str): the prompt
            request_reference_type (str): request reference type for the LLM module to log
            request_reference (str): request reference for the LLM module to log. This will help log where the results came from.
            on_success (func): function to execute when the job is completed
            on_failure (func): function to execute when the job fails
            meta (dict): metadata to pass to the job
        """
        # turn on success function into RQ callback object
        if not isinstance(on_success, Callback):
            on_success = Callback(on_success)

        return self.llm_queue.enqueue_completion_request(
            prompt,
            request_reference_type=request_reference_type,
            request_reference=request_reference,
            on_success=on_success,
            on_failure=on_failure,
            meta=meta,
        )

    def run_worker(self):
        self.llm_queue.run_worker()
