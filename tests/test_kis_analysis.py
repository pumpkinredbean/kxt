"""KIS domestic analysis/ranking smoke tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from kxt import InstrumentRef, KISClient, RankingKind, StreamKind, Venue
from kxt.clients.kis.parsing import (
    KIS_MARKET_STATUS_KRX_WS_TR_ID,
    KIS_PROGRAM_TRADE_KRX_WS_TR_ID,
    parse_market_status_event,
    parse_program_trade_event,
    parse_rankings,
)
from kxt.models import MarketPhase


def test_parse_rankings_common_fields():
    payload = {
        "output": [
            {
                "data_rank": "1",
                "mksc_shrn_iscd": "005930",
                "hts_kor_isnm": "삼성전자",
                "stck_prpr": "70000",
                "prdy_ctrt": "1.23",
                "acml_vol": "1000",
                "acml_tr_pbmn": "70000000",
            }
        ]
    }

    entries = parse_rankings(payload, kind=RankingKind.VOLUME)

    assert entries[0].symbol == "005930"
    assert entries[0].rank == 1
    assert entries[0].price == Decimal("70000")
    assert entries[0].change_rate == Decimal("1.23")


def test_parse_realtime_program_trade_and_status():
    inst = InstrumentRef(symbol="005930", venue=Venue.KRX)
    program_body = "^".join(
        ["005930", "093000", "10", "700000", "15", "1050000", "5", "350000", "", "", ""]
    )
    record = parse_program_trade_event(
        f"0|{KIS_PROGRAM_TRADE_KRX_WS_TR_ID}|001|{program_body}",
        instrument=inst,
    )

    assert record is not None
    assert record.symbol == "005930"
    assert record.net_buy_quantity == Decimal("5")

    status_body = "^".join(["005930", "N", "", "2", "", "", "", "", "", "", "KRX"])
    event = parse_market_status_event(
        f"0|{KIS_MARKET_STATUS_KRX_WS_TR_ID}|001|{status_body}",
        instrument=inst,
    )

    assert event is not None
    assert event.phase == MarketPhase.OPEN


async def test_get_rankings_uses_native_endpoint(monkeypatch):
    client = KISClient(app_key="x", app_secret="y")
    seen = {}

    async def fake_get_json_response(path, *, tr_id, params, tr_cont=""):
        seen.update(path=path, tr_id=tr_id, params=params, tr_cont=tr_cont)

        class Resp:
            payload = {
                "output": [
                    {"data_rank": "1", "mksc_shrn_iscd": "005930", "acml_vol": "10"}
                ]
            }
            tr_cont = ""
            headers = {}

        return Resp()

    monkeypatch.setattr(client._transport, "get_json_response", fake_get_json_response)
    try:
        response = await client.get_rankings(RankingKind.VOLUME, limit=1)
    finally:
        await client.aclose()

    assert seen["tr_id"] == "FHPST01710000"
    assert seen["params"]["FID_COND_SCR_DIV_CODE"] == "20171"
    assert response.entries[0].symbol == "005930"


async def test_get_rankings_value_uses_trade_value_sort(monkeypatch):
    client = KISClient(app_key="x", app_secret="y")
    seen = {}

    async def fake_get_json_response(path, *, tr_id, params, tr_cont=""):
        seen.update(path=path, tr_id=tr_id, params=params, tr_cont=tr_cont)

        class Resp:
            payload = {"output": []}
            tr_cont = ""
            headers = {}

        return Resp()

    monkeypatch.setattr(client._transport, "get_json_response", fake_get_json_response)
    try:
        await client.get_rankings(RankingKind.VALUE, limit=1)
    finally:
        await client.aclose()

    assert seen["tr_id"] == "FHPST01710000"
    assert seen["params"]["FID_BLNG_CLS_CODE"] == "3"


async def test_condition_search_requires_hts_id():
    client = KISClient(app_key="x", app_secret="y")
    try:
        with pytest.raises(Exception):
            await client.get_condition_searches()
    finally:
        await client.aclose()


def test_stream_kind_has_new_analysis_values():
    assert StreamKind.program_trade.value == "program_trade"
    assert StreamKind.member_flow.value == "member_flow"
    assert StreamKind.market_status.value == "market_status"
