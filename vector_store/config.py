import os

from dotenv import load_dotenv

load_dotenv("vector_store/.env.vector_store")


class DatabaseConfig:

    DRIVERNAME = os.environ.get("DRIVERNAME")
    HOST = os.environ.get("HOST")
    PORT = os.environ.get("PORT")
    USERNAME = os.environ.get("USERNAME")
    PASSWORD = os.environ.get("PASSWORD")
