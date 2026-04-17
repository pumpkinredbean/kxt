"""Public exception hierarchy for kxt."""

from __future__ import annotations


class KXTError(Exception):
    """Base exception for public kxt failures."""


class KXTClientError(KXTError):
    """Base exception for provider client failures."""


class KXTValidationError(KXTError):
    """Raised when a caller provides invalid input to the public API."""


class KXTUnsupportedError(KXTClientError):
    """Raised when a provider does not support a requested operation."""


class KXTAuthenticationError(KXTClientError):
    """Raised when provider authentication fails."""


class KXTTransportError(KXTClientError):
    """Raised when a provider transport/runtime layer fails before an API response."""

    def __init__(self, message: str, *, provider: str | None = None) -> None:
        super().__init__(message)
        self.provider = provider


class KXTTimeoutError(KXTTransportError):
    """Raised when a provider transport operation times out."""


class KXTConnectionError(KXTTransportError):
    """Raised when a provider connection cannot be established or is lost."""


class KXTAPIError(KXTClientError):
    """Raised when a provider returns an API-level failure."""

    def __init__(self, message: str, *, provider: str | None = None, code: str | None = None) -> None:
        super().__init__(message)
        self.provider = provider
        self.code = code
