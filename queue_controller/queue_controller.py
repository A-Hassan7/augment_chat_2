from fakeredis import FakeStrictRedis
from rq import Queue, Worker, SimpleWorker

from .connection import RedisConnection
from config import GlobalConfig

# modules will add tasks to specific queues through this TaskQueue
# the class will manage the queues for each queue i.e.
# the event processor queue, summarizer queue, llm queue etc.
# The task queue can eventually serve as an orchestrator to create/remove workers
# funcitons
# add task (to specific queue)
# list_queues (get a list of queues)
# manage workload and spawn new workers


class QueueController:
    """
    Centralized class to register and retrieve queues. Hoping this class comes in handy managing queues and workers internally.
    """

    QUEUES = ["event_processor", "vector_store"]

    def __init__(self, debug: bool = False):

        self.debug = debug if not GlobalConfig.DEBUG_MODE else GlobalConfig.DEBUG_MODE

        # create and test connection to redis
        # if debugging then use a fake redis connection
        # https://python-rq.org/docs/testing/#running-jobs-in-unit-tests
        if self.debug:
            self.connection = FakeStrictRedis()
            self.is_async = False
        else:
            self.connection = RedisConnection()
            self.is_async = True

        self.connection.ping()

    def get_queue(self, queue_name: str) -> Queue:
        self._check_queue_name(queue_name)
        return Queue(queue_name, connection=self.connection, is_async=self.is_async)

    def get_worker(self, queue_name: Queue) -> Worker:
        self._check_queue_name(queue_name)
        return Worker(queue_name, connection=self.connection)

    def _check_queue_name(self, queue_name: str):
        """
        Raises exception if queue has not been registered in self.QUEUES

        Args:
            queue_name (str): name of queue

        Raises:
            ValueError: if queue has not been registered in this class
        """
        if not queue_name in self.QUEUES:
            raise ValueError(
                f"Specified queue name ({queue_name}) has not been registered with the QueueController. ",
                f"Available queues include {self.QUEUES}",
            )
