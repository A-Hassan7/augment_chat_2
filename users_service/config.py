import os

from dotenv import load_dotenv

load_dotenv('users_service/.env.users_service')

class DatabaseConfig:

    DRIVERNAME = os.environ.get('DRIVERNAME')
    HOST = os.environ.get('HOST')
    PORT = os.environ.get('PORT')
    USERNAME = os.environ.get('USERNAME')
    PASSWORD = os.environ.get('PASSWORD')