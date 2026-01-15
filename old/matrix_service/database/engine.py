from sqlalchemy.engine import URL
from sqlalchemy import create_engine

from matrix_service.config import MatrixDatabaseConfig

class MatrixDatabaseEngine:
    """
    Singleton class for the matrix database engine
    """

    _engine = None

    def __new__(cls):
        if cls._engine is None:

            cls._engine = create_engine(URL.create(
                drivername=MatrixDatabaseConfig.DRIVERNAME,
                host=MatrixDatabaseConfig.HOST,
                port=MatrixDatabaseConfig.PORT,
                username=MatrixDatabaseConfig.USERNAME,
                password=MatrixDatabaseConfig.PASSWORD
            ))
        
        return cls._engine
