import os

from dotenv import load_dotenv

load_dotenv('bridge_manager/.env.bridge_manager')

class DatabaseConfig:

    DRIVERNAME = os.environ.get('DRIVERNAME')
    HOST = os.environ.get('HOST')
    PORT = os.environ.get('PORT')
    USERNAME = os.environ.get('USERNAME')
    PASSWORD = os.environ.get('PASSWORD')