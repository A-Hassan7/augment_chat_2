"""
Homeserver Interface - Public API for homeserver client.

Import homeserver client through this interface:
    from matrix_manager.homeserver import HomeserverClient, HomeserverClientError
"""

from .client import (
    HomeserverClient,
    HomeserverClientError,
    RegistrationError,
    LoginError,
    RoomCreationError,
    MessageSendError,
)
from .config import (
    HOMESERVER_URL,
    HOMESERVER_NAME,
    SYNAPSE_DATABASE_URL,
)

__all__ = [
    "HomeserverClient",
    "HomeserverClientError",
    "RegistrationError",
    "LoginError",
    "RoomCreationError",
    "MessageSendError",
    "HOMESERVER_URL",
    "HOMESERVER_NAME",
    "SYNAPSE_DATABASE_URL",
]
