"""KIS payload parsing isolated from the public package surface."""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import UTC, date, datetime, time
from decimal import Decimal

from kxt.models import (
    AccountEquitySnapshot,
    AccountSummary,
    BarTimeframe,
    BuyingPowerSnapshot,
    FillNotificationEvent,
    InstrumentRef,
    IntradayBar,
    InvestorFlowBucket,
    InvestorFlowResponse,
    MarketBar,
    MarketPhase,
    MarketStatusResponse,
    OpenOrder,
    OrderAcceptedEvent,
    OrderAmendAckEvent,
    OrderBookSnapshot,
    OrderCancelAckEvent,
    OrderCorrelationKey,
    OrderHistoryRecord,
    OrderHistorySummary,
    OrderLifecycleState,
    OrderRejectedEvent,
    OrderSide,
    OrderType,
    PositionDayActivity,
    PositionLot,
    ProviderOrderRef,
    QuoteLevel,
    QuoteSnapshot,
    Trade,
    TradeSide,
    Venue,
)

from .exceptions import KISAPIError

KIS_CURRENT_MINUTE_PATH = "/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice"
KIS_CURRENT_MINUTE_TR_ID = "FHKST03010200"
KIS_HISTORICAL_MINUTE_PATH = "/uapi/domestic-stock/v1/quotations/inquire-time-dailychartprice"
KIS_HISTORICAL_MINUTE_TR_ID = "FHKST03010230"
KIS_PERIOD_BARS_PATH = "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
KIS_PERIOD_BARS_TR_ID = "FHKST03010100"
KIS_RECENT_TRADES_PATH = "/uapi/domestic-stock/v1/quotations/inquire-time-itemconclusion"
KIS_RECENT_TRADES_TR_ID = "FHPST01060000"
KIS_QUOTE_PATH = "/uapi/domestic-stock/v1/quotations/inquire-price"
KIS_QUOTE_TR_ID = "FHKST01010100"
KIS_ORDERBOOK_PATH = "/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn"
KIS_ORDERBOOK_TR_ID = "FHKST01010200"
KIS_INVESTOR_FLOW_PATH = "/uapi/domestic-stock/v1/quotations/inquire-investor"
KIS_INVESTOR_FLOW_TR_ID = "FHKST01010900"
KIS_TRADE_TR_ID = "H0STCNT0"
KIS_ORDERBOOK_WS_TR_ID = "H0STASP0"
KIS_TRADE_FIELDS = (
    "MKSC_SHRN_ISCD",
    "STCK_CNTG_HOUR",
    "STCK_PRPR",
    "PRDY_VRSS_SIGN",
    "PRDY_VRSS",
    "PRDY_CTRT",
    "WGHN_AVRG_STCK_PRC",
    "STCK_OPRC",
    "STCK_HGPR",
    "STCK_LWPR",
    "ASKP1",
    "BIDP1",
    "CNTG_VOL",
    "ACML_VOL",
    "ACML_TR_PBMN",
    "SELN_CNTG_CSNU",
    "SHNU_CNTG_CSNU",
    "NTBY_CNTG_CSNU",
    "CTTR",
    "SELN_CNTG_SMTN",
    "SHNU_CNTG_SMTN",
    "CCLD_DVSN",
    "SHNU_RATE",
    "PRDY_VOL_VRSS_ACML_VOL_RATE",
    "OPRC_HOUR",
    "OPRC_VRSS_PRPR_SIGN",
    "OPRC_VRSS_PRPR",
    "HGPR_HOUR",
    "HGPR_VRSS_PRPR_SIGN",
    "HGPR_VRSS_PRPR",
    "LWPR_HOUR",
    "LWPR_VRSS_PRPR_SIGN",
    "LWPR_VRSS_PRPR",
    "BSOP_DATE",
    "NEW_MKOP_CLS_CODE",
    "TRHT_YN",
    "ASKP_RSQN1",
    "BIDP_RSQN1",
    "TOTAL_ASKP_RSQN",
    "TOTAL_BIDP_RSQN",
    "VOL_TNRT",
    "PRDY_SMNS_HOUR_ACML_VOL",
    "PRDY_SMNS_HOUR_ACML_VOL_RATE",
    "HOUR_CLS_CODE",
    "MRKT_TRTM_CLS_CODE",
    "VI_STND_PRC",
)
KIS_ORDERBOOK_FIELDS = (
    "MKSC_SHRN_ISCD",
    "BSOP_HOUR",
    "HOUR_CLS_CODE",
    "ASKP1",
    "ASKP2",
    "ASKP3",
    "ASKP4",
    "ASKP5",
    "ASKP6",
    "ASKP7",
    "ASKP8",
    "ASKP9",
    "ASKP10",
    "BIDP1",
    "BIDP2",
    "BIDP3",
    "BIDP4",
    "BIDP5",
    "BIDP6",
    "BIDP7",
    "BIDP8",
    "BIDP9",
    "BIDP10",
    "ASKP_RSQN1",
    "ASKP_RSQN2",
    "ASKP_RSQN3",
    "ASKP_RSQN4",
    "ASKP_RSQN5",
    "ASKP_RSQN6",
    "ASKP_RSQN7",
    "ASKP_RSQN8",
    "ASKP_RSQN9",
    "ASKP_RSQN10",
    "BIDP_RSQN1",
    "BIDP_RSQN2",
    "BIDP_RSQN3",
    "BIDP_RSQN4",
    "BIDP_RSQN5",
    "BIDP_RSQN6",
    "BIDP_RSQN7",
    "BIDP_RSQN8",
    "BIDP_RSQN9",
    "BIDP_RSQN10",
    "TOTAL_ASKP_RSQN",
    "TOTAL_BIDP_RSQN",
    "OVTM_TOTAL_ASKP_RSQN",
    "OVTM_TOTAL_BIDP_RSQN",
    "ANTC_CNPR",
    "ANTC_CNQN",
    "ANTC_VOL",
    "ANTC_CNTG_VRSS",
    "ANTC_CNTG_VRSS_SIGN",
    "ANTC_CNTG_PRDY_CTRT",
    "ACML_VOL",
    "TOTAL_ASKP_RSQN_ICDC",
    "TOTAL_BIDP_RSQN_ICDC",
    "OVTM_TOTAL_ASKP_ICDC",
    "OVTM_TOTAL_BIDP_ICDC",
    "STCK_DEAL_CLS_CODE",
)


