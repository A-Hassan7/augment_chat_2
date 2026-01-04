"""
Custom exceptions for user management service.
"""


# User Registration Errors
class MatrixUserRegistrationError(Exception):
    """Raised when Matrix user registration fails"""

    pass


class UserAlreadyExistsError(Exception):
    """Raised when attempting to create a user that already exists"""

    pass


# Bridge Management Errors
class BridgeAccessDeniedError(Exception):
    """Raised when user tries to access a bridge they don't own"""

    pass


class BridgeCreationError(Exception):
    """Raised when bridge creation fails"""

    pass


class BridgeLoginError(Exception):
    """Raised when bridge login fails"""

    pass


class InvalidBridgeServiceError(Exception):
    """Raised when unsupported bridge service is requested"""

    pass


class BridgeNotFoundError(Exception):
    """Raised when bridge doesn't exist"""

    pass
