"""Power-user request, cursor, subscription, and instruction DTOs.

These types are inputs you only need when going beyond the primitive-friendly
public methods on :class:`kxt.KISClient` (which accept symbol strings and
keyword arguments directly). They live in this dedicated namespace so that
``from kxt import *`` and tab-completion on the top-level ``kxt`` package stay
focused on the response/output surface.

Typical usage::

    from kxt.requests import BarsRequest

    req = BarsRequest(instrument=InstrumentRef(symbol="005930"), timeframe="day")
    resp = await client.get_bars(req)
"""

from .models.api import (
    AccountOverviewCursor,
    AccountOverviewRequest,
    AccountsRequest,
    BalanceRequest,
    BarCursor,
    BarsRequest,
    BuyingPowerRequest,
    CancelOrderRequest,
    FillUpdatesStreamRequest,
    InvestorFlowRequest,
    InvestorFlowStreamRequest,
    MarketStatusRequest,
    MarketStatusStreamRequest,
    MemberFlowRequest,
    ModifyOrderRequest,
    OpenOrdersRequest,
    OrderAmendment,
    OrderBookRequest,
    OrderBookStreamRequest,
    OrderEventsStreamRequest,
    OrderHistoryCursor,
    OrderHistoryRequest,
    OrderInstruction,
    OrderRouteHint,
    OrderUpdatesStreamRequest,
    PositionsRequest,
    ProgramTradeRequest,
    ProgramTradeStreamRequest,
    ProviderRef,
    QuoteRequest,
    RankingsRequest,
    RecentTradesRequest,
    SubmitOrderRequest,
    TradeCursor,
    TradeStreamRequest,
)
from .streams.subscriptions import (
    OrderBookSubscription,
    ProgramTradeSubscription,
    TradeSubscription,
)
from .clients.kis.realtime import Subscription

__all__ = [
    "AccountOverviewCursor",
    "AccountOverviewRequest",
    "AccountsRequest",
    "BalanceRequest",
    "BarCursor",
    "BarsRequest",
    "BuyingPowerRequest",
    "CancelOrderRequest",
    "FillUpdatesStreamRequest",
    "InvestorFlowRequest",
    "InvestorFlowStreamRequest",
    "MarketStatusRequest",
    "MarketStatusStreamRequest",
    "MemberFlowRequest",
    "ModifyOrderRequest",
    "OpenOrdersRequest",
    "OrderAmendment",
    "OrderBookRequest",
    "OrderBookStreamRequest",
    "OrderBookSubscription",
    "OrderEventsStreamRequest",
    "OrderHistoryCursor",
    "OrderHistoryRequest",
    "OrderInstruction",
    "OrderRouteHint",
    "OrderUpdatesStreamRequest",
    "PositionsRequest",
    "ProgramTradeRequest",
    "ProgramTradeStreamRequest",
    "ProgramTradeSubscription",
    "ProviderRef",
    "QuoteRequest",
    "RankingsRequest",
    "RecentTradesRequest",
    "SubmitOrderRequest",
    "Subscription",
    "TradeCursor",
    "TradeStreamRequest",
    "TradeSubscription",
]