def parse_intraday_bars(
    payload: dict[str, object],
    *,
    instrument: InstrumentRef,
    interval_minutes: int,
) -> tuple[IntradayBar, ...]:
    dated_rows = _normalize_minute_rows(payload.get("output2"), instrument=instrument, default_trade_date=_parse_trade_date(payload.get("output1")))
    if interval_minutes == 1:
        return tuple(
            IntradayBar(
                instrument=item["instrument"],
                opened_at=item["opened_at"],
                interval_minutes=1,
                open=item["open"],
                high=item["high"],
                low=item["low"],
                close=item["close"],
                volume=item["volume"],
                notional=item["notional"],
            )
            for item in dated_rows
        )
    return tuple(_aggregate_bars(dated_rows, interval_minutes))


def parse_market_bars(
    payload: dict[str, object],
    *,
    instrument: InstrumentRef,
    timeframe: BarTimeframe,
    interval_minutes: int = 1,
) -> tuple[MarketBar, ...]:
    if timeframe == BarTimeframe.MINUTE:
        rows = _normalize_minute_rows(payload.get("output2"), instrument=instrument, default_trade_date=_parse_trade_date(payload.get("output1")))
        if interval_minutes == 1:
            return tuple(_minute_row_to_market_bar(item) for item in rows)
        return tuple(_intraday_to_market_bar(bar) for bar in _aggregate_bars(rows, interval_minutes))

    rows = payload.get("output2")
    if not isinstance(rows, list):
        return ()
    return tuple(_parse_period_bar(row, instrument=instrument, timeframe=timeframe) for row in rows if isinstance(row, dict))


def parse_trade_event(raw_message: str, *, instrument: InstrumentRef) -> Trade | None:
    if not raw_message:
        return None
    if raw_message[0] == "{":
        data = json.loads(raw_message)
        header = data.get("header") or {}
        if header.get("tr_id") == "PINGPONG":
            return None
        body = data.get("body") or {}
        if body and body.get("rt_cd") not in (None, "0"):
            raise KISAPIError(str(body.get("msg1") or "KIS websocket subscription failed"), code=str(body.get("msg_cd") or body.get("rt_cd") or ""))
        return None
    if raw_message[0] not in {"0", "1"}:
        return None

    parts = raw_message.split("|", 3)
    if len(parts) != 4 or parts[1] != KIS_TRADE_TR_ID:
        return None
    fields = dict(zip(KIS_TRADE_FIELDS, parts[3].split("^"), strict=False))

    occurred_at = _parse_market_datetime(str(fields.get("BSOP_DATE") or ""), str(fields.get("STCK_CNTG_HOUR") or ""))
    price = _to_decimal(fields.get("STCK_PRPR"))
    quantity = _to_decimal(fields.get("CNTG_VOL"))
    if occurred_at is None or price is None or quantity is None:
        return None

    symbol = str(fields.get("MKSC_SHRN_ISCD") or instrument.symbol)
    return Trade(
        instrument=InstrumentRef(
            symbol=symbol,
            venue=instrument.venue or Venue.KRX,
            market_segment=instrument.market_segment,
            instrument_id=symbol,
        ),
        occurred_at=occurred_at,
        price=price,
        quantity=quantity,
        side=_parse_trade_side(fields.get("CCLD_DVSN")),
        sequence=str(fields.get("CTTR") or "").strip() or None,
    )


def parse_recent_trades(payload: dict[str, object], *, instrument: InstrumentRef) -> tuple[Trade, ...]:
    output1 = payload.get("output1")
    default_trade_date = _parse_trade_date(output1)
    rows = payload.get("output2")
    if not isinstance(rows, list):
        return ()

    trades: list[Trade] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        occurred_at = _parse_market_datetime(str(row.get("stck_bsop_date") or "") or default_trade_date.strftime("%Y%m%d"), str(row.get("stck_cntg_hour") or ""))
        price = _to_decimal(row.get("stck_prpr") or row.get("stck_pbpr"))
        quantity = _to_decimal(row.get("cnqn") or row.get("cntg_vol"))
        if occurred_at is None or price is None or quantity is None:
            continue
        sequence = f"{occurred_at.strftime('%H%M%S')}-{index}"
        ask_price = _to_decimal(row.get("askp") or row.get("ASKP"))
        bid_price = _to_decimal(row.get("bidp") or row.get("BIDP"))
        trades.append(
            Trade(
                instrument=instrument,
                occurred_at=occurred_at,
                price=price,
                quantity=quantity,
                side=_parse_recent_trade_side(row, price=price),
                sequence=sequence,
                ask_price=ask_price,
                bid_price=bid_price,
            )
        )
    return tuple(sorted(trades, key=lambda item: (item.occurred_at, str(item.sequence or ""))))


def parse_quote_snapshot(payload: dict[str, object], *, instrument: InstrumentRef) -> QuoteSnapshot:
    output = payload.get("output") if isinstance(payload.get("output"), dict) else payload.get("output1")
    if not isinstance(output, dict):
        raise KISAPIError("KIS quote response did not include an output payload")

    occurred_at = _parse_market_datetime_from_fields(output) or datetime.now(UTC)
    last = _required_decimal(output, "stck_prpr")
    return QuoteSnapshot(
        instrument=instrument,
        occurred_at=occurred_at,
        last=last,
        open=_to_decimal(output.get("stck_oprc")),
        high=_to_decimal(output.get("stck_hgpr")),
        low=_to_decimal(output.get("stck_lwpr")),
        previous_close=_to_decimal(output.get("stck_sdpr")),
        change=_to_decimal(output.get("prdy_vrss")),
        change_rate=_to_decimal(output.get("prdy_ctrt")),
        volume=_to_decimal(output.get("acml_vol")),
        notional=_to_decimal(output.get("acml_tr_pbmn")),
    )


def parse_market_status(payload: dict[str, object], *, instrument: InstrumentRef) -> MarketStatusResponse:
    output = payload.get("output") if isinstance(payload.get("output"), dict) else payload.get("output1")
    if not isinstance(output, dict):
        raise KISAPIError("KIS market status response did not include an output payload")

    occurred_at = _parse_market_datetime_from_fields(output) or datetime.now(UTC)
    phase = _parse_market_phase(output)
    return MarketStatusResponse(
        phase=phase,
        occurred_at=occurred_at,
    )


