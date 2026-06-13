from __future__ import annotations

import json
from decimal import Decimal

import httpx
import pytest

from kxt import OrderLifecycleState, OrderSide, OrderType, TossInvestClient


def _token_response() -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "access_token": "token-1",
            "token_type": "Bearer",
            "expires_in": 3600,
        },
    )


@pytest.mark.asyncio
async def test_tossinvest_get_quote_uses_oauth_token(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    seen: list[tuple[str, str | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.url.path, request.headers.get("authorization")))
        if request.url.path == "/oauth2/token":
            assert b"grant_type=client_credentials" in request.content
            assert b"client_id=cid" in request.content
            return _token_response()
        assert request.url.path == "/api/v1/prices"
        assert request.url.params["symbols"] == "005930"
        return httpx.Response(
            200,
            json={
                "result": [
                    {
                        "symbol": "005930",
                        "timestamp": "2026-03-25T09:30:00.123+09:00",
                        "lastPrice": "72000",
                        "currency": "KRW",
                    }
                ]
            },
        )

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    async with TossInvestClient(
        client_id="cid",
        client_secret="secret",
        http_client=http_client,
    ) as client:
        quote = await client.get_quote("005930")

    assert quote.last == Decimal("72000")
    assert quote.occurred_at.isoformat() == "2026-03-25T09:30:00.123000+09:00"
    assert seen == [
        ("/oauth2/token", None),
        ("/api/v1/prices", "Bearer token-1"),
    ]


@pytest.mark.asyncio
async def test_tossinvest_refreshes_invalid_access_token(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    issued_tokens: list[str] = []
    seen_auth: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth2/token":
            token = f"token-{len(issued_tokens) + 1}"
            issued_tokens.append(token)
            return httpx.Response(
                200,
                json={
                    "access_token": token,
                    "token_type": "Bearer",
                    "expires_in": 3600,
                },
            )

        assert request.url.path == "/api/v1/prices"
        seen_auth.append(request.headers.get("authorization"))
        if request.headers.get("authorization") == "Bearer token-1":
            return httpx.Response(
                401,
                json={"error": {"code": "UNAUTHORIZED", "message": "유효하지 않은 토큰입니다."}},
            )
        return httpx.Response(
            200,
            json={
                "result": [
                    {
                        "symbol": "005930",
                        "timestamp": "2026-03-25T09:30:00+09:00",
                        "lastPrice": "72000",
                    }
                ]
            },
        )

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    async with TossInvestClient(
        client_id="cid",
        client_secret="secret",
        http_client=http_client,
    ) as client:
        quote = await client.get_quote("005930")

    assert quote.last == Decimal("72000")
    assert issued_tokens == ["token-1", "token-2"]
    assert seen_auth == ["Bearer token-1", "Bearer token-2"]


@pytest.mark.asyncio
async def test_tossinvest_get_quotes_batches_symbols(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    seen_params: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth2/token":
            return _token_response()
        assert request.url.path == "/api/v1/prices"
        seen_params.append(request.url.params["symbols"])
        return httpx.Response(
            200,
            json={
                "result": [
                    {
                        "symbol": "000660",
                        "timestamp": "2026-03-25T09:31:00+09:00",
                        "lastPrice": "180000",
                    },
                    {
                        "symbol": "005930",
                        "timestamp": "2026-03-25T09:30:00+09:00",
                        "lastPrice": "72000",
                    },
                ]
            },
        )

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    async with TossInvestClient(
        client_id="cid",
        client_secret="secret",
        http_client=http_client,
    ) as client:
        response = await client.get_quotes(["005930", "000660"])

    assert seen_params == ["005930,000660"]
    assert [quote.symbol for quote in response.quotes] == ["005930", "000660"]
    assert [quote.last for quote in response.quotes] == [Decimal("72000"), Decimal("180000")]


@pytest.mark.asyncio
async def test_tossinvest_get_bars_aggregates_minute_bars(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth2/token":
            return _token_response()
        assert request.url.path == "/api/v1/candles"
        assert request.url.params["interval"] == "1m"
        return httpx.Response(
            200,
            json={
                "result": {
                    "candles": [
                        {
                            "timestamp": "2026-03-25T09:01:00+09:00",
                            "openPrice": "101",
                            "highPrice": "102",
                            "lowPrice": "100",
                            "closePrice": "101",
                            "volume": "20",
                            "currency": "KRW",
                        },
                        {
                            "timestamp": "2026-03-25T09:00:00+09:00",
                            "openPrice": "100",
                            "highPrice": "101",
                            "lowPrice": "99",
                            "closePrice": "100",
                            "volume": "10",
                            "currency": "KRW",
                        },
                    ],
                    "nextBefore": None,
                }
            },
        )

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    async with TossInvestClient(
        client_id="cid",
        client_secret="secret",
        http_client=http_client,
    ) as client:
        response = await client.get_bars("005930", timeframe="2m")

    assert response.timeframe == "2m"
    assert len(response.bars) == 1
    bar = response.bars[0]
    assert bar.open == Decimal("100")
    assert bar.high == Decimal("102")
    assert bar.low == Decimal("99")
    assert bar.close == Decimal("101")
    assert bar.volume == Decimal("30")


@pytest.mark.asyncio
async def test_tossinvest_account_reads_use_account_header(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    account_headers: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth2/token":
            return _token_response()
        account_headers.append(request.headers.get("X-Tossinvest-Account"))
        if request.url.path == "/api/v1/accounts":
            return httpx.Response(
                200,
                json={
                    "result": [
                        {
                            "accountNo": "12345678901",
                            "accountSeq": 7,
                            "accountType": "BROKERAGE",
                        }
                    ]
                },
            )
        if request.url.path == "/api/v1/holdings":
            return httpx.Response(
                200,
                json={
                    "result": {
                        "items": [
                            {
                                "symbol": "005930",
                                "name": "삼성전자",
                                "marketCountry": "KR",
                                "currency": "KRW",
                                "quantity": "3",
                                "lastPrice": "72000",
                                "averagePurchasePrice": "70000",
                                "profitLoss": {
                                    "amount": "6000",
                                    "amountAfterCost": "5000",
                                    "rate": "0.0285",
                                    "rateAfterCost": "0.0238",
                                },
                            }
                        ]
                    }
                },
            )
        raise AssertionError(request.url.path)

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    async with TossInvestClient(
        client_id="cid",
        client_secret="secret",
        account_seq="7",
        http_client=http_client,
    ) as client:
        accounts = await client.get_accounts()
        positions = await client.get_positions()

    assert accounts.accounts[0].account_id == "7"
    assert positions.positions[0].symbol == "005930"
    assert positions.positions[0].quantity == Decimal("3")
    assert account_headers == [None, "7"]


@pytest.mark.asyncio
async def test_tossinvest_submit_order_sends_client_order_id(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    captured_body: dict[str, object] = {}
    captured_account: str | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_account
        if request.url.path == "/oauth2/token":
            return _token_response()
        assert request.url.path == "/api/v1/orders"
        captured_account = request.headers.get("X-Tossinvest-Account")
        captured_body.update(json.loads(request.content.decode("utf-8")))
        return httpx.Response(
            200,
            json={"result": {"orderId": "ord-1", "clientOrderId": "cli-1"}},
        )

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    async with TossInvestClient(
        client_id="cid",
        client_secret="secret",
        http_client=http_client,
    ) as client:
        response = await client.submit_order(
            symbol="005930",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=1,
            limit_price=70000,
            account_seq="7",
            client_order_id="cli-1",
            confirm_high_value_order=True,
        )

    assert captured_account == "7"
    assert captured_body == {
        "symbol": "005930",
        "side": "BUY",
        "orderType": "LIMIT",
        "confirmHighValueOrder": True,
        "clientOrderId": "cli-1",
        "quantity": "1",
        "price": "70000",
    }
    assert response.acknowledgement.state == OrderLifecycleState.ACKNOWLEDGED
    assert response.acknowledgement.order_ref is not None
    assert response.acknowledgement.order_ref.provider == "tossinvest"
    assert response.acknowledgement.order_ref.order_id == "ord-1"
