"""Parsing helpers for Toss Invest Open API payloads."""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any

from kxt.errors import KXTAPIError, KXTValidationError
from kxt.markets.master import Market
from kxt.models import (
    AccountSummary,
    AssetClass,
    Bar,
    BarCursor,
    BarTimeframe,
    BarsResponse,
    BuyingPowerResponse,
    BuyingPowerSnapshot,
    InstrumentRef,
    InstrumentType,
    IntradayBar,
    MarketBar,
    MarketPhase,
    MarketSegment,
    MarketStatusResponse,
    OpenOrder,
    OpenOrdersResponse,
    OrderAcknowledgement,
    OrderBookLevel,
    OrderBookResponse,
    OrderBookSnapshot,
    OrderCorrelationKey,
    OrderHistoryCursor,
    OrderHistoryRecord,
    OrderHistoryResponse,
    OrderLifecycleState,
    OrderSide,
    OrderType,
    Position,
    PositionsResponse,
    ProviderOrderRef,
    ProviderRef,
    QuoteResponse,
    QuoteSnapshot,
    QuotesResponse,
    RecentTradesResponse,
    SubmitOrderResponse,
    CancelOrderResponse,
    ModifyOrderResponse,
    Trade,
    TradePrint,
    Venue,
)

PROVIDER = "tossinvest"


def parse_quote_snapshot(result: Any, *, instrument: InstrumentRef) -> QuoteSnapshot:
    rows = _as_list(result)
    if not rows:
        raise KXTAPIError("Toss Invest price response did not include result rows", provider=PROVIDER)
    row = _first_matching_symbol(rows, instrument.symbol)
    return _quote_snapshot_from_row(row, symbol=instrument.symbol)


def parse_quote_snapshots(result: Any) -> tuple[QuoteSnapshot, ...]:
    rows = _as_list(result)
    if not rows:
        raise KXTAPIError("Toss Invest price response did not include result rows", provider=PROVIDER)
    return tuple(
        _quote_snapshot_from_row(_as_dict(row), symbol=str(_as_dict(row).get("symbol") or ""))
        for row in rows
    )


def _quote_snapshot_from_row(row: dict[str, Any], *, symbol: str) -> QuoteSnapshot:
    occurred_at = _parse_datetime(row.get("timestamp")) or datetime.now(UTC)
    return QuoteSnapshot(
        symbol=str(row.get("symbol") or symbol),
        occurred_at=occurred_at,
        last=_decimal(row.get("lastPrice"), field="lastPrice"),
    )


def quote_response_from_snapshot(snapshot: QuoteSnapshot) -> QuoteResponse:
    return QuoteResponse(
        occurred_at=snapshot.occurred_at,
        last=snapshot.last,
        open=snapshot.open,
        high=snapshot.high,
        low=snapshot.low,
        previous_close=snapshot.previous_close,
        change=snapshot.change,
        change_rate=snapshot.change_rate,
        volume=snapshot.volume,
    )


def quotes_response_from_snapshots(snapshots: tuple[QuoteSnapshot, ...]) -> QuotesResponse:
    return QuotesResponse(quotes=snapshots)


def parse_orderbook_snapshot(result: Any, *, instrument: InstrumentRef) -> OrderBookSnapshot:
    row = _as_dict(result)
    asks = tuple(_parse_orderbook_level(v) for v in _as_list(row.get("asks")))
    bids = tuple(_parse_orderbook_level(v) for v in _as_list(row.get("bids")))
    occurred_at = _parse_datetime(row.get("timestamp")) or datetime.now(UTC)
    return OrderBookSnapshot(
        symbol=instrument.symbol,
        occurred_at=occurred_at,
        asks=asks,
        bids=bids,
        total_ask_quantity=sum((level.quantity for level in asks), Decimal(0)) if asks else None,
        total_bid_quantity=sum((level.quantity for level in bids), Decimal(0)) if bids else None,
    )


def orderbook_response_from_snapshot(snapshot: OrderBookSnapshot) -> OrderBookResponse:
    return OrderBookResponse(
        occurred_at=snapshot.occurred_at,
        asks=snapshot.asks,
        bids=snapshot.bids,
        total_ask_quantity=snapshot.total_ask_quantity,
        total_bid_quantity=snapshot.total_bid_quantity,
    )


def parse_recent_trades(result: Any, *, instrument: InstrumentRef) -> tuple[Trade, ...]:
    trades = []
    for row in _as_list(result):
        data = _as_dict(row)
        trades.append(
            Trade(
                symbol=instrument.symbol,
                occurred_at=_parse_datetime(data.get("timestamp")) or datetime.now(UTC),
                price=_decimal(data.get("price"), field="price"),
                quantity=_decimal(data.get("volume"), field="volume"),
            )
        )
    return tuple(sorted(trades, key=lambda trade: trade.occurred_at))


