from .event_queue import EventProcessorQueue
from .event_backfiller import EventBackfiller
from .event_listener import EventListener


class EventProcessorInterface:

    def __init__(self):
        self.event_backfiller = EventBackfiller()
        self.event_listener = EventListener()

    def backfill(self):
        self.event_backfiller.process_unprocessed_events()

    def run_event_listener(self):
        self.event_listener.run()

    def run_event_processor_worker(self):
        self.event_processor_queue.run_worker()
