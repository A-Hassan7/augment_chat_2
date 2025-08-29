import os

from dotenv import load_dotenv

load_dotenv(".env")


class DatabaseConfig:

    DRIVERNAME = os.environ.get("DRIVERNAME")
    HOST = os.environ.get("HOST")
    PORT = os.environ.get("PORT")
    USERNAME = os.environ.get("USERNAME")
    PASSWORD = os.environ.get("PASSWORD")


class BridgeManagerConfig:

    ID = "bridge_manager_1"
    USERNAME = "_bridge_manager"
    NAMESPACE = "_bridge_manager__"

    HS_URL = "http://localhost:8008"
    HS_NAME = "matrix.localhost.me"
    HS_TOKEN = "test"

    @property
    def full_username(self):
        return f"@{self.USERNAME}:{self.HS_NAME}"


# TODO: NEEDS TO BE A DB TABLE
TRANSACTION_ID_TO_BRIDGE_MAPPER = {}
