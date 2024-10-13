# the vectorstore is going to create embeddings for messages in a room
# it needs to request messages from the event_processor (chunking required - could end up with loads of messages)
# process the messages once they'r received
# convert to transcript
# chunk?
# create embeddings
# implement retriever
# create update check logic for the listeners to use
import math
from datetime import datetime, timedelta

from logger import Logger
from llm_service import LLMInterface
from .transcriber import Transcriber
from .database.repositories import TranscriptsRepository, TranscriptChunksRepository
from .database.models import Transcript, TranscriptChunk


def insert_embedding_on_success(job, connection, result, *args, **kawargs):
    """
    Once the embedding has been generated it needs to be inserted into the database.
    I'm using RQ's on_success feature so when the embedding task is done, this function will trigger

    https://python-rq.org/docs/#success-callback

    IMPORTANT: this implementation expects the transcript chunk id to be passed as metadata to the job.
    """
    transcript_chunks_repository = TranscriptChunksRepository()

    transcript_chunk_id = job.meta.get("transcript_chunk.id")
    if not transcript_chunk_id:
        raise ValueError(
            "The job meta MUST contain the transcript_chunk.id in order to insert the embedding"
        )

    transcript_chunks_repository.insert_embedding(transcript_chunk_id, embedding=result)
    # log


