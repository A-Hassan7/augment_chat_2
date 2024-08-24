from sqlalchemy.engine import URL
from sqlalchemy import create_engine

from bridge_manager.config import DatabaseConfig

class DatabaseEngine:
    """
    Singleton class for the matrix database engine
    """

    _engine = None

    def __new__(cls):
        if cls._engine is None:

            cls._engine = create_engine(URL.create(
                drivername=DatabaseConfig.DRIVERNAME,
                host=DatabaseConfig.HOST,
                port=DatabaseConfig.PORT,
                username=DatabaseConfig.USERNAME,
                password=DatabaseConfig.PASSWORD
            ))
        
        return cls._engine
