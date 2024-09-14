from .llm_queue import LLMQueue


class LLMInterface:

    def __init__(self):
        self.llm_queue = LLMQueue()

    def enqueue_embedding_request(self, text, on_success, meta):
        """
        Send an embedding request to the queue

        Args:
            text (str): text to embedd
            on_success (func): function to execute when the job is completed
        """
        return self.llm_queue.enqueue_embedding_request(
            text, on_success=on_success, meta=meta
        )
