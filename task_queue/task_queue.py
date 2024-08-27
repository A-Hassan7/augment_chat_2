from rq import Queue

from .connection import RedisConnection


class TaskQueue:
    """
    Centralized class to get an instance of the queue
    """

    @staticmethod
    def get_queue(name: str) -> Queue:
        connection = RedisConnection()
        connection.ping()

        return Queue(name, connection=connection)
