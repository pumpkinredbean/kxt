"""Provider-specific exceptions for Toss Invest Open API."""

from __future__ import annotations

from kxt.errors import (
    KXTAPIError,
    KXTAuthenticationError,
    KXTConnectionError,
    KXTTimeoutError,
    KXTTransportError,
)


class TossInvestAPIError(KXTAPIError):
    """Raised when Toss Invest returns an API-level error envelope."""


class TossInvestAuthenticationError(KXTAuthenticationError):
    """Raised when Toss Invest OAuth authentication fails."""


class TossInvestTransportError(KXTTransportError):
    """Raised when Toss Invest transport fails before an API response."""


class TossInvestTimeoutError(TossInvestTransportError, KXTTimeoutError):
    """Raised when a Toss Invest request times out."""


class TossInvestConnectionError(TossInvestTransportError, KXTConnectionError):
    """Raised when Toss Invest cannot be reached."""


__all__ = [
    "TossInvestAPIError",
    "TossInvestAuthenticationError",
    "TossInvestConnectionError",
    "TossInvestTimeoutError",
    "TossInvestTransportError",
]
