"""Realtime session smoke tests backed by a fake websocket server."""

from __future__ import annotations

import asyncio
from dataclasses import replace

import pytest

from kxt import (
    InstrumentRef,
    KISRealtimeSession,
    RealtimeSessionConfig,
    RealtimeState,
    StreamKind,
    Venue,
)
from kxt.clients.kis.realtime.reconnect import BackoffPolicy

from tests.fakes import make_fake_transport, wait_until
from tests.fakes.kis_ws_server import FakeKISWSServer


def _fast_config(**overrides) -> RealtimeSessionConfig:
    cfg = RealtimeSessionConfig(
        subscribe_ack_timeout=2.0,
        shutdown_grace=1.0,
        backoff_base=0.05,
        backoff_max=0.2,
        backoff_jitter=0.0,
        per_sub_backoff_base=0.05,
        per_sub_backoff_max=0.2,
        per_sub_jitter=0.0,
    )
    if overrides:
        cfg = replace(cfg, **overrides)
    return cfg


async def _mk_server_session(
    cfg: RealtimeSessionConfig | None = None,
    *,
    on_recovery=None,
) -> tuple[FakeKISWSServer, KISRealtimeSession]:
    server = FakeKISWSServer()
    url = await server.__aenter__()
    transport = make_fake_transport(url)
    session = KISRealtimeSession(
        transport,
        config=cfg or _fast_config(),
        on_recovery=on_recovery,
    )
    return server, session


async def _shutdown(server: FakeKISWSServer, session: KISRealtimeSession) -> None:
    try:
        await session.aclose()
    finally:
        await server.__aexit__(None, None, None)


async def _start_ready(session: KISRealtimeSession) -> None:
    """Start the session and wait until the websocket pumps are ready."""

    await session.start()
    ok = await wait_until(
        lambda: session.state == RealtimeState.HEALTHY, timeout=3.0
    )
    assert ok, f"session never reached HEALTHY (state={session.state})"


async def test_session_subscribe_sends_tr_type_1():
    server, session = await _mk_server_session()
    try:
        await _start_ready(session)
        inst = InstrumentRef(symbol="005930", venue=Venue.KRX)
        await session.subscribe(StreamKind.trades, inst)

        subs = [
            m for m in server.received
            if ((m.get("header") or {}).get("tr_type") == "1")
        ]
        assert subs, "expected at least one tr_type='1' subscribe frame"
        keys = {((m.get("body") or {}).get("input") or {}).get("tr_key") for m in subs}
        assert "005930" in keys
    finally:
        await _shutdown(server, session)


async def test_session_unsubscribe_sends_tr_type_2():
    server, session = await _mk_server_session()
    try:
        await _start_ready(session)
        inst = InstrumentRef(symbol="005930", venue=Venue.KRX)
        sub = await session.subscribe(StreamKind.trades, inst)
        assert server.subscribe_count >= 1

        await sub.aclose()

        ok = await wait_until(lambda: server.unsubscribe_count >= 1, timeout=2.0)
        assert ok, f"expected unsubscribe frame; got {server.unsubscribe_count}"
        unsubs = [
            m for m in server.received
            if ((m.get("header") or {}).get("tr_type") == "2")
        ]
        assert unsubs
    finally:
        await _shutdown(server, session)


async def test_session_demux_routes_per_symbol():
    server, session = await _mk_server_session()
    try:
        await _start_ready(session)
        a = InstrumentRef(symbol="005930", venue=Venue.KRX)
        b = InstrumentRef(symbol="034020", venue=Venue.KRX)
        sub_a = await session.subscribe(StreamKind.trades, a)
        sub_b = await session.subscribe(StreamKind.trades, b)

        await server.send_trade_event("005930", price="71000")
        await server.send_trade_event("034020", price="15000")

        async def _first(sub):
            async for ev in sub.events():
                return ev
            return None

        ev_a = await asyncio.wait_for(_first(sub_a), timeout=2.0)
        ev_b = await asyncio.wait_for(_first(sub_b), timeout=2.0)

        assert getattr(ev_a, "symbol") == "005930"
        assert getattr(ev_b, "symbol") == "034020"
    finally:
        await _shutdown(server, session)


async def test_session_reconnect_replays_subscriptions():
    server, session = await _mk_server_session()
    try:
        await _start_ready(session)
        a = InstrumentRef(symbol="005930", venue=Venue.KRX)
        b = InstrumentRef(symbol="034020", venue=Venue.KRX)
        await session.subscribe(StreamKind.trades, a)
        await session.subscribe(StreamKind.trades, b)

        initial = server.subscribe_count
        assert initial >= 2

        await server.drop()

        ok = await wait_until(
            lambda: server.subscribe_count >= initial + 2,
            timeout=3.0,
        )
        assert ok, (
            f"expected re-subscribe after drop; sub_count={server.subscribe_count} "
            f"initial={initial}"
        )
        keys = [
            ((m.get("body") or {}).get("input") or {}).get("tr_key")
            for m in server.received
            if (m.get("header") or {}).get("tr_type") == "1"
        ]
        assert keys.count("005930") >= 2
        assert keys.count("034020") >= 2
    finally:
        await _shutdown(server, session)


def test_session_backoff_capped_at_30s():
    policy = BackoffPolicy(base=1.0, cap=30.0, jitter=0.0)
    delays = [policy.next() for _ in range(20)]
    assert max(delays) <= 30.0
    assert delays[0] == 1.0
    assert delays[-1] == 30.0


async def test_session_recovery_callback_fires_once():
    fired = 0
    done = asyncio.Event()

    async def _on_recovery():
        nonlocal fired
        fired += 1
        done.set()

    server, session = await _mk_server_session(on_recovery=_on_recovery)
    try:
        await _start_ready(session)
        a = InstrumentRef(symbol="005930", venue=Venue.KRX)
        b = InstrumentRef(symbol="034020", venue=Venue.KRX)
        await session.subscribe(StreamKind.trades, a)
        await session.subscribe(StreamKind.trades, b)

        await server.drop()

        try:
            await asyncio.wait_for(done.wait(), timeout=3.0)
        except asyncio.TimeoutError:
            pytest.fail(f"on_recovery never fired (count={fired})")

        await asyncio.sleep(0.25)
        assert fired == 1
    finally:
        await _shutdown(server, session)


async def test_subscribe_refcount_same_handle():
    server, session = await _mk_server_session()
    try:
        await _start_ready(session)
        inst = InstrumentRef(symbol="005930", venue=Venue.KRX)
        sub_a = await session.subscribe(StreamKind.trades, inst)
        sub_b = await session.subscribe(StreamKind.trades, inst)
        assert sub_a is sub_b

        # Exactly one subscribe frame should have reached the server.
        assert server.subscribe_count == 1

        # First aclose decrements refcount and must not emit an unsubscribe frame.
        await sub_a.aclose()
        await asyncio.sleep(0.1)
        assert server.unsubscribe_count == 0
    finally:
        await _shutdown(server, session)


async def test_unsubscribe_idempotent():
    server, session = await _mk_server_session()
    try:
        await _start_ready(session)
        inst = InstrumentRef(symbol="005930", venue=Venue.KRX)
        sub = await session.subscribe(StreamKind.trades, inst)

        await sub.aclose()
        await sub.aclose()

        ok = await wait_until(lambda: server.unsubscribe_count >= 1, timeout=2.0)
        assert ok
        await asyncio.sleep(0.15)
        assert server.unsubscribe_count == 1
    finally:
        await _shutdown(server, session)
