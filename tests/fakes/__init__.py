"""Fake helpers for kxt tests."""

from __future__ import annotations

import asyncio
from typing import Any

import websockets

from kxt.clients.kis.transport import KISTransport


def make_fake_transport(ws_url: str) -> KISTransport:
    """Return a KISTransport whose websocket + approval key are wired to a fake server."""

    transport = KISTransport(app_key="test", app_secret="test")

    async def _connect() -> Any:
        return await websockets.connect(
            ws_url,
            ping_interval=None,
            ping_timeout=None,
            max_size=None,
            close_timeout=2.0,
        )

    async def _approval() -> str:
        return "TESTAPPROVAL"

    async def _refresh() -> str:
        return "TESTAPPROVAL"

    transport.connect_websocket = _connect  # type: ignore[assignment]
    transport.get_approval_key = _approval  # type: ignore[assignment]
    transport.refresh_approval_key = _refresh  # type: ignore[assignment]
    return transport


async def wait_until(predicate, *, timeout: float = 2.0, interval: float = 0.02) -> bool:
    """Poll ``predicate`` until truthy or timeout. Returns True on success."""

    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if predicate():
            return True
        await asyncio.sleep(interval)
    return predicate()
