"""Broker-neutral market data models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from .enums import AssetClass, BarTimeframe, InstrumentType, MarketSegment, TradeSide, Venue


@dataclass(frozen=True, slots=True)
class InstrumentRef:
    """Stable instrument reference independent from provider-specific payload fields."""

    symbol: str
    venue: Venue | None = None
    market_segment: MarketSegment | None = None
    instrument_id: str | None = None
    name: str | None = None
    isin: str | None = None
    asset_class: AssetClass | None = None
    instrument_type: InstrumentType | None = None


@dataclass(frozen=True, slots=True)
class Trade:
    """Individual execution fact without transport/runtime baggage."""

    symbol: str
    occurred_at: datetime
    price: Decimal
    quantity: Decimal
    side: TradeSide | None = None
    trade_id: str | None = None
    sequence: int | str | None = None
    ask_price: Decimal | None = None
    bid_price: Decimal | None = None


@dataclass(frozen=True, slots=True)
class QuoteSnapshot:
    """Normalized last-price snapshot from the provider quote endpoint."""

    symbol: str
    occurred_at: datetime
    last: Decimal
    open: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    previous_close: Decimal | None = None
    change: Decimal | None = None
    change_rate: Decimal | None = None
    volume: Decimal | None = None
    notional: Decimal | None = None


@dataclass(frozen=True, slots=True)
class IntradayBar:
    """Intraday OHLCV bar independent from provider field names."""

    symbol: str
    opened_at: datetime
    interval_minutes: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    notional: Decimal | None = None


@dataclass(frozen=True, slots=True)
class MarketBar:
    """Unified K-line OHLCV bar across minute/day/week/month/year families."""

    symbol: str
    opened_at: datetime
    timeframe: BarTimeframe
    interval_minutes: int | None
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    notional: Decimal | None = None


@dataclass(frozen=True, slots=True)
class QuoteLevel:
    """Single order book level."""

    price: Decimal
    quantity: Decimal


@dataclass(frozen=True, slots=True)
class OrderBookSnapshot:
    """Snapshot order book state."""

    symbol: str
    occurred_at: datetime
    asks: tuple[QuoteLevel, ...] = ()
    bids: tuple[QuoteLevel, ...] = ()
    total_ask_quantity: Decimal | None = None
    total_bid_quantity: Decimal | None = None


@dataclass(frozen=True, slots=True)
class ProgramTrade:
    """Program-trade flow separated from ordinary execution prints."""

    symbol: str
    occurred_at: datetime
    sell_quantity: Decimal
    buy_quantity: Decimal
    net_buy_quantity: Decimal
    sell_notional: Decimal
    buy_notional: Decimal
    net_buy_notional: Decimal
    program_sell_depth: Decimal | None = None
    program_buy_depth: Decimal | None = None
