"""Custom exceptions for Mender client."""


class AuthenticationError(Exception):
    """Raised when authentication token is invalid or expired (401)."""
    pass
