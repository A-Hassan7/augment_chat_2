# does it create a parsed messsage object and insert into the database
# does it mark the event as processed
# does the event processor forward the event onto the vectorstore event queue
import json

import pytest

from event_processor.event_processor import EventProcessor
from event_processor.database.repositories import (
    ParsedMessagesRepository,
    ProcessedEventsRepository,
)


event_listener_payload = json.dumps(
    {
        "event_id": "test",
        "event_json": {
            "type": "m.room.message",
            "depth": 201,
            "hashes": {"sha256": "iSDbBtAGaGTfXLOFkJ3GiLOVuBVsi9sb585+9Tj7VBw"},
            "origin": "matrix.localhost.me",
            "sender": "@main:matrix.localhost.me",
            "content": {"body": "good", "msgtype": "m.text", "m.mentions": {}},
            "room_id": "!knjndlpommyDgaXrTp:matrix.localhost.me",
            "unsigned": {"age_ts": 1726389947522},
            "signatures": {
                "matrix.localhost.me": {
                    "ed25519:a_xlkE": "bIMSPnhiQYiYkjU3b/BO5sNvnpFqgqpllebkCfAXOqw/eAohBD+G6YxZnXK6X5NrtpumqQUQdpDOva6oesAUCQ"
                }
            },
            "auth_events": [
                "$eEua197JfqEy5RJqG1lWsbyEixlaADg5IKMtHHVo8oY",
                "$iHwgB3Eld_mYwNtwqbr2Eo-NKIMCbcDH2i5dqrVFW7k",
                "$G7nJHUareUgY47_B5EmrusaBSdw_2xf0aKpdMlemicE",
            ],
            "prev_events": ["$6p32ebmb2PtjW4odFnCbScC5DwiLSQD2U3scRt3R-84"],
            "origin_server_ts": 1726389947522,
        },
    }
)


@pytest.mark.parametrize("payload", [event_listener_payload])
def test_process_event(payload):

    # check inserted into parsed messages
    # check marked as processed
    # how do I check if it's been added to the vectorstore queue?
    # check the jobid
    event_processor = EventProcessor()

    job = event_processor.process_event(payload)

    event_id = json.loads(payload)["event_id"]

    # check parsed message has been created
    parsed_messages_repository = ParsedMessagesRepository()
    parsed_message = parsed_messages_repository.get_by_event_id(event_id)
    assert parsed_message, "Parsed message doesn't seem to have been created"

    # check the event has been parsed as processed
    processed_events_repository = ProcessedEventsRepository()
    processed_event = processed_events_repository.get_by_event_id(event_id)
    assert processed_event, "The parsed message has not been marked as processed"

    # check the job has been queue in the event processor queue
    assert job.enqueued_at, "Job hasn't been created"

    # cleanup
    # remove event from parsed messages and processed events
    parsed_messages_repository.delete_by_event_id(event_id)
    processed_events_repository.delete_by_event_id(event_id)
