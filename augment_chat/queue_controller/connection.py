from redis import Redis

from .config import RedisConfig


class RedisConnection:
    """
    Singleton class for the redis connection
    """

    _connection = None

    def __new__(cls):
        if cls._connection is None:

            cls._connection = Redis(
                host=RedisConfig.HOST,
                port=RedisConfig.PORT,
                db=RedisConfig.DB,
                password=RedisConfig.PASSWORD,
            )

            # test connection
            cls._connection.ping()

        return cls._connection
