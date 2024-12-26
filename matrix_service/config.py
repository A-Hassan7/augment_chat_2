import os

from dotenv import load_dotenv

load_dotenv(".env")


class MatrixDatabaseConfig:

    DRIVERNAME = os.environ.get("MATRIX_DATABASE_DRIVERNAME")
    HOST = os.environ.get("MATRIX_DATABASE_HOST")
    PORT = os.environ.get("MATRIX_DATABASE_PORT")
    USERNAME = os.environ.get("MATRIX_DATABASE_USERNAME")
    PASSWORD = os.environ.get("MATRIX_DATABASE_PASSWORD")


class MatrixConfig:

    MATRIX_HOMESERVER_URL = os.environ.get("MATRIX_HOMESERVER_URL")
    MATRIX_HOMESERVER_NAME = os.environ.get("MATRIX_HOMESERVER_NAME")
