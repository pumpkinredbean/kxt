"""KIS realtime session multiplexing multiple subscriptions on one websocket."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import random
from dataclasses import dataclass, field, replace
from typing import Any, Awaitable, Callable, Optional

from ..exceptions import KISApprovalError, KISRealtimeError, KISSubscriptionError
from ..parsing import (
    KIS_MARKET_STATUS_KRX_WS_TR_ID,
    KIS_MARKET_STATUS_NXT_WS_TR_ID,
    KIS_MARKET_STATUS_TOTAL_WS_TR_ID,
    KIS_MEMBER_KRX_WS_TR_ID,
    KIS_MEMBER_NXT_WS_TR_ID,
    KIS_MEMBER_TOTAL_WS_TR_ID,
    KIS_ORDERBOOK_WS_TR_ID,
    KIS_PROGRAM_TRADE_KRX_WS_TR_ID,
    KIS_PROGRAM_TRADE_NXT_WS_TR_ID,
    KIS_PROGRAM_TRADE_TOTAL_WS_TR_ID,
    KIS_TRADE_TR_ID,
)
from .inbound import InboundPump
from .outbound import OutboundCommand, OutboundPump
from .reconnect import BackoffPolicy, RealtimeState, env_backoff_overrides
from .registry import SubscriptionRegistry
from .subscription import _SHUTDOWN, StreamKind, Subscription

_TR_ID_MAP: dict[tuple[StreamKind, str], str] = {
    (StreamKind.trades, "KRX"): KIS_TRADE_TR_ID,
    (StreamKind.trades, "TOTAL"): KIS_TRADE_TR_ID,
    (StreamKind.order_book, "KRX"): KIS_ORDERBOOK_WS_TR_ID,
    (StreamKind.order_book, "TOTAL"): KIS_ORDERBOOK_WS_TR_ID,
    (StreamKind.program_trade, "KRX"): KIS_PROGRAM_TRADE_KRX_WS_TR_ID,
    (StreamKind.program_trade, "NXT"): KIS_PROGRAM_TRADE_NXT_WS_TR_ID,
    (StreamKind.program_trade, "TOTAL"): KIS_PROGRAM_TRADE_TOTAL_WS_TR_ID,
    (StreamKind.member_flow, "KRX"): KIS_MEMBER_KRX_WS_TR_ID,
    (StreamKind.member_flow, "NXT"): KIS_MEMBER_NXT_WS_TR_ID,
    (StreamKind.member_flow, "TOTAL"): KIS_MEMBER_TOTAL_WS_TR_ID,
    (StreamKind.market_status, "KRX"): KIS_MARKET_STATUS_KRX_WS_TR_ID,
    (StreamKind.market_status, "NXT"): KIS_MARKET_STATUS_NXT_WS_TR_ID,
    (StreamKind.market_status, "TOTAL"): KIS_MARKET_STATUS_TOTAL_WS_TR_ID,
}


@dataclass
class RealtimeSessionConfig:
    """Configuration knobs for :class:`KISRealtimeSession`."""

    subscriber_queue_maxsize: int = 1024
    subscribe_ack_timeout: float = 5.0
    shutdown_grace: float = 2.0
    backoff_base: float = 1.0
    backoff_max: float = 30.0
    backoff_jitter: float = 0.2
    max_resubscribe_attempts: int = 5
    per_sub_backoff_base: float = 1.0
    per_sub_backoff_max: float = 30.0
    per_sub_jitter: float = 0.2
    permanent_failure_rt_cds: frozenset[str] = field(default_factory=frozenset)
    overflow_policy: str = "drop_oldest"


StateCallback = Callable[[RealtimeState, RealtimeState], Awaitable[None]]
RecoveryCallback = Callable[[], Awaitable[None]]


class KISRealtimeSession:
    """Multiplexed realtime session built on top of a :class:`KISTransport`.

    The session owns a single websocket and demultiplexes messages across any
    number of :class:`Subscription` handles keyed by ``(tr_id, tr_key)``.
    """

    def __init__(
        self,
        transport: Any,
        config: Optional[RealtimeSessionConfig] = None,
        *,
        on_state_change: Optional[StateCallback] = None,
        on_recovery: Optional[RecoveryCallback] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._transport = transport
        cfg = config or RealtimeSessionConfig()
        eb, em, ej = env_backoff_overrides()
        if eb is not None:
            cfg = replace(cfg, backoff_base=eb)
        if em is not None:
            cfg = replace(cfg, backoff_max=em)
        if ej is not None:
            cfg = replace(cfg, backoff_jitter=ej)
        self._config = cfg
        self._on_state_change = on_state_change
        self._on_recovery = on_recovery
        self._logger = logger or logging.getLogger("kxt.kis.realtime")

        self._registry = SubscriptionRegistry()
        self._state = RealtimeState.IDLE
        self._ws: Any = None
        self._supervisor_task: Optional[asyncio.Task[None]] = None
        self._stop_event = asyncio.Event()
        self._started = False
        self._closed = False
        self._recovery_pending = False
        self._is_reconnect = False
        self._ack_waiters: dict[tuple[str, str], asyncio.Future[bool]] = {}
        self._retry_handles: dict[tuple[str, str], asyncio.TimerHandle] = {}
        self._outbound: Optional[OutboundPump] = None
        self._inbound: Optional[InboundPump] = None

    @property
    def state(self) -> RealtimeState:
        return self._state

    async def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._supervisor_task = asyncio.create_task(self._supervise())

    async def subscribe(self, stream_kind: StreamKind, instrument: Any, *, scope: str = "KRX") -> Subscription:
        if self._closed:
            raise KISRealtimeError("session closed")
        if not self._started:
            await self.start()

        scope_key = str(scope or "KRX").upper()
        tr_id = _TR_ID_MAP[(stream_kind, scope_key)]
        tr_key = str(getattr(instrument, "symbol", "") or "")

        existing = self._registry.get(tr_id, tr_key)
        if existing is not None:
            existing.ref_count += 1
            return existing.subscription

        sub = Subscription(
            stream_kind=stream_kind,
            instrument=instrument,
            tr_id=tr_id,
            tr_key=tr_key,
            queue_maxsize=self._config.subscriber_queue_maxsize,
            overflow_policy=self._config.overflow_policy,
        )
        sub._session = self
        self._registry.add(sub)

        if self._outbound is not None:
            await self._outbound.enqueue(OutboundCommand(kind="subscribe", tr_id=tr_id, tr_key=tr_key))

        fut: asyncio.Future[bool] = asyncio.get_running_loop().create_future()
        self._ack_waiters[(tr_id, tr_key)] = fut
        try:
            await asyncio.wait_for(fut, timeout=self._config.subscribe_ack_timeout)
        except asyncio.TimeoutError:
            # Leave retry to the nack/per-sub scheduler. Caller sees pending sub.
            pass
        except KISSubscriptionError:
            # Permanent failure surfaced via the future; re-raise to caller.
            raise
        finally:
            self._ack_waiters.pop((tr_id, tr_key), None)
        return sub

    async def unsubscribe(self, subscription: Subscription) -> None:
        await self._unsubscribe_internal(subscription)

    async def _unsubscribe_internal(self, subscription: Subscription) -> None:
        _, needs_unsub = self._registry.remove(subscription.tr_id, subscription.tr_key)
        if needs_unsub and self._outbound is not None:
            await self._outbound.enqueue(
                OutboundCommand(kind="unsubscribe", tr_id=subscription.tr_id, tr_key=subscription.tr_key)
            )

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._stop_event.set()

        for handle in self._retry_handles.values():
            handle.cancel()
        self._retry_handles.clear()

        if self._supervisor_task is not None:
            try:
                await asyncio.wait_for(self._supervisor_task, timeout=self._config.shutdown_grace)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._supervisor_task.cancel()
                with contextlib.suppress(Exception, asyncio.CancelledError):
                    await self._supervisor_task

        for entry in self._registry.all_entries():
            with contextlib.suppress(Exception):
                entry.subscription._queue.put_nowait(_SHUTDOWN)
            entry.subscription._closed = True

        await self._set_state(RealtimeState.CLOSED)

    async def _set_state(self, new: RealtimeState) -> None:
        if new == self._state:
            return
        old = self._state
        self._state = new
        if self._on_state_change is not None:
            try:
                await self._on_state_change(old, new)
            except Exception:
                self._logger.exception("on_state_change failed")

    async def _supervise(self) -> None:
        backoff = BackoffPolicy(
            self._config.backoff_base,
            self._config.backoff_max,
            self._config.backoff_jitter,
        )
        attempt_since_approval_refresh = 0
        while not self._closed:
            await self._set_state(RealtimeState.CONNECTING)
            try:
                try:
                    self._ws = await self._transport.connect_websocket()
                except KISApprovalError:
                    if attempt_since_approval_refresh == 0:
                        attempt_since_approval_refresh += 1
                        with contextlib.suppress(Exception):
                            await self._transport.refresh_approval_key()
                        continue
                    raise
                attempt_since_approval_refresh = 0
                backoff.reset()

                cycle_stop = asyncio.Event()
                self._outbound = OutboundPump(
                    ws_getter=lambda: self._ws,
                    registry=self._registry,
                    approval_key_getter=self._transport.get_approval_key,
                    logger=self._logger,
                )
                self._inbound = InboundPump(
                    ws_getter=lambda: self._ws,
                    registry=self._registry,
                    on_ack=self._handle_ack,
                    on_nack=self._handle_nack,
                    on_event=self._handle_event,
                    on_pingpong=self._handle_pingpong,
                    logger=self._logger,
                )

                if self._is_reconnect:
                    self._recovery_pending = True
                    self._registry.reset_pending_for_replay()
                    await self._outbound.enqueue(OutboundCommand(kind="resubscribe_all"))

                await self._set_state(RealtimeState.HEALTHY)

                out_task = asyncio.create_task(self._outbound.run(cycle_stop))
                in_task = asyncio.create_task(self._inbound.run(cycle_stop))
                stop_task = asyncio.create_task(self._stop_event.wait())
                try:
                    _, pending = await asyncio.wait(
                        {out_task, in_task, stop_task},
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                finally:
                    cycle_stop.set()
                    for task in (out_task, in_task, stop_task):
                        if not task.done():
                            task.cancel()
                    for task in (out_task, in_task, stop_task):
                        with contextlib.suppress(Exception, asyncio.CancelledError):
                            await task
                with contextlib.suppress(Exception):
                    if self._ws is not None:
                        await self._ws.close()
                if self._closed or self._stop_event.is_set():
                    break
            except Exception as exc:
                self._logger.warning("session cycle failed: %r", exc)

            if self._closed:
                break
            await self._set_state(RealtimeState.DEGRADED)
            delay = backoff.next()
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=delay)
            except asyncio.TimeoutError:
                pass
            self._is_reconnect = True

        await self._set_state(RealtimeState.CLOSED)

    # ----- frame handlers ------------------------------------------------

    async def _handle_pingpong(self, raw: Any) -> None:
        if self._ws is None:
            return
        raw_bytes = raw if isinstance(raw, (bytes, bytearray)) else str(raw).encode()
        with contextlib.suppress(Exception):
            await self._ws.pong(raw_bytes)

    async def _handle_ack(self, tr_id: str, tr_key: str) -> None:
        self._registry.mark_ack(tr_id, tr_key)
        fut = self._ack_waiters.get((tr_id, tr_key))
        if fut is not None and not fut.done():
            fut.set_result(True)
        handle = self._retry_handles.pop((tr_id, tr_key), None)
        if handle is not None:
            handle.cancel()
        await self._maybe_fire_recovery()

    async def _handle_nack(self, tr_id: str, tr_key: str, rt_cd: str, msg: str) -> None:
        self._registry.mark_nack(tr_id, tr_key, rt_cd, msg)
        entry = self._registry.get(tr_id, tr_key)
        if entry is None:
            return

        permanent = (
            rt_cd in self._config.permanent_failure_rt_cds
            or entry.attempts >= self._config.max_resubscribe_attempts
        )
        if permanent:
            reason = (
                "nack_permanent"
                if rt_cd in self._config.permanent_failure_rt_cds
                else "max_retries_exceeded"
            )
            err = KISSubscriptionError(
                stream_kind=entry.subscription.stream_kind,
                instrument=entry.subscription.instrument,
                reason=reason,
                rt_cd=rt_cd,
                msg=msg,
                attempts=entry.attempts,
            )
            entry.ack_state = "permanently_failed"
            entry.subscription._mark_permanently_failed(err)
            self._registry.purge_permanent(tr_id, tr_key)
            waiter = self._ack_waiters.pop((tr_id, tr_key), None)
            if waiter is not None and not waiter.done():
                waiter.set_exception(err)
            await self._maybe_fire_recovery()
            return

        delay_raw = min(
            self._config.per_sub_backoff_max,
            self._config.per_sub_backoff_base * (2 ** max(0, entry.attempts - 1)),
        )
        delay = max(0.0, delay_raw * (1.0 + random.uniform(-self._config.per_sub_jitter, self._config.per_sub_jitter)))
        loop = asyncio.get_running_loop()

        def _retry() -> None:
            self._retry_handles.pop((tr_id, tr_key), None)
            current = self._registry.get(tr_id, tr_key)
            if current is None:
                return
            current.ack_state = "pending"
            if self._outbound is not None:
                asyncio.create_task(
                    self._outbound.enqueue(OutboundCommand(kind="subscribe", tr_id=tr_id, tr_key=tr_key))
                )

        prev = self._retry_handles.pop((tr_id, tr_key), None)
        if prev is not None:
            prev.cancel()
        self._retry_handles[(tr_id, tr_key)] = loop.call_later(delay, _retry)

    async def _handle_event(self, subscription: Subscription, event: Any) -> None:
        subscription._offer(event)

    async def _maybe_fire_recovery(self) -> None:
        if not self._recovery_pending:
            return
        alive = self._registry.alive_entries()
        if all(entry.ack_state == "acked" for entry in alive):
            self._recovery_pending = False
            if self._on_recovery is not None:
                try:
                    await self._on_recovery()
                except Exception:
                    self._logger.exception("on_recovery failed")
