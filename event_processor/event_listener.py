import json
import psycopg2

from logger import Logger

from .database.engine import DatabaseEngine
from .config import EventListenerConfig
from .event_queue import EventProcessorQueue


class EventListener:

    def __init__(self):
        logger_instance = Logger(file="logs.txt")
        self.logger = logger_instance.get_logger(self.__class__.__name__)

        self.engine = DatabaseEngine()
        self.config = EventListenerConfig()
        self.event_processor_queue = EventProcessorQueue()

    def run(self):
        """
        Run the event listener. This creates an infinate while loop to listen for events on the
        postgreSQL channel specified in the EventListenerConfig
        """

        # create connection with the database
        # enable autocommit so every statement is executed without needing to call cursor.commit()
        connection = self.engine.raw_connection()
        connection.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = connection.cursor()

        # start listening to the channel
        cursor.execute(f"LISTEN {self.config.NOTIFY_CHANNEL};")

        self.logger.debug("Starting event listener")

        # loop
        while True:

            # polls the database for new notifications
            # if there is a new event it will be added to the notifies list
            connection.poll()
            while notifies := connection.notifies:

                notification = notifies.pop(0)

                if not notification.payload:
                    self.logger.critical("Notification payload is missing")
                    raise ValueError("Notifaciton payload is missing")

                event_id = json.loads(notification.payload).get("event_id")
                self.logger.info(f"Received notification with event id: {event_id}")

                # add event to queue
                self.event_processor_queue.enqueue_event(notification.payload)
                self.logger.info(
                    f"Added event to event processor queue with event id: {event_id} "
                )
