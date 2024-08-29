# recieve insert events from the event_json table
# put the event in a processing queue
# if the queue is not empty then take a task
# mark task as taken
# process the event
# put in marsed messages table
# put parsed message event in queue


import json

from pydantic import BaseModel, ValidationError

from .event_models import BaseEvent, RoomMessageEvent
from .database.models import ParsedMessage, ProcessedEvent
from .database.repositories import ParsedMessagesRepository, ProcessedEventsRepository
from .errors import (
    UnsupportedEventTypeError,
    NoContentInRoomMessageEvent,
    UnsupportedMessageContentType,
)


class EventPayload(BaseModel):
    event_id: str
    event_json: dict


class EventProcessor:
    # TODO:
    # reconcile i.e. process events that have been missed
    # task queue
    # logging

    @staticmethod
    def process_event(payload: str):
        """
        Process an event

        Args:
            payload (str): json string containing an object that complies with EventPayload
        """

        self = EventProcessor()

        # validate payload
        payload_json = json.loads(payload)
        payload = EventPayload(**payload_json)

        # create internal event object
        try:
            event = self._create_event_object_from_payload(payload)
        except UnsupportedEventTypeError as e:
            # log
            print(e)
            return

        if isinstance(event, RoomMessageEvent):
            # insert parsed message event into database
            self._insert_room_message_event(event)
            # mark event_id as having been processed so when I do a refresh
            # to grab missing events - I'll know which events have been processed
            self._mark_event_processed(event)

    def _insert_room_message_event(self, event: RoomMessageEvent):
        """
        Insert the room message event into the parsed messages table in the database.

        Args:
            event (RoomMessageEvent): _description_
        """

        # text message content types don't have a url
        resource_url = getattr(event.content, "url", None)

        # create orm model
        parsed_message = ParsedMessage(
            event_id=event.event_id,
            room_id=event.room_id,
            message_timestamp=event.origin_server_ts,  # this is the original timestamp the message was sent
            matrix_server_hostname=event.origin,
            message_type=event.content.msgtype,
            sender=event.sender,
            body=event.content.body,
            resource_url=resource_url,
            depth=event.depth,
        )

        # insert into parsed messages table
        parsed_message_repository = ParsedMessagesRepository()
        parsed_message_repository.create(parsed_message)

    def _mark_event_processed(self, event):
        """
        Mark the event as being processed by adding it to the processed_events table.

        Args:
            event (_type_): event
        """
        # create model
        processed_event = ProcessedEvent(event_id=event.event_id)

        # insert into the processed_events table
        processed_events_repository = ProcessedEventsRepository()
        processed_events_repository.create(processed_event)

    def _create_event_object_from_payload(
        self, event_payload: EventPayload
    ) -> BaseEvent:
        """
        Creates an internal event model from the payload. The events returned will be of type BaseEvent.

        Args:
            event_payload (EventPayload): event payload

        Raises:
            ValueError: if the event type is not supported

        Returns:
            BaseEvent: an event model
        """
        event_json = event_payload.event_json
        event_json["event_id"] = event_payload.event_id

        event_type = event_json.get("type")
        if event_type == "m.room.message":
            try:
                return RoomMessageEvent(**event_json)
            except NoContentInRoomMessageEvent as e:
                # log
                print(e)
            except UnsupportedMessageContentType as e:
                # log
                print(e)

        # non m.room.message events are currently not needed by the application so I can imply ignore these
        raise UnsupportedEventTypeError(f"Unsupported event type {event_type}")
