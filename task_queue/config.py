import os

from dotenv import load_dotenv

load_dotenv("task_queue/.env.task_queue")


class RedisConfig:

    HOST = os.environ.get("HOST")
    PORT = os.environ.get("PORT")
    DB = os.environ.get("DB")
    PASSWORD = os.environ.get("PASSWORD")
