import os

from dotenv import load_dotenv

load_dotenv("queue_controller/.env.queue_controller")


class RedisConfig:

    HOST = os.environ.get("REDIS_HOST")
    PORT = os.environ.get("REDIS_PORT")
    DB = os.environ.get("REDIS_DB")
    PASSWORD = os.environ.get("REDIS_PASSWORD")
