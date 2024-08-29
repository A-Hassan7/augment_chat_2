import json

from pydantic import ValidationError

from .database.repositories import UnprocessedEventsViewRepository
from .event_processor import EventProcessor, EventPayload
from .interface import EventProcessorQueueInterface


class EventBackfiller:
    # get unprocessed events
    # process them/add them to the queue

    def __init__(self):
        self.event_processor_queue = EventProcessorQueueInterface()

    def process_unprocessed_events(self):
        """
        Processes events that have not yet been processed by the event processor.
        """

        # these are events that don't exist in the event_processor.processed_events table but
        # do exist in the public.event_json table from matrix
        unprocessed_events = self.unprocessed_events
        for event_id, event_json in unprocessed_events:
            # create a payload that complies with the EventPayload model
            # this is required because that's the expected input into the event processor
            payload = self._create_payload(event_id, event_json)
            if not payload:
                # log
                print("Payload could not be constructed")

            # TODO: append task to queue instead
            self.event_processor_queue.enqueue_event(payload)

    @property
    def unprocessed_events(self):
        """
        Returns unprocessed events by comparing the public.event_json table from the matrix server to the
        event_processor.processed_events table. If an event exists in the matrix table but not in the processed_events table
        then it has not been processed.

        Returns:
            _type_: _description_
        """
        unprocessed_events_repository = UnprocessedEventsViewRepository()
        unprocessed_events = unprocessed_events_repository.get_unprocessed_events()

        return unprocessed_events

    def _create_payload(self, event_id, event_json) -> str:
        """
        Create a payload that is consistent with the EventPayload model as this is what's expected by
        the EventProcessor.process_event function.

        Args:
            event_id (str): event_id
            event_json (str): event_json

        Returns:
            _type_: _description_
        """

        payload = json.dumps({"event_id": event_id, "event_json": event_json})
        try:
            EventPayload.model_validate_json(payload)
        except ValidationError as e:
            # log
            print(e)
            return

        return payload
