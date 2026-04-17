"""Subscription handle and stream kinds for the KIS realtime session."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

from ..exceptions import KISSubscriptionError

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .session import KISRealtimeSession


_logger = logging.getLogger("kxt.kis.realtime")


class StreamKind(str, Enum):
    """Realtime stream kinds supported by the KIS session."""

    trades = "trades"
    order_book = "order_book"


# Sentinels used in the subscription queue to signal shutdown / failure.
_SHUTDOWN: Any = object()
_FAIL: Any = object()


class Subscription:
    """Handle for a single realtime subscription.

    Not a dataclass: owns a mutable asyncio.Queue and internal state managed
    by :class:`KISRealtimeSession`.
    """

    def __init__(
        self,
        *,
        stream_kind: StreamKind,
        instrument: Any,
        tr_id: str,
        tr_key: str,
        queue_maxsize: int,
        overflow_policy: str = "drop_oldest",
    ) -> None:
        self.stream_kind = stream_kind
        self.instrument = instrument
        self.tr_id = tr_id
        self.tr_key = tr_key
        self._queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=queue_maxsize)
        self._closed = False
        self._overflow = overflow_policy
        self._err: Optional[KISSubscriptionError] = None
        self._dropped = 0
        self._session: Optional["KISRealtimeSession"] = None

    @property
    def closed(self) -> bool:
        return self._closed

    def _offer(self, event: Any) -> None:
        """Offer an event to the subscriber queue respecting overflow policy."""

        if self._closed:
            return
        try:
            self._queue.put_nowait(event)
            return
        except asyncio.QueueFull:
            pass

        if self._overflow == "drop_oldest":
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                self._queue.put_nowait(event)
            except asyncio.QueueFull:
                self._dropped += 1
        else:  # drop_newest
            self._dropped += 1

        if self._dropped and self._dropped % 1000 == 1:
            _logger.warning(
                "subscription dropped events tr_id=%s tr_key=%s total=%d",
                self.tr_id,
                self.tr_key,
                self._dropped,
            )

    async def events(self) -> AsyncIterator[Any]:
        """Async iterator yielding parsed events until shutdown or failure."""

        while True:
            item = await self._queue.get()
            if item is _SHUTDOWN:
                return
            if item is _FAIL:
                assert self._err is not None
                raise self._err
            yield item

    async def aclose(self) -> None:
        """Close the subscription and unsubscribe from the session."""

        if self._closed:
            return
        self._closed = True
        session = self._session
        if session is not None:
            try:
                await session._unsubscribe_internal(self)
            except Exception:  # pragma: no cover - defensive
                _logger.exception("unsubscribe failed for %s:%s", self.tr_id, self.tr_key)
        self._push_sentinel(_SHUTDOWN)

    def _mark_permanently_failed(self, err: KISSubscriptionError) -> None:
        """Mark the subscription as permanently failed and raise on next read."""

        self._err = err
        self._closed = True
        self._push_sentinel(_FAIL)

    def _push_sentinel(self, sentinel: Any) -> None:
        try:
            self._queue.put_nowait(sentinel)
            return
        except asyncio.QueueFull:
            pass
        # Make room (drop oldest) and retry exactly once.
        try:
            self._queue.get_nowait()
        except asyncio.QueueEmpty:
            pass
        try:
            self._queue.put_nowait(sentinel)
        except asyncio.QueueFull:  # pragma: no cover - extremely unlikely
            pass
