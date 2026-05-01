"""KIS domestic analysis/ranking smoke tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from datetime import date

from kxt import InstrumentRef, KISClient, RankingKind, StreamKind, Venue
from kxt.clients.kis.parsing import (
    KIS_MARKET_CALENDAR_PATH,
    KIS_MARKET_CALENDAR_TR_ID,
    KIS_MARKET_STATUS_KRX_WS_TR_ID,
    KIS_PROGRAM_TRADE_KRX_WS_TR_ID,
    parse_market_calendar,
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


def test_parse_market_calendar_filters_and_sorts_rows():
    payload = {
        "output2": [
            {"bass_dt": "20250102", "bzdy_yn": "Y", "tr_day_yn": "Y", "opnd_yn": "Y", "sttl_day_yn": "Y"},
            {"bass_dt": "20250101", "bzdy_yn": "N", "tr_day_yn": "N", "opnd_yn": "N", "sttl_day_yn": "N"},
            {"bass_dt": "20250103", "bzdy_yn": "Y", "tr_day_yn": "Y", "sttl_day_yn": "Y"},
        ]
    }

    response = parse_market_calendar(
        payload,
        market="KRX",
        start=date(2025, 1, 1),
        end=date(2025, 1, 2),
    )

    assert [day.date for day in response.days] == [date(2025, 1, 1), date(2025, 1, 2)]
    assert response.days[0].is_open is False
    assert response.days[1].business_day is True
    assert response.days[1].raw == payload["output2"][0]


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


async def test_get_market_calendar_uses_kis_holiday_endpoint(monkeypatch):
    client = KISClient(app_key="x", app_secret="y")
    seen = []

    async def fake_get_json_response(path, *, tr_id, params, tr_cont=""):
        seen.append((path, tr_id, dict(params), tr_cont))

        class Resp:
            payload = {
                "output": [
                    {"bass_dt": "20250101", "bzdy_yn": "N", "tr_day_yn": "N", "opnd_yn": "N", "sttl_day_yn": "N"},
                    {"bass_dt": "20250102", "bzdy_yn": "Y", "tr_day_yn": "Y", "opnd_yn": "Y", "sttl_day_yn": "Y"},
                ]
            }
            tr_cont = ""
            headers = {}

        return Resp()

    monkeypatch.setattr(client._transport, "get_json_response", fake_get_json_response)
    try:
        response = await client.get_market_calendar(date(2025, 1, 1), date(2025, 1, 2))
    finally:
        await client.aclose()

    assert seen[0][0] == KIS_MARKET_CALENDAR_PATH
    assert seen[0][1] == KIS_MARKET_CALENDAR_TR_ID
    assert seen[0][2] == {"BASS_DT": "20250101", "CTX_AREA_FK": "", "CTX_AREA_NK": ""}
    assert [day.is_open for day in response.days] == [False, True]


async def test_get_market_calendar_paginates_with_body_context(monkeypatch):
    client = KISClient(app_key="x", app_secret="y")
    seen = []

    async def fake_get_json_response(path, *, tr_id, params, tr_cont=""):
        seen.append((dict(params), tr_cont))

        class Resp:
            payload = {
                "output": [{"bass_dt": "20250101", "opnd_yn": "N"}],
                "ctx_area_fk": "FK1",
                "ctx_area_nk": "NK1",
            }
            tr_cont = "M"
            headers = {}

        if len(seen) == 2:
            Resp.payload = {"output": [{"bass_dt": "20250102", "opnd_yn": "Y"}]}
            Resp.tr_cont = ""
        return Resp()

    monkeypatch.setattr(client._transport, "get_json_response", fake_get_json_response)
    try:
        response = await client.get_market_calendar(date(2025, 1, 1), date(2025, 1, 2))
    finally:
        await client.aclose()

    assert seen[1] == ({"BASS_DT": "20250101", "CTX_AREA_FK": "FK1", "CTX_AREA_NK": "NK1"}, "N")
    assert [day.date for day in response.days] == [date(2025, 1, 1), date(2025, 1, 2)]


async def test_is_market_open_returns_unknown_day_when_row_missing(monkeypatch):
    client = KISClient(app_key="x", app_secret="y")

    async def fake_get_json_response(path, *, tr_id, params, tr_cont=""):
        class Resp:
            payload = {"output": []}
            tr_cont = ""
            headers = {}

        return Resp()

    monkeypatch.setattr(client._transport, "get_json_response", fake_get_json_response)
    try:
        day = await client.is_market_open(date(2025, 1, 1))
    finally:
        await client.aclose()

    assert day.date == date(2025, 1, 1)
    assert day.is_open is None
    assert day.raw is None


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