def parse_orderbook_snapshot(payload: dict[str, object], *, instrument: InstrumentRef) -> OrderBookSnapshot:
    output = payload.get("output1") if isinstance(payload.get("output1"), dict) else payload.get("output")
    if not isinstance(output, dict):
        raise KISAPIError("KIS order book response did not include an output payload")
    return _parse_orderbook_fields(output, instrument=instrument)


def parse_orderbook_event(raw_message: str, *, instrument: InstrumentRef) -> OrderBookSnapshot | None:
    if not raw_message:
        return None
    if raw_message[0] == "{":
        data = json.loads(raw_message)
        header = data.get("header") or {}
        if header.get("tr_id") == "PINGPONG":
            return None
        body = data.get("body") or {}
        if body and body.get("rt_cd") not in (None, "0"):
            raise KISAPIError(str(body.get("msg1") or "KIS websocket subscription failed"), code=str(body.get("msg_cd") or body.get("rt_cd") or ""))
        return None
    if raw_message[0] not in {"0", "1"}:
        return None

    parts = raw_message.split("|", 3)
    if len(parts) != 4 or parts[1] != KIS_ORDERBOOK_WS_TR_ID:
        return None
    fields = dict(zip(KIS_ORDERBOOK_FIELDS, parts[3].split("^"), strict=False))
    return _parse_orderbook_fields(fields, instrument=instrument)


def parse_investor_flow(payload: dict[str, object], *, instrument: InstrumentRef) -> InvestorFlowResponse:
    output = payload.get("output")
    if isinstance(output, dict):
        row = output
    elif isinstance(output, list):
        row = next((item for item in output if isinstance(item, dict)), None)
        if row is None:
            raise KISAPIError("KIS investor-flow response did not include an output row")
    else:
        raise KISAPIError("KIS investor-flow response did not include an output payload")

    as_of_date = _parse_trade_date(row)
    return InvestorFlowResponse(
        as_of_date=as_of_date,
        retail=_investor_flow_bucket(row, prefix="prsn"),
        foreign=_investor_flow_bucket(row, prefix="frgn"),
        institution=_investor_flow_bucket(row, prefix="orgn"),
    )


def _investor_flow_bucket(row: dict[str, object], *, prefix: str) -> InvestorFlowBucket:
    return InvestorFlowBucket(
        buy_quantity=_to_decimal(row.get(f"{prefix}_shnu_vol")),
        sell_quantity=_to_decimal(row.get(f"{prefix}_seln_vol")),
        net_buy_quantity=_to_decimal(row.get(f"{prefix}_ntby_qty")),
        buy_notional=_to_decimal(row.get(f"{prefix}_shnu_tr_pbmn")),
        sell_notional=_to_decimal(row.get(f"{prefix}_seln_tr_pbmn")),
        net_buy_notional=_to_decimal(row.get(f"{prefix}_ntby_tr_pbmn")),
    )


def websocket_subscription_message(
    *,
    approval_key: str,
    symbol: str,
    tr_id: str = KIS_TRADE_TR_ID,
    tr_type: str = "1",
) -> dict[str, object]:
    return {
        "header": {
            "approval_key": approval_key,
            "content-type": "utf-8",
            "custtype": "P",
            "tr_type": tr_type,
        },
        "body": {"input": {"tr_id": tr_id, "tr_key": symbol}},
    }


def _parse_orderbook_fields(fields: dict[str, object], *, instrument: InstrumentRef) -> OrderBookSnapshot:
    occurred_at = _parse_market_datetime_from_fields(fields) or datetime.now(UTC)
    asks = _parse_quote_levels(fields, price_prefix="askp", quantity_prefix="askp_rsqn")
    bids = _parse_quote_levels(fields, price_prefix="bidp", quantity_prefix="bidp_rsqn")
    return OrderBookSnapshot(
        instrument=InstrumentRef(
            symbol=str(fields.get("mksc_shrn_iscd") or fields.get("MKSC_SHRN_ISCD") or instrument.symbol),
            venue=instrument.venue or Venue.KRX,
            market_segment=instrument.market_segment,
            instrument_id=instrument.instrument_id or instrument.symbol,
            name=instrument.name,
            isin=instrument.isin,
            asset_class=instrument.asset_class,
            instrument_type=instrument.instrument_type,
        ),
        occurred_at=occurred_at,
        asks=asks,
        bids=bids,
        total_ask_quantity=_to_decimal(fields.get("total_askp_rsqn") or fields.get("TOTAL_ASKP_RSQN")),
        total_bid_quantity=_to_decimal(fields.get("total_bidp_rsqn") or fields.get("TOTAL_BIDP_RSQN")),
    )


def _parse_quote_levels(fields: dict[str, object], *, price_prefix: str, quantity_prefix: str) -> tuple[QuoteLevel, ...]:
    levels: list[QuoteLevel] = []
    for level in range(1, 11):
        price = _to_decimal(fields.get(f"{price_prefix}{level}") or fields.get(f"{price_prefix.upper()}{level}"))
        quantity = _to_decimal(fields.get(f"{quantity_prefix}{level}") or fields.get(f"{quantity_prefix.upper()}{level}"))
        if price is None or quantity is None:
            continue
        levels.append(QuoteLevel(price=price, quantity=quantity))
    return tuple(levels)


def _parse_market_phase(fields: dict[str, object]) -> MarketPhase:
    halt = str(fields.get("trht_yn") or fields.get("TRHT_YN") or "").strip().upper()
    if halt == "Y":
        return MarketPhase.HALTED

    state = str(fields.get("new_mkop_cls_code") or fields.get("NEW_MKOP_CLS_CODE") or "").strip()
    if state == "2":
        return MarketPhase.OPEN
    if state == "3":
        return MarketPhase.AFTER_HOURS
    if state == "4":
        return MarketPhase.CLOSED
    if state == "1":
        return MarketPhase.PREOPEN

    time_state = str(fields.get("mrkt_trtm_cls_code") or fields.get("MRKT_TRTM_CLS_CODE") or "").strip()
    if time_state == "2":
        return MarketPhase.OPEN
    if time_state == "3":
        return MarketPhase.AUCTION
    if time_state == "4":
        return MarketPhase.CLOSED
    if time_state == "1":
        return MarketPhase.PREOPEN

    return MarketPhase.UNKNOWN


