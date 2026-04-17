"""Transport-level smoke tests."""

from __future__ import annotations

import pytest


async def test_transport_ping_kwargs_passed(monkeypatch):
    """connect_websocket must forward explicit ping/keepalive knobs to websockets.connect."""

    from kxt.clients.kis import transport as transport_module

    captured: dict = {}

    class _FakeWS:
        async def close(self):
            return None

    async def _fake_connect(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return _FakeWS()

    monkeypatch.setattr(transport_module.websockets, "connect", _fake_connect)

    tr = transport_module.KISTransport(app_key="x", app_secret="y")
    try:
        ws = await tr.connect_websocket()
        assert ws is not None
    finally:
        await tr.aclose()

    kwargs = captured["kwargs"]
    assert kwargs["ping_interval"] is None
    assert kwargs["ping_timeout"] is None
    assert kwargs["max_size"] is None
    assert kwargs["close_timeout"] == 2.0
