import os

from dotenv import load_dotenv

load_dotenv(".env")


class DatabaseConfig:

    DRIVERNAME = os.environ.get("DRIVERNAME")
    HOST = os.environ.get("HOST")
    PORT = os.environ.get("PORT")
    USERNAME = os.environ.get("USERNAME")
    PASSWORD = os.environ.get("PASSWORD")


class EventListenerConfig:

    NOTIFY_CHANNEL = "matrix_event_json"
