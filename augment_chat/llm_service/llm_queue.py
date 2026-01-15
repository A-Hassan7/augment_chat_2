from queue_controller import QueueController

from .llm import LLM


class LLMQueue:

    def __init__(self):
        self.queue_controller = QueueController()
        self.llm_queue = self.queue_controller.get_queue("llm")
        self.llm_worker = self.queue_controller.get_worker("llm")

        self.llm = LLM()

    def enqueue_embedding_request(
        self,
        text,
        request_reference_type: str,
        request_reference: str,
        on_success,
        meta,
    ):
        """
        Create an embedding task

        Args:
            text (str): text to embed
            on_success (func): function to execute when the job is completed
        """
        return self.llm_queue.enqueue(
            self.llm.create_embedding,
            kwargs={
                "text": text,
                "request_reference_type": request_reference_type,
                "request_reference": request_reference,
            },
            on_success=on_success,
            meta=meta,
        )

    def enqueue_completion_request(
        self,
        prompt,
        request_reference_type: str,
        request_reference: str,
        on_success,
        meta,
        **kwargs
    ):
        """
        Create a completion task

        Args:
            prompt (str): the prompt
            request_reference_type (str): type of the request reference
            request_reference (str): the request reference
            on_success (func): function to execute on success
            meta (dict): metadata to add to the job
        """
        return self.llm_queue.enqueue(
            self.llm.create_completion,
            kwargs={
                "prompt": prompt,
                "request_reference_type": request_reference_type,
                "request_reference": request_reference,
            },
            on_success=on_success,
            meta=meta,
            **kwargs,
        )

    def run_worker(self):
        """
        Run a worker to process events in the event processor queue
        """
        self.llm_worker.work()
