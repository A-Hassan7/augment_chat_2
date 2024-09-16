# is the transcript created
# initialise room
# update room

from datetime import datetime

import pytest

from vector_store.vector_store import VectorStore
from vector_store.database.repositories import (
    TranscriptsRepository,
    TranscriptChunksRepository,
)
from event_processor.database.models import ParsedMessage


TEST_ROOM_ID = "test"
NUM_TEST_MESSAGES = 30

test_parsed_messages = [
    ParsedMessage(
        event_id=f"test_{i}",
        room_id=TEST_ROOM_ID,
        message_timestamp=datetime.now(),
        matrix_server_hostname="test",
        message_type="m.text",
        sender=f"@main:matrix.localhost.me",
        body=f"test",
        depth=i,
    )
    for i in range(NUM_TEST_MESSAGES)
]


# insert enough parsed messages to test chunking and embedding along with it
@pytest.mark.parametrize("parsed_messages", [test_parsed_messages])
def test_process_message(parsed_messages):

    vector_store = VectorStore()
    transcript_repository = TranscriptsRepository()
    transcript_chunks_repository = TranscriptChunksRepository()

    # process messages
    for message in parsed_messages:

        vector_store.process_message(message)

        # check a transcript gets created and inserted into the transcripts table
        transcript = transcript_repository.get_by_event_id(message.event_id)
        assert transcript, "Transcript not created"

    # TODO: check that a chunk has been created

    # cleanup
    event_ids = [message.event_id for message in parsed_messages]
    [transcript_repository.delete_by_event_id(event_id) for event_id in event_ids]
    transcript_chunks_repository.delete_by_room_id(TEST_ROOM_ID)
