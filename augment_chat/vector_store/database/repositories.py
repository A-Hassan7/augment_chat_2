from abc import ABC, abstractmethod

from sqlalchemy import select, update, text, func, delete, asc, desc
from sqlalchemy.orm import sessionmaker

from .models import Base, MatrixProfile, Transcript, TranscriptChunk
from .engine import DatabaseEngine

Base.metadata.create_all(bind=DatabaseEngine())


class BaseRepository(ABC):

    def __init__(self):
        self.Session = sessionmaker(bind=DatabaseEngine())

    def get_all(self):
        with self.Session() as session:
            statement = select(self.model)
            return session.execute(statement).scalars().all()


class TranscriptsRepository(BaseRepository):

    model = Transcript

    def get_by_matrix_user_id(self, matrix_user_id: str):
        with self.Session() as session:
            statement = select(self.model).where(
                self.model.sender_matrix_user_id == matrix_user_id
            )
            return session.execute(statement).scalars().all()

    def get_by_event_id(self, event_id: str):
        with self.Session() as session:
            statement = select(self.model).where(self.model.event_id == event_id)
            return session.execute(statement).scalar()

    def delete_by_event_id(self, event_id: str):
        with self.Session() as session:
            statement = delete(self.model).where(self.model.event_id == event_id)
            session.execute(statement)
            session.commit()

    def delete_by_room_id(self, room_id: str):
        with self.Session() as session:
            statement = delete(self.model).where(self.model.room_id == room_id)
            session.execute(statement)
            session.commit()

    def get_by_room_id(
        self,
        room_id: str,
        order_by_timestamp_asc: bool = True,
        limit: int = None,
        until_message_event_id: str = None,
    ):
        with self.Session() as session:

            # order transcripts by timestamp in specified order
            order_by_func = asc if order_by_timestamp_asc else desc

            statement = (
                select(self.model)
                .where(self.model.room_id == room_id)
                .order_by(order_by_func(self.model.message_timestamp))
            )

            # get the depth of the message where we want to cut the transcripts off at
            if until_message_event_id:
                until_event = self.get_by_event_id(until_message_event_id)
                # add max depth to the where clause to limit messages depth
                statement = statement.where(self.model.depth <= until_event.depth)

            if limit:
                statement = statement.limit(limit)

            return session.execute(statement).scalars().all()

    def get_count_by_room_id(self, room_id: str):
        with self.Session() as session:
            statement = select(func.count(self.model.room_id)).where(
                self.model.room_id == room_id
            )
            return session.execute(statement).scalar()

    def create(self, transcript: Transcript):
        with self.Session() as session:
            session.add(transcript)
            session.commit()

    def get_oldest_message_by_room_id(self, room_id: str):
        # get the row with the oldest message in the room
        # I'm using the 'depth' to find the oldest message
        # Depth increments every time a new event takes place in a room
        # therefore message with the lowest depth, is the oldest message.
        # docs: https://spec.matrix.org/latest/#event-graphs
        with self.Session() as session:
            query = f"""
            select *
            from vector_store.transcripts
            where
                room_id = '{room_id}'
                and depth = (
                    select min(depth)
                    from vector_store.transcripts
                    where room_id = '{room_id}'
                )
            """
            return session.execute(text(query)).one()

    def get_new_messages_for_chunking(
        self,
        room_id: str,
        max_depth_of_newest_transcript_chunk: int,
        chunk_overlap: int,
    ):
        """
        Get new messages for creating chunks. This grabs new messages after a specified depth for a room
        and includes an overlap amount.

        Args:
            room_id (str): room_id
            max_depth_of_newest_transcript_chunk (int): maximum message depth of the most recent chunk
            chunk_overlap (int): chunk overlap amount
        """
        with self.Session() as session:
            # gets new messages after the max depth of the newest chunk
            # this includes the overlap
            query = f"""
            (
                -- get transcripts after the last chunked message
                select *
                from vector_store.transcripts
                where 
                    depth > {max_depth_of_newest_transcript_chunk}
                    and room_id = '{room_id}'
            )
            union 
            (
                -- get the overlapping transcripts if a new chunk were to be created
                select *
                from vector_store.transcripts
                where 
                    depth <= {max_depth_of_newest_transcript_chunk}
                    and room_id = '{room_id}'
                order by depth desc
                limit {chunk_overlap}
            )
            order by message_timestamp asc
            """
            return session.execute(text(query)).all()


class TranscriptChunksRepository(BaseRepository):

    model = TranscriptChunk

    def get_by_room_id(self, room_id: str):
        with self.Session() as session:
            statement = select(self.model).where(self.model.room_id == room_id)
            return session.execute(statement).scalars().all()

    def delete_by_room_id(self, room_id: str):
        with self.Session() as session:
            statement = delete(self.model).where(self.model.room_id == room_id)
            session.execute(statement)
            session.commit()

    def get_count_by_room_id(self, room_id: str):
        with self.Session() as session:
            statement = select(func.count(self.model.room_id)).where(
                self.model.room_id == room_id
            )
            return session.execute(statement).scalar()

    def create(self, transcript_chunk: TranscriptChunk):
        with self.Session() as session:

            # need to prevent the session from expiring so that the chunk
            # can still be accessed in the vectorstore. Without this the following error is created
            # sqlalchemy.orm.exc.DetachedInstanceError
            session.expire_on_commit = False

            session.add(transcript_chunk)
            session.commit()

    def insert_embedding(self, transcript_chunk_id: str, embedding):
        with self.Session() as session:
            statement = (
                update(self.model)
                .where(self.model.id == transcript_chunk_id)
                .values(embedding=embedding)
            )
            session.execute(statement)
            session.commit()

    def get_max_message_depth_by_room_id(self, room_id: str):
        with self.Session() as session:
            query = f"""
            select room_id, max(max_message_depth) as max_depth
            from vector_store.transcript_chunks
            where room_id = '{room_id}'
            group by room_id
            """
            result = session.execute(text(query)).one()
            return result.max_depth


class MatrixProfilesRepository(BaseRepository):

    model = MatrixProfile

    def get_by_matrix_user_id(self, matrix_user_id: str):
        with self.Session() as session:
            statement = select(self.model).where(
                self.model.full_user_id == matrix_user_id
            )
            return session.execute(statement).scalar()
