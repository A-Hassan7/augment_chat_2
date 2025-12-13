import os

from dotenv import load_dotenv

load_dotenv(".env")


class DatabaseConfig:

    DRIVERNAME = os.environ.get("DRIVERNAME")
    HOST = os.environ.get("HOST")
    PORT = os.environ.get("PORT")
    USERNAME = os.environ.get("USERNAME")
    PASSWORD = os.environ.get("PASSWORD")
    DATABASE = os.environ.get("DATABASE")


class BridgeManagerConfig:

    ID = "bridge_manager_1"
    USERNAME = "_bridge_manager"
    NAMESPACE = "_bridge_manager__"

    PORT = 8080
    HOST = "0.0.0.0"
    AS_TOKEN = "as_token_test"

    @property
    def username_regex(self):
        return rf"@{self.NAMESPACE}(?P<bridge_type>[^_]+)_(?P<bridge_id>[^_]+)__(?P<bridge_username>[^:]+):(?P<homeserver>[^\s/]+)"