def recent_trades_response_from_trades(trades: tuple[Trade, ...]) -> RecentTradesResponse:
    return RecentTradesResponse(
        trades=tuple(
            TradePrint(
                occurred_at=trade.occurred_at,
                price=trade.price,
                quantity=trade.quantity,
                ask_price=trade.ask_price,
                bid_price=trade.bid_price,
            )
            for trade in trades
        )
    )


def parse_market_bars(
    result: Any,
    *,
    instrument: InstrumentRef,
    timeframe: BarTimeframe,
    interval_minutes: int | None,
) -> tuple[MarketBar, ...]:
    rows = _as_list(_as_dict(result).get("candles"))
    bars = tuple(
        MarketBar(
            symbol=instrument.symbol,
            opened_at=_required_datetime(row.get("timestamp"), field="timestamp"),
            timeframe=timeframe,
            interval_minutes=interval_minutes,
            open=_decimal(row.get("openPrice"), field="openPrice"),
            high=_decimal(row.get("highPrice"), field="highPrice"),
            low=_decimal(row.get("lowPrice"), field="lowPrice"),
            close=_decimal(row.get("closePrice"), field="closePrice"),
            volume=_decimal(row.get("volume"), field="volume"),
        )
        for row in (_as_dict(item) for item in rows)
    )
    return tuple(sorted(bars, key=lambda bar: bar.opened_at))


def bars_response_from_market_bars(
    bars: tuple[MarketBar, ...],
    *,
    timeframe: str,
    adjusted: bool,
    next_before: str | None,
) -> BarsResponse:
    return BarsResponse(
        timeframe=timeframe,
        adjusted=adjusted,
        bars=tuple(
            Bar(
                opened_at=bar.opened_at,
                timeframe=timeframe,
                open=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close,
                volume=bar.volume,
            )
            for bar in bars
        ),
        cursor=BarCursor(next_opened_at=_parse_datetime(next_before)) if next_before else None,
    )


def parse_accounts(result: Any) -> tuple[AccountSummary, ...]:
    accounts: list[AccountSummary] = []
    for row in _as_list(result):
        data = _as_dict(row)
        account_seq = str(data.get("accountSeq") or "").strip()
        if not account_seq:
            continue
        accounts.append(
            AccountSummary(
                provider=ProviderRef(provider=PROVIDER, account_id=account_seq),
                account_id=account_seq,
                name=str(data.get("accountType") or "") or None,
                product_code=str(data.get("accountNo") or "") or None,
            )
        )
    return tuple(accounts)


def parse_positions(result: Any) -> PositionsResponse:
    overview = _as_dict(result)
    positions: list[Position] = []
    for row in _as_list(overview.get("items")):
        data = _as_dict(row)
        positions.append(
            Position(
                symbol=str(data.get("symbol") or ""),
                quantity=_decimal(data.get("quantity"), field="quantity"),
                average_price=_optional_decimal(data.get("averagePurchasePrice")),
                market_price=_optional_decimal(data.get("lastPrice")),
                unrealized_pnl=_optional_decimal(_as_dict(data.get("profitLoss")).get("amount")),
                side=None,
            )
        )
    return PositionsResponse(positions=tuple(positions))


def parse_buying_power(result: Any) -> BuyingPowerResponse:
    data = _as_dict(result)
    cash_buying_power = _optional_decimal(data.get("cashBuyingPower"))
    snapshot = BuyingPowerSnapshot(
        available_cash=cash_buying_power,
        max_buy_amount=cash_buying_power,
    )
    return BuyingPowerResponse(snapshot=snapshot)


def parse_order_ack(
    result: Any,
    *,
    account_seq: str,
    state: OrderLifecycleState,
    original_order_id: str | None = None,
) -> OrderAcknowledgement:
    data = _as_dict(result)
    order_id = str(data.get("orderId") or "").strip()
    if not order_id:
        raise KXTAPIError("Toss Invest order response did not include orderId", provider=PROVIDER)
    return OrderAcknowledgement(
        order_ref=ProviderOrderRef(
            provider=PROVIDER,
            order_id=order_id,
            original_order_id=original_order_id,
            account_id=account_seq,
        ),
        state=state,
        occurred_at=datetime.now(UTC),
        message=str(data.get("clientOrderId") or "") or None,
    )


def submit_response_from_ack(ack: OrderAcknowledgement) -> SubmitOrderResponse:
    return SubmitOrderResponse(acknowledgement=ack)


def cancel_response_from_ack(ack: OrderAcknowledgement) -> CancelOrderResponse:
    return CancelOrderResponse(acknowledgement=ack)


def modify_response_from_ack(ack: OrderAcknowledgement) -> ModifyOrderResponse:
    return ModifyOrderResponse(acknowledgement=ack)


