from rq import Queue, Worker

from .connection import RedisConnection

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

    QUEUES = ["event_processor", "test"]

    def __init__(self):
        # create and test connection to redis
        self.connection = RedisConnection()
        self.connection.ping()

    def get_queue(self, queue_name: str) -> Queue:
        self._check_queue_name(queue_name)
        return Queue(queue_name, connection=self.connection)

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
