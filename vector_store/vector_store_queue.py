from datetime import timedelta

from queue_controller import QueueController
from .vector_store import VectorStore


class VectorStoreQueue:

    def __init__(self):
        self.queue_controller = QueueController()
        self.vector_store_queue = self.queue_controller.get_queue("vector_store")
        self.vector_store_worker = self.queue_controller.get_worker("vector_store")

        self.vector_store = VectorStore()

    def enqueue_message(self, parsed_message):
        """
        Add a parsed message to the vector store queue in order to be processed

        Args:
            parsed_message (ParsedMessage): event_processor.database.models.ParsedMessage object
        """
        return self.vector_store_queue.enqueue(
            self.vector_store.process_message,
            kwargs={"parsed_message": parsed_message},
        )

    def enqueue_room_initialisation(self, room_id: str, delay: timedelta = None):
        """
        Queue a room initialisation task. This checks to see if there are existing documents in the vectorstore for the room
        if not then it'll 'initialise' by creating documents.

        Args:
            room_id (str): room_id
        """
        if delay:
            return self.vector_store_queue.enqueue_in(
                delay, self.vector_store.initialise_room, room_id
            )

        return self.vector_store_queue.enqueue(
            self.vector_store.initialise_room, room_id
        )

    def run_worker(self):
        """
        Run a worker to process events in the event processor queue
        """
        self.vector_store_worker.work()
