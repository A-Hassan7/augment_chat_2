from .database.repositories import TranscriptsRepository
from .vector_store_queue import VectorStoreQueue
from .backfiller import backfill_transcripts


class VectorStoreInterface:

    def __init__(self):
        self.vector_store_queue = VectorStoreQueue()
        self.transcripts_repository = TranscriptsRepository()

    def enqueue_message(self, parsed_message):
        return self.vector_store_queue.enqueue_message(parsed_message)

    def run_worker(self):
        self.vector_store_queue.run_worker()

    def get_transcripts_by_room_id(
        self,
        room_id: str,
        order_by_timestamp_asc: bool = True,
        limit: bool = None,
        until_message_event_id: str = None,
    ):
        return self.transcripts_repository.get_by_room_id(
            room_id, order_by_timestamp_asc, limit, until_message_event_id
        )

    def backfill_room(self, room_ids: list):
        backfill_transcripts(room_ids)
