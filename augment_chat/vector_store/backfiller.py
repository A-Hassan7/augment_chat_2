# backfill parsed messages into transcripts
# at the moment I only have transcripts for events that have triggered VectorStore.process_message

from event_processor import EventProcessorInterface

from .vector_store_queue import VectorStoreQueue
from .database.repositories import TranscriptsRepository

event_processor = EventProcessorInterface()
transcripts_repository = TranscriptsRepository()
vector_store_queue = VectorStoreQueue()


def backfill_transcripts(room_ids: list = None, all_rooms: bool = False):
    """
    Find messages in the event processor that haven't been transcribed and transribe them.

    Args:
        room_ids (list, optional): _description_. Defaults to None.
        all_rooms (bool, optional): _description_. Defaults to False.

    Raises:
        ValueError: _description_
    """
    # log

    if room_ids and not isinstance(room_ids, list):
        raise ValueError(
            f"room_ids must be passed as a list received instance of {type(room_ids)}"
        )

    if not room_ids and not all_rooms:
        raise ValueError(
            "Either room_ids should be provided or all_rooms must be set to True."
        )

    # get all room_ids
    if all_rooms:
        room_ids = event_processor.get_all_room_ids()

    for room_id in room_ids:

        # get parsed messages from the event_processor
        # and get the event_ids from the vector store transcripts
        parsed_messages = event_processor.get_parsed_messages(room_id)
        transcripts = transcripts_repository.get_by_room_id(room_id)
        transcript_event_ids = [transcript.event_id for transcript in transcripts]

        for message in parsed_messages:
            if not message.event_id in transcript_event_ids:
                vector_store_queue.enqueue_message(message)
