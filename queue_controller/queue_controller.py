from rq import Queue

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

    QUEUES = ["event_processor"]

    def get_queue(self, queue_name: str) -> Queue:

        # handle unregistered queue
        if not queue_name in self.QUEUES:
            raise ValueError(
                f"Specified queue name ({queue_name}) has not been registered with the TaskQueueController. ",
                f"Available queues include {self.QUEUES}",
            )

        # test connection to redis
        connection = RedisConnection()
        connection.ping()

        return Queue(queue_name, connection=connection)
