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

    def backfill(self, room_id: str = None):
        # no room id will result in all events being processed
        self.event_backfiller.process_unprocessed_events(room_id)

    def run_event_listener(self):
        self.event_listener.run()

    def run_event_processor_worker(self):
        self.event_processor_queue.run_worker()

    def get_parsed_messages(self, room_id):
        return self.parsed_messages_repository.get_by_room_id(room_id)

    def get_parsed_message_by_event_id(self, event_id):
        return self.parsed_messages_repository.get_by_event_id(event_id)

    def get_all_room_ids(self):
        return self.parsed_messages_repository.get_unique_room_ids()