def _parse_market_datetime_from_fields(fields: dict[str, object]) -> datetime | None:
    date_text = ""
    for key in ("stck_bsop_date", "bsop_date", "BASS_DT", "BSOP_DATE"):
        value = str(fields.get(key) or "").strip()
        if len(value) == 8 and value.isdigit():
            date_text = value
            break
    if not date_text:
        date_text = datetime.now(UTC).strftime("%Y%m%d")

    for key in ("stck_cntg_hour", "aspr_acpt_hour", "BSOP_HOUR", "bsop_hour"):
        value = str(fields.get(key) or "").strip()
        if len(value) == 6 and value.isdigit():
            return _parse_market_datetime(date_text, value)
    return None


def _required_decimal(fields: dict[str, object], key: str) -> Decimal:
    value = _to_decimal(fields.get(key))
    if value is None:
        raise KISAPIError(f"KIS payload did not include a valid numeric '{key}' field")
    return value


def _parse_trade_date(output1: object) -> date:
    if isinstance(output1, dict):
        for key in ("bsop_date", "stck_bsop_date", "BASS_DT"):
            value = str(output1.get(key) or "").strip()
            if len(value) == 8 and value.isdigit():
                return datetime.strptime(value, "%Y%m%d").date()
    return datetime.now(UTC).date()