def parse_open_orders(result: Any, *, account_seq: str) -> OpenOrdersResponse:
    data = _as_dict(result)
    orders = tuple(_parse_open_order(row, account_seq=account_seq) for row in _as_list(data.get("orders")))
    return OpenOrdersResponse(orders=orders)


def parse_order_history(result: Any, *, account_seq: str) -> OrderHistoryResponse:
    data = _as_dict(result)
    records = tuple(
        _parse_order_history_record(row, account_seq=account_seq)
        for row in _as_list(data.get("orders"))
    )
    next_cursor = str(data.get("nextCursor") or "").strip() or None
    return OrderHistoryResponse(
        records=records,
        cursor=OrderHistoryCursor(fk100=next_cursor) if next_cursor else None,
    )


def parse_markets(result: Any) -> tuple[Market, ...]:
    markets = []
    for row in _as_list(result):
        data = _as_dict(row)
        symbol = str(data.get("symbol") or "").strip()
        if not symbol:
            continue
        markets.append(
            Market(
                instrument=InstrumentRef(
                    symbol=symbol,
                    venue=_venue_from_market(data.get("market")),
                    market_segment=_segment_from_market(data.get("market")),
                    instrument_id=symbol,
                    name=str(data.get("name") or "") or None,
                    isin=str(data.get("isinCode") or "") or None,
                    asset_class=_asset_class_from_security_type(data.get("securityType")),
                    instrument_type=_instrument_type_from_security_type(data.get("securityType")),
                ),
                listed_on=_parse_date(data.get("listDate")),
                delisted_on=_parse_date(data.get("delistDate")),
            )
        )
    return tuple(markets)


def parse_market_status(result: Any) -> MarketStatusResponse:
    data = _as_dict(result)
    today = _as_dict(data.get("today"))
    integrated = today.get("integrated")
    now = datetime.now(UTC)
    if not integrated:
        return MarketStatusResponse(phase=MarketPhase.CLOSED, occurred_at=now)

    regular = _as_dict(integrated.get("regularMarket"))
    pre = _as_dict(integrated.get("preMarket"))
    after = _as_dict(integrated.get("afterMarket"))
    if _within_session(now, regular):
        return MarketStatusResponse(phase=MarketPhase.OPEN, occurred_at=now)
    if _within_session(now, pre):
        return MarketStatusResponse(phase=MarketPhase.PREOPEN, occurred_at=now)
    if _within_session(now, after):
        return MarketStatusResponse(phase=MarketPhase.AFTER_HOURS, occurred_at=now)
    return MarketStatusResponse(phase=MarketPhase.CLOSED, occurred_at=now)


def _parse_orderbook_level(row: Any) -> OrderBookLevel:
    data = _as_dict(row)
    return OrderBookLevel(
        price=_decimal(data.get("price"), field="price"),
        quantity=_decimal(data.get("volume"), field="volume"),
    )


def _parse_open_order(row: Any, *, account_seq: str) -> OpenOrder:
    data = _as_dict(row)
    execution = _as_dict(data.get("execution"))
    quantity = _decimal(data.get("quantity"), field="quantity")
    filled = _optional_decimal(execution.get("filledQuantity")) or Decimal(0)
    order_ref = _order_ref(data, account_seq=account_seq)
    return OpenOrder(
        order_ref=order_ref,
        symbol=str(data.get("symbol") or ""),
        side=_order_side(data.get("side")),
        order_type=_order_type(data.get("orderType")),
        quantity=quantity,
        remaining_quantity=max(quantity - filled, Decimal(0)),
        limit_price=_optional_decimal(data.get("price")),
        state=_order_state(data.get("status")),
        occurred_at=_parse_datetime(data.get("orderedAt")),
        filled_quantity=filled,
        correlation_key=OrderCorrelationKey(order_ref=order_ref),
    )


def _parse_order_history_record(row: Any, *, account_seq: str) -> OrderHistoryRecord:
    data = _as_dict(row)
    execution = _as_dict(data.get("execution"))
    order_ref = _order_ref(data, account_seq=account_seq)
    quantity = _decimal(data.get("quantity"), field="quantity")
    filled = _optional_decimal(execution.get("filledQuantity")) or Decimal(0)
    submitted_at = _parse_datetime(data.get("orderedAt"))
    return OrderHistoryRecord(
        order_ref=order_ref,
        correlation_key=OrderCorrelationKey(order_ref=order_ref),
        symbol=str(data.get("symbol") or ""),
        side=_order_side(data.get("side")),
        order_type=_order_type(data.get("orderType")),
        quantity=quantity,
        limit_price=_optional_decimal(data.get("price")),
        filled_quantity=filled,
        filled_notional=_optional_decimal(execution.get("filledAmount")),
        average_fill_price=_optional_decimal(execution.get("averageFilledPrice")),
        remaining_quantity=max(quantity - filled, Decimal(0)),
        is_canceled=_order_state(data.get("status")) == OrderLifecycleState.CANCELED,
        state=_order_state(data.get("status")),
        order_date=submitted_at.date() if submitted_at else None,
        submitted_at=submitted_at,
    )