class VectorStore:
    """
    Responsible for managing the vectorstore of messages.

    1. listens to all new messages in the vectorstore queue and processes.
    2. maintains the transcript_chunks table in the database
    3. creates embeddings
    4. provides retrieval functionality


    Returns:
        _type_: _description_
    """

    MESSAGES_CHUNK_SIZE = 30
    MESSAGES_CHUNK_OVERLAP = 10

    # required time to wait since the oldest message in the room was received
    # when backfilling the oldest messages get loaded last
    # if I start creating transcript chunks before the oldest message is received
    # I'll have to re-create the chunks
    OLDEST_ROOM_MESSAGE_WAIT_TIME_SECONDS = 10

    def __init__(self):
        logger_instance = Logger()
        self.logger = logger_instance.get_logger(name=__class__.__name__)

        self.transcriber = Transcriber()
        self.transcripts_repository = TranscriptsRepository()
        self.transcript_chunks_repository = TranscriptChunksRepository()

    @staticmethod
    def process_message(parsed_message):
        """
        Process a new parsed message received from the event processor and update the vector store accordingly.

        1. check if the event needs to be processed (already exists/not a text message etc.)
        2. Create transcript
        3. Check if there are existing chunks
            a. if not then initialise the room
                i. check if we have received the oldest message in the room if not then check agian in 5 seconds
                ii. start creating transcripts if there are enough messages
            b. if there aren't existing chunks then update the transcript_chunks table
                i. Get messages that haven't already been chunked (but grab the overlap amount required)
                ii. create transcript if there are enough messages

        Args:
            parsed_message (ParsedMessage): _description_
        """

        self = VectorStore()

        self.logger.info(f"Message received with event id: {parsed_message.event_id}")

        # for now ignore anything that isn't a text message
        # TODO: this ignores images and voice notes
        if not parsed_message.message_type == "m.text":
            self.logger.warning(
                "Message types other than m.text are not supported. "
                f"Message of type {parsed_message.message_type} received for event id: {parsed_message.event_id}"
            )
            return

        # transcript already exists so do nothing
        if self.transcripts_repository.get_by_event_id(parsed_message.event_id):
            self.logger.debug(
                f"Transcript already exists for event id: {parsed_message.event_id}"
            )
            return

        # transcribe the message and insert into the database
        self.transcriber.transcribe(parsed_message, insert_into_database=True)
        self.logger.info(f"Transcript created for event id: {parsed_message.event_id}")

        room_id = parsed_message.room_id

        # check if there are existing transcript chunks in the vectorstore
        # if not then initialise the room i.e. create chunks
        num_chunks = self.transcript_chunks_repository.get_count_by_room_id(room_id)
        if not num_chunks:
            self.logger.info(
                f"No existing transcript chunks found for room id: {room_id}"
            )
            # this will check to see if we can create chunks for the room
            # if not then it'll queue a task to take place to check again.
            self.initialise_room(room_id)
            return

        # inserts new chunks into the database if there are enough messages
        self.update_room(room_id)

    def initialise_room(self, room_id):

        # check if existing chunks have been created
        # if not then this is a fresh room to create chunks for
        # in which case I need to check if I've received the oldest backfilled messages
        # and that there are enough transcripts to create a chunk
        # then create the chunks using all transcripts

        # get the existing number of transcript chunks
        # if there are existing chunks then the room has already been initialised so exit
        num_chunks = self.transcript_chunks_repository.get_count_by_room_id(room_id)
        if num_chunks:
            return

        # has the oldest room message been received?
        if not self._is_oldest_message_received(room_id):
            # create a task to check again in 5 seconds
            # if I receive all messages in the room in less than 10 seconds
            # then none of the messages will trigger this
            # I need this to trigger after all the messages have been received
            # TODO: test
            from vector_store_queue import VectorStoreQueue

            self.logger.info(
                f"I hasn't been long enough since the oldest message was received to create transcript chunk for room id: {room_id}"
            )

            queue = VectorStoreQueue()
            queue.enqueue_room_initialisation(room_id, delay=timedelta(seconds=5))
            self.logger.info(
                f"Enqueuing room initialisation for room id: {room_id} with a delay of 5 seconds"
            )
            return

        # are there enough transcripts to create a chunk?
        num_transcripts = self.transcripts_repository.get_count_by_room_id(room_id)
        if not num_transcripts >= self.MESSAGES_CHUNK_SIZE:
            self.logger.info(
                f"Not enough transcripts to create a transcript chunk for room id: {room_id}"
            )
            return

        all_transcripts = self.transcripts_repository.get_by_room_id(room_id)
        chunks = self._create_transcript_chunks(all_transcripts)
        self.logger.info(
            f"Created {len(chunks)} initial chunk(s) for room id: {room_id}"
        )

        # insert chunks into the database
        # TODO: how do I handle embeddings?
        for chunk in chunks:
            self._insert_chunk_into_database(chunk, create_embedding=True)
            self.logger.info(
                f"Added chunk to transcript chunks table for room id: {room_id}"
            )

    def update_room(self, room_id):

        # there are existing chunks
        # get the max message depth from the existing chunks
        # are there enough messages after that depth to create a new chunk (including the overlap amount)
        # if there are then create the chunk

        max_depth_of_newest_transcript_chunk = (
            self.transcript_chunks_repository.get_max_message_depth_by_room_id(room_id)
        )
        new_transcripts = self.transcripts_repository.get_new_messages_for_chunking(
            room_id=room_id,
            max_depth_of_newest_transcript_chunk=max_depth_of_newest_transcript_chunk,
            chunk_overlap=self.MESSAGES_CHUNK_OVERLAP,
        )
        if not len(new_transcripts) >= self.MESSAGES_CHUNK_SIZE:
            self.logger.debug(
                f"Not enough transcripts to create a new chunk for room id {room_id}. "
                f"{len(new_transcripts)} out of the {self.MESSAGES_CHUNK_SIZE} required."
            )
            return

        chunks = self._create_transcript_chunks(new_transcripts)
        for chunk in chunks:
            self._insert_chunk_into_database(chunk, create_embedding=True)

    def _is_oldest_message_received(self, room_id: str) -> bool:
        """
        Check if the vectorstore can start creating chunks for a room_id.

        The goal is to ensure that we've received all backfilled messages from the matrix server and bridge.
        The current implementation relies on enough time passing since the vectorstore received the oldest message
        in the room.

        Args:
            room_id (str): matrix room id

        Returns:
            bool: can start chunking
        """

        # get the created_at of the oldest message in the room
        oldest_message = self.transcripts_repository.get_oldest_message_by_room_id(
            room_id
        )
        oldest_message_created_at = oldest_message.created_at

        # check if required time has passed since the oldest message was received
        time_elapsed = (datetime.now() - oldest_message_created_at).seconds
        return time_elapsed > self.OLDEST_ROOM_MESSAGE_WAIT_TIME_SECONDS

    def _create_transcript_chunks(
        self, transcripts: list[Transcript]
    ) -> list[TranscriptChunk]:
        """
        Turns a list of transcripts into chunks. Partial chunks are not returned.

        Args:
            transcripts (list[Transcript]): _description_

        Returns:
            list[TranscriptChunk]: _description_
        """

        chunksize = self.MESSAGES_CHUNK_SIZE
        overlap = self.MESSAGES_CHUNK_OVERLAP

        len_parsed_messages = len(transcripts)

        # calculate the number of chunks we can make given the length of transcripts
        # round down to exclude any incomplete chunks
        # OR round up to include incomplete chunks
        num_chunks = 1 + (len(transcripts) - chunksize) / (chunksize - overlap)
        num_chunks = math.floor(num_chunks)

        # create chunks by indexing the transcripts
        chunk_list = []
        for i in range(num_chunks):
            start_index = i * (chunksize - overlap)

            # if the end index exceeds the length of the transcripts
            # then use the message length instead
            end_index = start_index + chunksize
            end_index = None if end_index >= len_parsed_messages else end_index

            chunk = self._construct_chunk(transcripts[start_index:end_index])
            chunk_list.append(chunk)

        return chunk_list

    def _construct_chunk(self, chunk: list[Transcript]) -> TranscriptChunk:
        """
        Construct a TranscriptChunk object from a given chunk of transcripts.

        Simply a convenience function.

        Args:
            chunk (list[Transcript]): _description_
        """
        room_ids, event_ids, depths, message_timestamps, transcripts = [
            [] for _ in range(5)
        ]
        for transcript in chunk:
            room_ids.append(transcript.room_id)
            event_ids.append(transcript.event_id)
            depths.append(transcript.depth)
            message_timestamps.append(transcript.message_timestamp)
            transcripts.append(transcript.transcript)

        document = "\n".join(transcripts)

        return TranscriptChunk(
            room_id=room_ids[0],
            event_ids=event_ids,
            min_message_depth=min(depths),
            max_message_depth=max(depths),
            min_message_timestamp=min(message_timestamps),
            max_message_timestamp=max(message_timestamps),
            num_transcripts=len(event_ids),
            document=document,
        )

    def _insert_chunk_into_database(
        self, chunk: TranscriptChunk, create_embedding: bool = False
    ):
        """
        Inserts a transcript chunk into the database.

        If create_embedding is True then this will queue a request with the LLM service to
        create the embedding and insert into the database on completion.

        Args:
            chunk (_type_): _description_
            create_embeddings (bool, optional): _description_. Defaults to False.
        """
        # insert chunk into the database
        self.transcript_chunks_repository.create(chunk)

        self.logger.info(
            f"New transcript chunk inserted into database for room id {chunk.room_id}"
        )

        # request embedding
        if create_embedding:

            llm = LLMInterface()
            # send request to llm
            llm.enqueue_embedding_request(
                text=chunk.document,
                request_reference_type="transcript_chunk_id",
                request_reference=chunk.id,
                on_success=insert_embedding_on_success,
                meta={"transcript_chunk.id": chunk.id},
            )
            self.logger.info(f"Embedding request enqueued for room_id: {chunk.room_id}")

    def retrieve(self):
        # TODO:
        # process your real messages
        # handle rate limits openai
        # implement room_id filtering so only rooms with a is_augmentation_enabled = True
        # can be processed by the vectorstore
        # if not is_augmentation_enabled then vectorstore ignore messages
        # if enabled then run backfiller first to grab all missed messages
        # build retrieval
        # ability to run everything synchronously without the queue, will help testing #
        # start building the summarizers so I know what sort of retrieval to implement

        pass
