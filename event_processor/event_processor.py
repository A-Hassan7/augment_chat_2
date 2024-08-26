# recieve insert events from the event_json table
# put the event in a processing queue
# if the queue is not empty then take a task
# mark task as taken
# process the event
# put in marsed messages table
# put parsed message event in queue


import json
from nio.events.room_events import Event, RoomMessage


class EventProcessor:

    def process_event(self, payload):

        payload = json.loads(payload)
        event_id = payload.get("event_id")
        event_json = payload.get("json")
        event_json["event_id"] = event_id

        event = Event.parse_event(event_json)

        if not isinstance(event, RoomMessage):
            # handle
            # do I simply ignore non message events?
            pass

        event_id = event.event_id
        room_id = event.source.get("room_id")
        matrix_server_timestamp = event.server_timestamp
        origin_server = event.source.get("origin")
        message_type = event.source["content"]["msgtype"]
        sender = event.sender
        body = event.body
        resource_url = event.source["content"].get("url")
        depth = event.source.get("depth")
        source = event.source

        print(event_id, body)
