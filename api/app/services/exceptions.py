"""
Domain exceptions raised by the secret service layer.

The service speaks in these terms; app.api.errors maps them to HTTP responses,
so routes never build error responses for domain failures by hand.

There is deliberately no "expired" error. Redis drops an expired key exactly
like a burned one, and invariant 5 forbids telling a burned id apart from one
that never existed: every miss is a SecretNotFoundError with one message.
"""


class SecretError(Exception):
    """Base class for every secret-domain failure."""


class SecretNotFoundError(SecretError):
    """The id is unknown, already revealed, or expired — indistinguishably."""


class InvalidSecretTTLError(SecretError):
    """The requested lifetime is outside the configured bounds."""

    def __init__(self, ttl_seconds: int, min_seconds: int, max_seconds: int) -> None:
        self.ttl_seconds = ttl_seconds
        self.min_seconds = min_seconds
        self.max_seconds = max_seconds
        super().__init__(
            f"ttl_seconds must be between {min_seconds} and {max_seconds}"
        )


class SecretStoreUnavailableError(SecretError):
    """The backing store could not be reached; the request may be retried."""
