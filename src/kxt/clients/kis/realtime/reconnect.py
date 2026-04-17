"""Session-level connection state and backoff policy helpers."""

from __future__ import annotations

import os
import random
from enum import Enum
from typing import Optional


class RealtimeState(str, Enum):
    """Lifecycle state of the realtime websocket session."""

    IDLE = "idle"
    CONNECTING = "connecting"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CLOSED = "closed"


class BackoffPolicy:
    """Exponential backoff with capped delay and symmetric jitter."""

    def __init__(self, base: float, cap: float, jitter: float) -> None:
        self.base = base
        self.cap = cap
        self.jitter = jitter
        self._attempt = 0

    def next(self) -> float:
        raw = min(self.cap, self.base * (2 ** self._attempt))
        self._attempt += 1
        return max(0.0, raw * (1.0 + random.uniform(-self.jitter, self.jitter)))

    def reset(self) -> None:
        self._attempt = 0


def env_backoff_overrides() -> tuple[Optional[float], Optional[float], Optional[float]]:
    """Read optional backoff overrides from environment variables.

    Returns ``(base, cap, jitter)``; any unset / invalid entry is ``None``.
    """

    def _parse(name: str) -> Optional[float]:
        value = os.environ.get(name)
        if value is None:
            return None
        try:
            return float(value)
        except ValueError:
            return None

    return (
        _parse("KXT_KIS_WS_BACKOFF_BASE"),
        _parse("KXT_KIS_WS_BACKOFF_MAX"),
        _parse("KXT_KIS_WS_BACKOFF_JITTER"),
    )
