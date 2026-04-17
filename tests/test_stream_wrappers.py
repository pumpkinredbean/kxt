"""KISClient.stream_trades wrapper smoke test."""

from __future__ import annotations

import asyncio

from kxt import InstrumentRef, RealtimeState, Venue
from kxt.clients.kis.client import KISClient
from kxt.streams.subscriptions import TradeSubscription

from tests.fakes import make_fake_transport, wait_until
from tests.fakes.kis_ws_server import FakeKISWSServer


async def test_stream_trades_wrapper_yields_events_and_closes_sub():
    server = FakeKISWSServer()
    url = await server.__aenter__()
    client = KISClient(app_key="x", app_secret="y")
    try:
        # Replace the transport with one wired to the fake server.
        fake_transport = make_fake_transport(url)
        await client._transport.aclose()
        client._transport = fake_transport

        # Pre-warm the realtime session so the outbound pump is ready
        # before stream_trades enqueues its subscribe command.
        session = client.realtime
        await session.start()
        ok = await wait_until(
            lambda: session.state == RealtimeState.HEALTHY, timeout=3.0
        )
        assert ok, f"session never reached HEALTHY (state={session.state})"

        sub_req = TradeSubscription(
            instrument=InstrumentRef(symbol="005930", venue=Venue.KRX)
        )

        events: list = []

        async def _consume() -> None:
            async for ev in client.stream_trades(sub_req):
                events.append(ev)
                break

        consumer = asyncio.create_task(_consume())

        ok = await wait_until(lambda: server.subscribe_count >= 1, timeout=3.0)
        assert ok, "subscribe frame never reached the fake server"

        await server.send_trade_event("005930", price="71000", qty="10")
        await asyncio.wait_for(consumer, timeout=3.0)

        assert len(events) == 1
        assert getattr(events[0], "instrument").symbol == "005930"

        ok = await wait_until(lambda: server.unsubscribe_count >= 1, timeout=2.0)
        assert ok, (
            f"expected unsubscribe frame after generator close; "
            f"got {server.unsubscribe_count}"
        )
    finally:
        try:
            await client.aclose()
        except Exception:
            pass
        await server.__aexit__(None, None, None)
