import psycopg2

from .database.engine import DatabaseEngine
from .config import EventListenerConfig
from .event_processor import EventProcessor


class EventListener:

    def __init__(self):
        self.engine = DatabaseEngine()
        self.config = EventListenerConfig()

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
                self.queue_event(notification)

    def queue_event(self, notification):

        if not notification.payload:
            raise ValueError("Notification payload is missing")

        # add the task to a queue
        processor = EventProcessor()
        processor.process_event(notification.payload)
