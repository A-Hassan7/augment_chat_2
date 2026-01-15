# is the transcript created
# initialise room
# update room

from datetime import datetime
import time

import pytest

from vector_store.vector_store import VectorStore
from vector_store.database.repositories import (
    TranscriptsRepository,
    TranscriptChunksRepository,
)
from event_processor.database.models import ParsedMessage
from config import GlobalConfig

# make queues synchronous
GlobalConfig.DEBUG_MODE = True

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

    # clean up existing tests if they exist
    transcript_repository.delete_by_room_id(TEST_ROOM_ID)
    transcript_chunks_repository.delete_by_room_id(TEST_ROOM_ID)

    # process messages
    for i, message in enumerate(parsed_messages):

        vector_store.process_message(message)

        if i == 0:
            time.sleep(vector_store.OLDEST_ROOM_MESSAGE_WAIT_TIME_SECONDS)

        # check a transcript gets created and inserted into the transcripts table
        transcript = transcript_repository.get_by_event_id(message.event_id)
        assert transcript, "Transcript not created"

    # check that a chunk has been created
    if NUM_TEST_MESSAGES >= vector_store.MESSAGES_CHUNK_SIZE:
        chunks = transcript_chunks_repository.get_by_room_id(TEST_ROOM_ID)
        assert chunks, "Chunk has not been created"
        assert chunks[0].embedding is not None, "Embeddings have not been created"

    # cleanup
    transcript_repository.delete_by_room_id(TEST_ROOM_ID)
    transcript_chunks_repository.delete_by_room_id(TEST_ROOM_ID)
