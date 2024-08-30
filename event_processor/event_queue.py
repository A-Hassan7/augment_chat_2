from queue_controller import QueueController
from .event_processor import EventProcessor


class EventProcessorQueue:

    def __init__(self):
        self.queue_controller = QueueController()
        self.event_processor_queue = self.queue_controller.get_queue("event_processor")
        self.event_processor_worker = self.queue_controller.get_worker(
            "event_processor"
        )

        self.event_processor = EventProcessor()

    def enqueue_event(self, payload):
        """
        Add an event to the queue to be processed

        Args:
            payload (str): json string containing an object that complies with EventPayload

        Returns:

        """
        # TODO: check the payload before inserting the task???
        return self.event_processor_queue.enqueue(
            self.event_processor.process_event, payload
        )

    def run_worker(self):
        """
        Run a worker to process events in the event processor queue
        """
        self.event_processor_worker.work()