def _order_ref(data: dict[str, Any], *, account_seq: str) -> ProviderOrderRef:
    return ProviderOrderRef(
        provider=PROVIDER,
        order_id=str(data.get("orderId") or ""),
        account_id=account_seq,
    )


def _order_state(value: Any) -> OrderLifecycleState:
    normalized = str(value or "").upper()
    if normalized == "FILLED":
        return OrderLifecycleState.FILLED
    if normalized == "PARTIAL_FILLED":
        return OrderLifecycleState.PARTIALLY_FILLED
    if normalized in {"CANCELED", "CANCEL_REJECTED"}:
        return OrderLifecycleState.CANCELED
    if normalized in {"REJECTED", "REPLACE_REJECTED"}:
        return OrderLifecycleState.REJECTED
    if normalized == "REPLACED":
        return OrderLifecycleState.ACKNOWLEDGED
    return OrderLifecycleState.WORKING


def _order_side(value: Any) -> OrderSide:
    try:
        return OrderSide(str(value or "").upper())
    except ValueError:
        raise KXTValidationError(f"unsupported Toss Invest order side: {value!r}") from None


def _order_type(value: Any) -> OrderType:
    try:
        return OrderType(str(value or "").upper())
    except ValueError:
        return OrderType.UNKNOWN


def _first_matching_symbol(rows: list[Any], symbol: str) -> dict[str, Any]:
    fallback: dict[str, Any] | None = None
    for row in rows:
        data = _as_dict(row)
        if fallback is None:
            fallback = data
        if str(data.get("symbol") or "").upper() == symbol.upper():
            return data
    if fallback is not None:
        return fallback
    raise KXTAPIError("Toss Invest response did not include any rows", provider=PROVIDER)


def _venue_from_market(value: Any) -> Venue | None:
    normalized = str(value or "").upper()
    if normalized in {"KOSPI", "KOSDAQ", "KR_ETC"}:
        return Venue.KRX
    if normalized == "NYSE":
        return Venue.NYSE
    if normalized == "NASDAQ":
        return Venue.NASDAQ
    if normalized == "AMEX":
        return Venue.AMEX
    return None


def _segment_from_market(value: Any) -> MarketSegment | None:
    normalized = str(value or "").upper()
    if normalized == "KOSPI":
        return MarketSegment.KOSPI
    if normalized == "KOSDAQ":
        return MarketSegment.KOSDAQ
    return None


def _asset_class_from_security_type(value: Any) -> AssetClass | None:
    normalized = str(value or "").upper()
    if "ETF" in normalized:
        return AssetClass.ETF
    if "ETN" in normalized:
        return AssetClass.ETN
    if "STOCK" in normalized or normalized in {"REIT", "DEPOSITARY_RECEIPT"}:
        return AssetClass.EQUITY
    return None


def _instrument_type_from_security_type(value: Any) -> InstrumentType | None:
    normalized = str(value or "").upper()
    if "ETF" in normalized:
        return InstrumentType.ETF
    if "ETN" in normalized:
        return InstrumentType.ETN
    if "STOCK" in normalized:
        return InstrumentType.COMMON_STOCK
    return None


def _within_session(now: datetime, session: dict[str, Any]) -> bool:
    start_at = _parse_datetime(session.get("startTime"))
    end_at = _parse_datetime(session.get("endTime"))
    if start_at is None or end_at is None:
        return False
    now_at = now.astimezone(start_at.tzinfo or UTC)
    return start_at <= now_at <= end_at


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _decimal(value: Any, *, field: str) -> Decimal:
    parsed = _optional_decimal(value)
    if parsed is None:
        raise KXTAPIError(f"Toss Invest response missing decimal field: {field}", provider=PROVIDER)
    return parsed


def _optional_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise KXTAPIError(f"Toss Invest response contained invalid decimal: {value!r}", provider=PROVIDER) from exc


def _required_datetime(value: Any, *, field: str) -> datetime:
    parsed = _parse_datetime(value)
    if parsed is None:
        raise KXTAPIError(f"Toss Invest response missing datetime field: {field}", provider=PROVIDER)
    return parsed


def _parse_datetime(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    text = str(value)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise KXTAPIError(f"Toss Invest response contained invalid datetime: {text!r}", provider=PROVIDER) from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _parse_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    return date.fromisoformat(str(value))


def coerce_datetime(value: date | datetime | None, *, is_end: bool) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    bound_time = time.max if is_end else time.min
    return datetime.combine(value, bound_time, tzinfo=UTC)
