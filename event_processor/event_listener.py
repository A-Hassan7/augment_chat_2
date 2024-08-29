import psycopg2

from .database.engine import DatabaseEngine
from .config import EventListenerConfig
from .interface import EventProcessorQueueInterface


class EventListener:

    def __init__(self):
        self.engine = DatabaseEngine()
        self.config = EventListenerConfig()
        self.event_processor_queue = EventProcessorQueueInterface()

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

        # loop
        while True:

            # polls the database for new notifications
            # if there is a new event it will be added to the notifies list
            connection.poll()
            while notifies := connection.notifies:

                notification = notifies.pop(0)

                if not notification.payload:
                    raise ValueError("Notifaciton payload is missing")

                print(notification.payload)
                self.event_processor_queue.enqueue_event(notification.payload)