def _normalize_minute_rows(
    rows: Iterable[object] | object,
    *,
    instrument: InstrumentRef,
    default_trade_date: date,
) -> list[dict[str, object]]:
    if not isinstance(rows, Iterable) or isinstance(rows, (str, bytes, dict)):
        return []
    by_time: dict[str, dict[str, object]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        time_text = str(row.get("stck_cntg_hour") or "").strip()
        if len(time_text) != 6 or not time_text.isdigit():
            continue
        close = _to_decimal(row.get("stck_prpr"))
        open_price = _to_decimal(row.get("stck_oprc")) or close
        high = _to_decimal(row.get("stck_hgpr")) or close
        low = _to_decimal(row.get("stck_lwpr")) or close
        volume = _to_decimal(row.get("cntg_vol")) or Decimal("0")
        if close is None:
            continue
        normalized_row = {
            "instrument": instrument,
            "opened_at": _parse_market_datetime(str(row.get("stck_bsop_date") or "") or default_trade_date.strftime("%Y%m%d"), time_text),
            "open": open_price or close,
            "high": max(high or close, close),
            "low": min(low or close, close),
            "close": close,
            "volume": max(volume, Decimal("0")),
            "notional": _to_decimal(row.get("acml_tr_pbmn")),
        }
        existing = by_time.get(time_text)
        if existing is None:
            by_time[time_text] = normalized_row
            continue
        existing["high"] = max(existing["high"], normalized_row["high"])
        existing["low"] = min(existing["low"], normalized_row["low"])
        existing["close"] = normalized_row["close"]
        existing["volume"] = max(existing["volume"], normalized_row["volume"])
        existing["notional"] = normalized_row["notional"] or existing["notional"]
    return [by_time[key] for key in sorted(by_time)]


def _aggregate_bars(rows: Iterable[dict[str, object]], interval_minutes: int) -> list[IntradayBar]:
    buckets: list[IntradayBar] = []
    current: dict[str, object] | None = None
    current_key: tuple[int, int] | None = None
    for row in rows:
        opened_at = row["opened_at"]
        if not isinstance(opened_at, datetime):
            continue
        minute = (opened_at.minute // interval_minutes) * interval_minutes
        bucket_opened_at = opened_at.replace(minute=minute, second=0, microsecond=0)
        bucket_key = (bucket_opened_at.hour, bucket_opened_at.minute)
        if current_key != bucket_key:
            if current is not None:
                buckets.append(_bucket_to_bar(current, interval_minutes))
            current_key = bucket_key
            current = {**row, "opened_at": bucket_opened_at}
            continue
        assert current is not None
        current["high"] = max(current["high"], row["high"])
        current["low"] = min(current["low"], row["low"])
        current["close"] = row["close"]
        current["volume"] = current["volume"] + row["volume"]
        current["notional"] = row["notional"] or current["notional"]
    if current is not None:
        buckets.append(_bucket_to_bar(current, interval_minutes))
    return buckets


def _bucket_to_bar(bucket: dict[str, object], interval_minutes: int) -> IntradayBar:
    return IntradayBar(
        instrument=bucket["instrument"],
        opened_at=bucket["opened_at"],
        interval_minutes=interval_minutes,
        open=bucket["open"],
        high=bucket["high"],
        low=bucket["low"],
        close=bucket["close"],
        volume=bucket["volume"],
        notional=bucket["notional"],
    )


def _minute_row_to_market_bar(row: dict[str, object]) -> MarketBar:
    return MarketBar(
        instrument=row["instrument"],
        opened_at=row["opened_at"],
        timeframe=BarTimeframe.MINUTE,
        interval_minutes=1,
        open=row["open"],
        high=row["high"],
        low=row["low"],
        close=row["close"],
        volume=row["volume"],
        notional=row["notional"],
    )


def _intraday_to_market_bar(bar: IntradayBar) -> MarketBar:
    return MarketBar(
        instrument=bar.instrument,
        opened_at=bar.opened_at,
        timeframe=BarTimeframe.MINUTE,
        interval_minutes=bar.interval_minutes,
        open=bar.open,
        high=bar.high,
        low=bar.low,
        close=bar.close,
        volume=bar.volume,
        notional=bar.notional,
    )


def _parse_period_bar(row: dict[str, object], *, instrument: InstrumentRef, timeframe: BarTimeframe) -> MarketBar:
    trade_date = _parse_market_datetime(str(row.get("stck_bsop_date") or ""), "000000")
    if trade_date is None:
        trade_date = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    close = _to_decimal(row.get("stck_clpr")) or Decimal("0")
    open_price = _to_decimal(row.get("stck_oprc")) or close
    high = _to_decimal(row.get("stck_hgpr")) or close
    low = _to_decimal(row.get("stck_lwpr")) or close
    volume = _to_decimal(row.get("acml_vol")) or Decimal("0")
    return MarketBar(
        instrument=instrument,
        opened_at=trade_date,
        timeframe=timeframe,
        interval_minutes=None,
        open=open_price,
        high=max(high, close),
        low=min(low, close),
        close=close,
        volume=max(volume, Decimal("0")),
        notional=_to_decimal(row.get("acml_tr_pbmn")),
    )


def _parse_market_datetime(date_text: str, time_text: str) -> datetime | None:
    if len(time_text) != 6 or not time_text.isdigit():
        return None
    trade_date = datetime.strptime(date_text, "%Y%m%d").date() if len(date_text) == 8 and date_text.isdigit() else datetime.now(UTC).date()
    return datetime.combine(trade_date, datetime.strptime(time_text, "%H%M%S").time(), tzinfo=UTC)


def _parse_trade_side(value: object) -> TradeSide:
    side_text = str(value or "").strip()
    if side_text in {"1", "2", "BUY"}:
        return TradeSide.BUY
    if side_text in {"3", "5", "SELL"}:
        return TradeSide.SELL
    return TradeSide.UNKNOWN


def _parse_recent_trade_side(row: dict[str, object], *, price: Decimal) -> TradeSide:
    ask = _to_decimal(row.get("askp") or row.get("askp1") or row.get("ASKP") or row.get("ASKP1"))
    bid = _to_decimal(row.get("bidp") or row.get("bidp1") or row.get("BIDP") or row.get("BIDP1"))

    if ask is not None and bid is not None:
        if ask <= bid:
            return TradeSide.UNKNOWN
        if price == ask:
            return TradeSide.BUY
        if price == bid:
            return TradeSide.SELL
        return TradeSide.UNKNOWN

    if ask is not None and price == ask:
        return TradeSide.BUY
    if bid is not None and price == bid:
        return TradeSide.SELL
    return TradeSide.UNKNOWN


def _to_decimal(value: object) -> Decimal | None:
    text = str(value or "").replace(",", "").strip()
    if not text:
        return None
    try:
        return Decimal(text)
    except Exception:
        return None


# ---- Account / Trading / Notification endpoint metadata --------------------

KIS_BALANCE_PATH = "/uapi/domestic-stock/v1/trading/inquire-balance"
KIS_BALANCE_TR_ID = "TTTC8434R"
KIS_BUYING_POWER_PATH = "/uapi/domestic-stock/v1/trading/inquire-psbl-order"
KIS_BUYING_POWER_TR_ID = "TTTC8908R"
KIS_OPEN_ORDERS_PATH = "/uapi/domestic-stock/v1/trading/inquire-psbl-rvsecncl"
KIS_OPEN_ORDERS_TR_ID = "TTTC8036R"
KIS_ORDER_HISTORY_PATH = "/uapi/domestic-stock/v1/trading/inquire-daily-ccld"
KIS_ORDER_HISTORY_TR_ID = "TTTC8001R"
KIS_ORDER_CASH_PATH = "/uapi/domestic-stock/v1/trading/order-cash"
KIS_ORDER_CASH_BUY_TR_ID = "TTTC0802U"
KIS_ORDER_CASH_SELL_TR_ID = "TTTC0801U"
KIS_ORDER_RVSECNCL_PATH = "/uapi/domestic-stock/v1/trading/order-rvsecncl"
KIS_ORDER_RVSECNCL_TR_ID = "TTTC0803U"
KIS_NOTIFICATION_TR_ID = "H0STCNI0"

KIS_NOTIFICATION_FIELDS = (
    "CUST_ID",
    "ACNT_NO",
    "ODER_NO",
    "OODER_NO",
    "SELN_BYOV_CLS",
    "RCTF_CLS",
    "ODER_KIND",
    "ODER_COND",
    "STCK_SHRN_ISCD",
    "CNTG_QTY",
    "CNTG_UNPR",
    "STCK_CNTG_HOUR",
    "RFUS_YN",
    "CNTG_YN",
    "ACPT_YN",
    "BRNC_NO",
    "ODER_QTY",
    "ACNT_NAME",
    "CNTG_ISNM",
    "ODER_COND_PRC",
    "ORD_EXG_GB",
    "POPUP_YN",
    "FILLER",
)

# Map KIS ORD_DVSN/ODER_KIND code to normalized OrderType.
_ORDER_TYPE_CODE_MAP = {
    "00": OrderType.LIMIT,
    "01": OrderType.MARKET,
    "02": OrderType.LIMIT,   # 조건부지정가: closest normalized = LIMIT
    "03": OrderType.BEST,    # 최유리지정가
    "04": OrderType.BEST,    # 최우선지정가
    "05": OrderType.MARKET,  # 장전시간외
    "06": OrderType.MARKET,  # 장후시간외
    "07": OrderType.MARKET,  # 시간외단일가
}


def _order_type_to_kis_code(order_type: OrderType) -> str:
    if order_type == OrderType.MARKET:
        return "01"
    if order_type == OrderType.BEST:
        return "03"
    # LIMIT / STOP / STOP_LIMIT / UNKNOWN default to 00 (지정가)
    return "00"


def _kis_code_to_order_type(code: str | None) -> OrderType:
    if not code:
        return OrderType.UNKNOWN
    return _ORDER_TYPE_CODE_MAP.get(str(code).strip(), OrderType.UNKNOWN)


def _kis_side_to_order_side(code: str | None) -> OrderSide:
    text = str(code or "").strip()
    if text in {"01", "1", "SELL"}:
        return OrderSide.SELL
    if text in {"02", "2", "BUY"}:
        return OrderSide.BUY
    # default SELL/BUY fallback raises later; but tolerate with BUY
    return OrderSide.BUY


def _synthesize_open_order_state(
    *,
    quantity: Decimal,
    filled: Decimal,
    remaining: Decimal,
    rejected: Decimal,
    canceled_confirmed: Decimal,
) -> OrderLifecycleState:
    if canceled_confirmed > 0 and filled == 0:
        return OrderLifecycleState.CANCELED
    if rejected > 0 and filled == 0:
        return OrderLifecycleState.REJECTED
    if filled > 0 and remaining == 0:
        return OrderLifecycleState.FILLED
    if filled > 0 and remaining > 0:
        return OrderLifecycleState.PARTIALLY_FILLED
    return OrderLifecycleState.WORKING


def _synthesize_history_state(
    *,
    quantity: Decimal,
    filled: Decimal,
    remaining: Decimal,
    rejected: Decimal,
    canceled_confirmed: Decimal,
    is_canceled: bool,
) -> OrderLifecycleState:
    if is_canceled:
        return OrderLifecycleState.CANCELED
    if filled >= quantity and remaining == 0 and quantity > 0:
        return OrderLifecycleState.FILLED
    if filled > 0 and remaining > 0:
        return OrderLifecycleState.PARTIALLY_FILLED
    if rejected > 0 and filled == 0:
        return OrderLifecycleState.REJECTED
    if canceled_confirmed > 0 and filled == 0:
        return OrderLifecycleState.CANCELED
    return OrderLifecycleState.ACKNOWLEDGED


def parse_account_overview(
    payload: dict[str, object],
    *,
    account: AccountSummary,
    as_of: datetime | None = None,
) -> tuple[tuple[PositionLot, ...], AccountEquitySnapshot, tuple[str | None, str | None]]:
    """Parse inquire-balance (TTTC8434R) output1 positions + output2 equity."""

    positions_rows = payload.get("output1")
    positions: list[PositionLot] = []
    if isinstance(positions_rows, list):
        for row in positions_rows:
            if not isinstance(row, dict):
                continue
            symbol = str(row.get("pdno") or "").strip()
            if not symbol:
                continue
            quantity = _to_decimal(row.get("hldg_qty")) or Decimal("0")
            positions.append(
                PositionLot(
                    instrument=InstrumentRef(
                        symbol=symbol,
                        venue=Venue.KRX,
                        name=str(row.get("prdt_name") or "") or None,
                        instrument_id=symbol,
                    ),
                    quantity=quantity,
                    orderable_quantity=_to_decimal(row.get("ord_psbl_qty")),
                    average_price=_to_decimal(row.get("pchs_avg_pric")),
                    cost_basis=_to_decimal(row.get("pchs_amt")),
                    market_price=_to_decimal(row.get("prpr")),
                    market_value=_to_decimal(row.get("evlu_amt")),
                    unrealized_pnl=_to_decimal(row.get("evlu_pfls_amt")),
                    unrealized_pnl_rate=_to_decimal(row.get("evlu_pfls_rt")),
                    today=PositionDayActivity(
                        buy_quantity=_to_decimal(row.get("thdt_buyqty")),
                        sell_quantity=_to_decimal(row.get("thdt_sll_qty")),
                    ),
                    previous_day=PositionDayActivity(
                        buy_quantity=_to_decimal(row.get("bfdy_buy_qty")),
                        sell_quantity=_to_decimal(row.get("bfdy_sll_qty")),
                    ),
                )
            )

    equity_rows = payload.get("output2")
    equity_row: dict[str, object] = {}
    if isinstance(equity_rows, list) and equity_rows:
        first = equity_rows[0]
        if isinstance(first, dict):
            equity_row = first
    elif isinstance(equity_rows, dict):
        equity_row = equity_rows

    equity = AccountEquitySnapshot(
        account=account,
        as_of=as_of or datetime.now(UTC),
        cash=_to_decimal(equity_row.get("dnca_tot_amt")),
        d1_settlement=_to_decimal(equity_row.get("nxdy_excc_amt")),
        d2_settlement=_to_decimal(equity_row.get("prvs_rcdl_excc_amt")),
        securities_value=_to_decimal(equity_row.get("scts_evlu_amt")),
        total_value=_to_decimal(equity_row.get("tot_evlu_amt")),
        net_asset_value=_to_decimal(equity_row.get("nass_amt")),
        total_cost_basis=_to_decimal(equity_row.get("pchs_amt_smtl_amt")),
        positions_market_value=_to_decimal(equity_row.get("evlu_amt_smtl_amt")),
        total_unrealized_pnl=_to_decimal(equity_row.get("evlu_pfls_smtl_amt")),
        previous_total_value=_to_decimal(equity_row.get("bfdy_tot_asst_evlu_amt")),
        asset_change=_to_decimal(equity_row.get("asst_icdc_amt")),
        asset_change_rate=_to_decimal(equity_row.get("asst_icdc_erng_rt")),
    )

    fk100 = str(payload.get("ctx_area_fk100") or "").strip() or None
    nk100 = str(payload.get("ctx_area_nk100") or "").strip() or None
    return tuple(positions), equity, (fk100, nk100)


def parse_buying_power(payload: dict[str, object]) -> BuyingPowerSnapshot:
    """Parse inquire-psbl-order (TTTC8908R) output."""

    output = payload.get("output")
    if isinstance(output, list) and output:
        output = output[0]
    if not isinstance(output, dict):
        raise KISAPIError("KIS buying-power response did not include an output payload")
    return BuyingPowerSnapshot(
        available_cash=_to_decimal(output.get("ord_psbl_cash")),
        available_substitute=_to_decimal(output.get("ord_psbl_sbst")),
        reusable_amount=_to_decimal(output.get("ruse_psbl_amt")),
        non_margin_buy_amount=_to_decimal(output.get("nrcvb_buy_amt")),
        non_margin_buy_quantity=_to_decimal(output.get("nrcvb_buy_qty")),
        max_buy_amount=_to_decimal(output.get("max_buy_amt")),
        max_buy_quantity=_to_decimal(output.get("max_buy_qty")),
        price_used_for_calc=_to_decimal(output.get("psbl_qty_calc_unpr")),
    )


def parse_open_orders(
    payload: dict[str, object],
    *,
    provider: str = "kis",
    account_id: str | None = None,
) -> tuple[OpenOrder, ...]:
    """Parse inquire-psbl-rvsecncl (TTTC8036R) output1."""

    rows = payload.get("output1") or payload.get("output")
    if not isinstance(rows, list):
        return ()
    orders: list[OpenOrder] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        order_id = str(row.get("odno") or "").strip()
        if not order_id:
            continue
        original_order_id = str(row.get("orgn_odno") or "").strip() or None
        branch_no = str(row.get("ord_gno_brno") or "").strip() or None
        symbol = str(row.get("pdno") or "").strip()
        quantity = _to_decimal(row.get("ord_qty")) or Decimal("0")
        filled = _to_decimal(row.get("tot_ccld_qty")) or Decimal("0")
        remaining = _to_decimal(row.get("rmn_qty")) or Decimal("0")
        rejected = _to_decimal(row.get("rjct_qty")) or Decimal("0")
        cancel_confirmed = _to_decimal(row.get("cncl_cfrm_qty")) or Decimal("0")
        occurred_at = _parse_market_datetime(
            _today_str(),
            str(row.get("ord_tmd") or "").strip(),
        )
        order_ref = ProviderOrderRef(
            provider=provider,
            order_id=order_id,
            original_order_id=original_order_id,
            account_id=account_id,
        )
        correlation = OrderCorrelationKey(
            order_ref=order_ref,
            branch_no=branch_no,
        )
        orders.append(
            OpenOrder(
                order_ref=order_ref,
                instrument=InstrumentRef(
                    symbol=symbol,
                    venue=Venue.KRX,
                    name=str(row.get("prdt_name") or "") or None,
                    instrument_id=symbol,
                ),
                side=_kis_side_to_order_side(row.get("sll_buy_dvsn_cd")),
                order_type=_kis_code_to_order_type(row.get("ord_dvsn_cd")),
                quantity=quantity,
                remaining_quantity=remaining,
                limit_price=_to_decimal(row.get("ord_unpr")),
                state=_synthesize_open_order_state(
                    quantity=quantity,
                    filled=filled,
                    remaining=remaining,
                    rejected=rejected,
                    canceled_confirmed=cancel_confirmed,
                ),
                occurred_at=occurred_at,
                filled_quantity=filled,
                cancelable_quantity=_to_decimal(row.get("psbl_qty")),
                cancel_confirmed_quantity=cancel_confirmed,
                rejected_quantity=rejected,
                correlation_key=correlation,
            )
        )
    return tuple(orders)


def parse_order_history(
    payload: dict[str, object],
    *,
    provider: str = "kis",
    account_id: str | None = None,
) -> tuple[tuple[OrderHistoryRecord, ...], OrderHistorySummary | None, tuple[str | None, str | None]]:
    rows = payload.get("output1")
    records: list[OrderHistoryRecord] = []
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            order_id = str(row.get("odno") or "").strip()
            if not order_id:
                continue
            original_order_id = str(row.get("orgn_odno") or "").strip() or None
            branch_no = str(row.get("ord_gno_brno") or "").strip() or None
            symbol = str(row.get("pdno") or "").strip()
            quantity = _to_decimal(row.get("ord_qty")) or Decimal("0")
            filled = _to_decimal(row.get("tot_ccld_qty")) or Decimal("0")
            remaining = _to_decimal(row.get("rmn_qty")) or Decimal("0")
            rejected = _to_decimal(row.get("rjct_qty")) or Decimal("0")
            cancel_confirmed = _to_decimal(row.get("cncl_cfrm_qty")) or Decimal("0")
            is_canceled = str(row.get("cncl_yn") or "").strip().upper() == "Y"
            order_date_text = str(row.get("ord_dt") or "").strip()
            order_date = None
            if len(order_date_text) == 8 and order_date_text.isdigit():
                order_date = datetime.strptime(order_date_text, "%Y%m%d").date()
            submitted_at = _parse_market_datetime(order_date_text, str(row.get("ord_tmd") or "").strip())
            order_ref = ProviderOrderRef(
                provider=provider,
                order_id=order_id,
                original_order_id=original_order_id,
                account_id=account_id,
            )
            records.append(
                OrderHistoryRecord(
                    order_ref=order_ref,
                    correlation_key=OrderCorrelationKey(order_ref=order_ref, branch_no=branch_no),
                    instrument=InstrumentRef(
                        symbol=symbol,
                        venue=Venue.KRX,
                        name=str(row.get("prdt_name") or "") or None,
                        instrument_id=symbol,
                    ),
                    side=_kis_side_to_order_side(row.get("sll_buy_dvsn_cd")),
                    order_type=_kis_code_to_order_type(row.get("ord_dvsn_cd")),
                    quantity=quantity,
                    limit_price=_to_decimal(row.get("ord_unpr")),
                    filled_quantity=filled,
                    filled_notional=_to_decimal(row.get("tot_ccld_amt")),
                    average_fill_price=_to_decimal(row.get("avg_prvs")),
                    remaining_quantity=remaining,
                    rejected_quantity=rejected,
                    cancel_confirmed_quantity=cancel_confirmed,
                    is_canceled=is_canceled,
                    state=_synthesize_history_state(
                        quantity=quantity,
                        filled=filled,
                        remaining=remaining,
                        rejected=rejected,
                        canceled_confirmed=cancel_confirmed,
                        is_canceled=is_canceled,
                    ),
                    order_date=order_date,
                    submitted_at=submitted_at,
                    exchange_code=str(row.get("excg_dvsn_cd") or "").strip() or None,
                )
            )

    summary: OrderHistorySummary | None = None
    summary_row = payload.get("output2")
    if isinstance(summary_row, list) and summary_row:
        summary_row = summary_row[0]
    if isinstance(summary_row, dict):
        summary = OrderHistorySummary(
            total_buy_quantity=_to_decimal(summary_row.get("tot_ord_qty")) or _to_decimal(summary_row.get("tot_buy_qty")),
            total_sell_quantity=_to_decimal(summary_row.get("tot_sll_qty")),
            total_buy_notional=_to_decimal(summary_row.get("tot_ccld_amt")) or _to_decimal(summary_row.get("tot_buy_amt")),
            total_sell_notional=_to_decimal(summary_row.get("tot_sll_amt")),
        )

    fk100 = str(payload.get("ctx_area_fk100") or "").strip() or None
    nk100 = str(payload.get("ctx_area_nk100") or "").strip() or None
    return tuple(records), summary, (fk100, nk100)


def parse_order_ack(
    payload: dict[str, object],
    *,
    provider: str = "kis",
    account_id: str | None = None,
    original_order_id: str | None = None,
) -> tuple[ProviderOrderRef, OrderCorrelationKey, datetime | None]:
    output = payload.get("output")
    if isinstance(output, list) and output:
        output = output[0]
    if not isinstance(output, dict):
        raise KISAPIError("KIS order response did not include an output payload")
    order_id = str(output.get("ODNO") or output.get("odno") or "").strip()
    if not order_id:
        raise KISAPIError("KIS order response did not include an order number")
    origin_org_no = str(output.get("KRX_FWDG_ORD_ORGNO") or output.get("krx_fwdg_ord_orgno") or "").strip() or None
    ord_tmd = str(output.get("ORD_TMD") or output.get("ord_tmd") or "").strip()
    occurred_at = _parse_market_datetime(_today_str(), ord_tmd) if ord_tmd else datetime.now(UTC)
    order_ref = ProviderOrderRef(
        provider=provider,
        order_id=order_id,
        original_order_id=original_order_id,
        account_id=account_id,
    )
    correlation = OrderCorrelationKey(order_ref=order_ref, origin_org_no=origin_org_no)
    return order_ref, correlation, occurred_at


def parse_notification_event(
    raw_message: str,
    *,
    provider: str = "kis",
    account: AccountSummary | None = None,
):
    """Dispatch a single H0STCNI0 realtime notification message.

    Returns one of: OrderAcceptedEvent | OrderAmendAckEvent | OrderCancelAckEvent
    | OrderRejectedEvent | FillNotificationEvent | None (non-event / pingpong / error).
    """

    if not raw_message:
        return None
    if raw_message[0] == "{":
        data = json.loads(raw_message)
        header = data.get("header") or {}
        if header.get("tr_id") == "PINGPONG":
            return None
        body = data.get("body") or {}
        if body and body.get("rt_cd") not in (None, "0"):
            raise KISAPIError(
                str(body.get("msg1") or "KIS websocket subscription failed"),
                code=str(body.get("msg_cd") or body.get("rt_cd") or ""),
            )
        return None
    if raw_message[0] not in {"0", "1"}:
        return None

    parts = raw_message.split("|", 3)
    if len(parts) != 4 or parts[1] != KIS_NOTIFICATION_TR_ID:
        return None
    fields = dict(zip(KIS_NOTIFICATION_FIELDS, parts[3].split("^"), strict=False))

    order_id = str(fields.get("ODER_NO") or "").strip()
    if not order_id:
        return None
    original_order_id = str(fields.get("OODER_NO") or "").strip() or None
    branch_no = str(fields.get("BRNC_NO") or "").strip() or None

    account_id = None
    if account is not None:
        account_id = account.account_id
    else:
        acnt_raw = str(fields.get("ACNT_NO") or "").strip()
        account_id = acnt_raw or None

    order_ref = ProviderOrderRef(
        provider=provider,
        order_id=order_id,
        original_order_id=original_order_id,
        account_id=account_id,
    )
    correlation = OrderCorrelationKey(order_ref=order_ref, branch_no=branch_no)

    symbol = str(fields.get("STCK_SHRN_ISCD") or "").strip()
    instrument = InstrumentRef(
        symbol=symbol or "",
        venue=Venue.KRX,
        name=str(fields.get("CNTG_ISNM") or "") or None,
        instrument_id=symbol or None,
    )
    side = _kis_side_to_order_side(fields.get("SELN_BYOV_CLS"))
    order_type = _kis_code_to_order_type(fields.get("ODER_KIND"))
    occurred_at = _parse_market_datetime(_today_str(), str(fields.get("STCK_CNTG_HOUR") or "").strip()) or datetime.now(UTC)

    cntg_yn = str(fields.get("CNTG_YN") or "").strip()
    if cntg_yn == "2":
        price = _to_decimal(fields.get("CNTG_UNPR")) or Decimal("0")
        quantity = _to_decimal(fields.get("CNTG_QTY")) or Decimal("0")
        return FillNotificationEvent(
            order_ref=order_ref,
            correlation_key=correlation,
            instrument=instrument,
            side=side,
            order_type=order_type,
            occurred_at=occurred_at,
            price=price,
            quantity=quantity,
            account=account,
        )
    if cntg_yn != "1":
        return None

    rfus_yn = str(fields.get("RFUS_YN") or "").strip()
    rctf_cls = str(fields.get("RCTF_CLS") or "").strip()
    acpt_yn = str(fields.get("ACPT_YN") or "").strip()
    quantity = _to_decimal(fields.get("ODER_QTY")) or Decimal("0")
    limit_price = _to_decimal(fields.get("ODER_COND_PRC"))

    if rfus_yn == "1":
        return OrderRejectedEvent(
            order_ref=order_ref,
            correlation_key=correlation,
            instrument=instrument,
            side=side,
            order_type=order_type,
            occurred_at=occurred_at,
            quantity=quantity,
            reason_code=str(fields.get("ODER_COND") or "").strip() or None,
            account=account,
        )
    if rctf_cls == "1":
        return OrderAmendAckEvent(
            order_ref=order_ref,
            correlation_key=correlation,
            instrument=instrument,
            side=side,
            order_type=order_type,
            occurred_at=occurred_at,
            quantity=quantity,
            limit_price=limit_price,
            account=account,
        )
    if rctf_cls == "2" or acpt_yn == "3":
        return OrderCancelAckEvent(
            order_ref=order_ref,
            correlation_key=correlation,
            instrument=instrument,
            side=side,
            order_type=order_type,
            occurred_at=occurred_at,
            canceled_quantity=quantity,
            account=account,
        )
    return OrderAcceptedEvent(
        order_ref=order_ref,
        correlation_key=correlation,
        instrument=instrument,
        side=side,
        order_type=order_type,
        occurred_at=occurred_at,
        quantity=quantity,
        limit_price=limit_price,
        account=account,
    )


def notification_subscription_message(*, approval_key: str, hts_id: str) -> dict[str, object]:
    return {
        "header": {
            "approval_key": approval_key,
            "content-type": "utf-8",
            "custtype": "P",
            "tr_type": "1",
        },
        "body": {"input": {"tr_id": KIS_NOTIFICATION_TR_ID, "tr_key": hts_id}},
    }


def _today_str() -> str:
    return datetime.now(UTC).strftime("%Y%m%d")
