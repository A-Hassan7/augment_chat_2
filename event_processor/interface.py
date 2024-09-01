from .event_queue import EventProcessorQueue
from .event_backfiller import EventBackfiller
from .event_listener import EventListener
from .database.repositories import ParsedMessagesRepository


class EventProcessorInterface:

    def __init__(self):
        self.event_backfiller = EventBackfiller()
        self.event_listener = EventListener()
        self.event_processor_queue = EventProcessorQueue()
        self.parsed_messages_repository = ParsedMessagesRepository()

    def backfill(self):
        self.event_backfiller.process_unprocessed_events()

    def run_event_listener(self):
        self.event_listener.run()

    def run_event_processor_worker(self):
        self.event_processor_queue.run_worker()

    def get_parsed_messages(self, room_id):
        return self.parsed_messages_repository.get_by_room_id(room_id)
