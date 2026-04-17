"""KIS realtime websocket multiplexing session and primitives."""

from __future__ import annotations

from .reconnect import BackoffPolicy, RealtimeState
from .session import KISRealtimeSession, RealtimeSessionConfig
from .subscription import StreamKind, Subscription

__all__ = [
    "StreamKind",
    "Subscription",
    "RealtimeState",
    "BackoffPolicy",
    "KISRealtimeSession",
    "RealtimeSessionConfig",
]

# Module-level defaults (single source of truth for the realtime session).
DEFAULT_SUBSCRIBER_QUEUE_MAXSIZE = 1024
DEFAULT_SUBSCRIBE_ACK_TIMEOUT = 5.0
DEFAULT_SHUTDOWN_GRACE = 2.0
DEFAULT_BACKOFF_BASE = 1.0
DEFAULT_BACKOFF_MAX = 30.0
DEFAULT_BACKOFF_JITTER = 0.2
DEFAULT_MAX_RESUBSCRIBE_ATTEMPTS = 5
DEFAULT_PER_SUB_BACKOFF_BASE = 1.0
DEFAULT_PER_SUB_BACKOFF_MAX = 30.0
DEFAULT_PER_SUB_JITTER = 0.2
DEFAULT_PERMANENT_RT_CDS: frozenset[str] = frozenset()
DEFAULT_OVERFLOW_POLICY = "drop_oldest"
