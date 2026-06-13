"""Transport-level smoke tests."""

from __future__ import annotations

import httpx
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


async def test_get_json_response_refreshes_expired_access_token(monkeypatch, tmp_path):
    from kxt.clients.kis import transport as transport_module

    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    tr = transport_module.KISTransport(app_key="x", app_secret="y")
    tokens = iter(["expired-token", "fresh-token"])
    seen_authorization: list[str] = []

    async def fake_post_json(path, *, json):
        assert path == "/oauth2/tokenP"
        token = next(tokens)
        return httpx.Response(
            200,
            json={
                "rt_cd": "0",
                "access_token": token,
                "access_token_token_expired": "2999-01-01 00:00:00",
            },
        )

    async def fake_get(path, *, params, headers):
        seen_authorization.append(headers["authorization"])
        if headers["authorization"] == "Bearer expired-token":
            return httpx.Response(
                200,
                json={"rt_cd": "1", "msg_cd": "MCA0017", "msg1": "기간이 만료된 token 입니다."},
            )
        return httpx.Response(200, json={"rt_cd": "0", "output": {"ok": "1"}})

    monkeypatch.setattr(tr, "_post_json", fake_post_json)
    monkeypatch.setattr(tr, "_get", fake_get)
    try:
        response = await tr.get_json_response("/path", tr_id="TR", params={})
    finally:
        await tr.aclose()

    assert response.payload["output"]["ok"] == "1"
    assert seen_authorization == ["Bearer expired-token", "Bearer fresh-token"]
