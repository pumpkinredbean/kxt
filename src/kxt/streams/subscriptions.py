"""Subscription request models for streaming APIs."""

from __future__ import annotations

from dataclasses import dataclass

from kxt.models.enums import MarketScope
from kxt.models.market_data import InstrumentRef


@dataclass(frozen=True, slots=True)
class TradeSubscription:
    """Subscribe to trade prints for one instrument or a broader market scope."""

    instrument: InstrumentRef | None = None
    scope: MarketScope | None = None


@dataclass(frozen=True, slots=True)
class OrderBookSubscription:
    """Subscribe to order book snapshots for one instrument."""

    instrument: InstrumentRef


@dataclass(frozen=True, slots=True)
class ProgramTradeSubscription:
    """Subscribe to program-trade updates for one instrument or scope."""

    instrument: InstrumentRef | None = None
    scope: MarketScope | None = None
