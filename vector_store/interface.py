from .vector_store_queue import VectorStoreQueue


class VectorStoreInterface:

    def __init__(self):
        self.vector_store_queue = VectorStoreQueue()

    def enqueue_message(self, parsed_message):
        self.vector_store_queue.enqueue_message(parsed_message)
