from .vector_store_queue import VectorStoreQueue


class VectorStoreInterface:

    def __init__(self):
        self.vector_store_queue = VectorStoreQueue()

    def enqueue_message(self, parsed_message):
        return self.vector_store_queue.enqueue_message(parsed_message)

    def run_worker(self):
        self.vector_store_queue.run_worker()
