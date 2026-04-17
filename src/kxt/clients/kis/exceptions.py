"""KIS-specific exception types layered on the public kxt hierarchy."""

from __future__ import annotations

from kxt.errors import (
    KXTAPIError,
    KXTAuthenticationError,
    KXTClientError,
    KXTConnectionError,
    KXTTimeoutError,
    KXTTransportError,
)


class KISError(KXTClientError):
    """Base exception for KIS client failures."""


class KISAuthenticationError(KXTAuthenticationError, KISError):
    """Raised when KIS authentication fails."""


class KISAPIError(KXTAPIError, KISError):
    """Raised when KIS returns an API-level error."""

    def __init__(self, message: str, *, code: str | None = None) -> None:
        KXTAPIError.__init__(self, message, provider="kis", code=code)


class KISTransportError(KXTTransportError, KISError):
    """Raised when KIS transport/runtime operations fail before an API response."""

    def __init__(self, message: str) -> None:
        KXTTransportError.__init__(self, message, provider="kis")


class KISTimeoutError(KXTTimeoutError, KISTransportError):
    """Raised when KIS transport operations time out."""

    def __init__(self, message: str) -> None:
        KISTransportError.__init__(self, message)


class KISConnectionError(KXTConnectionError, KISTransportError):
    """Raised when KIS connections cannot be established or are lost."""

    def __init__(self, message: str) -> None:
        KISTransportError.__init__(self, message)


class KISApprovalError(KISAuthenticationError):
    """Raised when the KIS approval-key acquisition or refresh fails.

    Typically corresponds to KIS ``msg_cd`` values starting with ``OAUTH`` or
    ``EGW``; treated as an authentication failure for upstream handlers.
    """

    def __init__(self, message: str, *, code: str | None = None) -> None:
        KISAuthenticationError.__init__(self, message)
        self.code = code


class KISRealtimeError(KISError):
    """Raised for KIS realtime session / websocket multiplex failures."""


class KISSubscriptionError(KISRealtimeError):
    """Raised for a permanent per-subscription failure on the realtime session."""

    def __init__(
        self,
        *,
        stream_kind: object,
        instrument: object,
        reason: str,
        rt_cd: str | None = None,
        msg: str | None = None,
        attempts: int | None = None,
    ) -> None:
        super().__init__(msg or f"subscription failed: {reason}")
        self.stream_kind = stream_kind
        self.instrument = instrument
        self.reason = reason  # "nack_permanent" | "max_retries_exceeded" | "session_closed"
        self.rt_cd = rt_cd
        self.msg = msg
        self.attempts = attempts
