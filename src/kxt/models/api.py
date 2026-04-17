"""Planned v2 request/response/event DTOs for the library-first kxt surface."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
import re

from kxt.errors import KXTValidationError

from .enums import (
    BarTimeframe,
    MarketPhase,
    MarketScope,
    MarketSegment,
    OrderLifecycleState,
    OrderSide,
    OrderType,
    RankingKind,
    SessionType,
    TradeSide,
    Venue,
)
from .market_data import InstrumentRef, MarketBar, OrderBookSnapshot, ProgramTrade, QuoteLevel, QuoteSnapshot, Trade


def normalize_bar_timeframe(value: BarTimeframe | str) -> str:
    if isinstance(value, BarTimeframe):
        return {
            BarTimeframe.MINUTE: "1m",
            BarTimeframe.DAY: "day",
            BarTimeframe.WEEK: "week",
            BarTimeframe.MONTH: "month",
            BarTimeframe.YEAR: "year",
        }[value]

    normalized = value.strip().lower()
    if not normalized:
        raise ValueError("timeframe must not be empty")

    minute_match = re.fullmatch(r"(?P<count>\d+)\s*(m|min|mins|minute|minutes)", normalized)
    if minute_match is not None:
        interval_minutes = int(minute_match.group("count"))
        if interval_minutes < 1:
            raise ValueError("minute timeframe must be >= 1m")
        return f"{interval_minutes}m"

    try:
        return {
            "m": "1m",
            "min": "1m",
            "mins": "1m",
            "minute": "1m",
            "minutes": "1m",
            "1m": "1m",
            "d": "day",
            "1d": "day",
            "day": "day",
            "daily": "day",
            "w": "week",
            "1w": "week",
            "week": "week",
            "weekly": "week",
            "mo": "month",
            "mon": "month",
            "1mo": "month",
            "1mon": "month",
            "month": "month",
            "monthly": "month",
            "y": "year",
            "1y": "year",
            "year": "year",
            "yearly": "year",
        }[normalized]
    except KeyError as exc:
        raise KXTValidationError(f"unsupported timeframe: {value!r}") from exc


def resolve_bar_timeframe(value: BarTimeframe | str) -> tuple[str, BarTimeframe, int]:
    normalized = normalize_bar_timeframe(value)
    if normalized.endswith("m"):
        return normalized, BarTimeframe.MINUTE, int(normalized.removesuffix("m"))

    timeframe = {
        "day": BarTimeframe.DAY,
        "week": BarTimeframe.WEEK,
        "month": BarTimeframe.MONTH,
        "year": BarTimeframe.YEAR,
    }[normalized]
    return normalized, timeframe, 1

@dataclass(frozen=True, slots=True)
class SingleInstrumentContext:
    symbol: str
    scope: MarketScope | None
    venue: Venue | None
    market_segment: MarketSegment | None


@dataclass(frozen=True, slots=True)
class Bar:
    opened_at: datetime
    timeframe: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


@dataclass(frozen=True, slots=True)
class TradePrint:
    occurred_at: datetime
    price: Decimal
    quantity: Decimal
    ask_price: Decimal | None = None
    bid_price: Decimal | None = None


@dataclass(frozen=True, slots=True)
class TradeEvent:
    occurred_at: datetime
    instrument: InstrumentRef
    price: Decimal
    quantity: Decimal
    side: TradeSide | None = None


OrderBookLevel = QuoteLevel


@dataclass(frozen=True, slots=True)
class OrderBookEvent:
    occurred_at: datetime
    instrument: InstrumentRef
    asks: tuple[OrderBookLevel, ...] = ()
    bids: tuple[OrderBookLevel, ...] = ()
    total_ask_quantity: Decimal | None = None
    total_bid_quantity: Decimal | None = None


ProgramTradeRecord = ProgramTrade


@dataclass(frozen=True, slots=True)
class ProviderRef:
    provider: str
    account_id: str | None = None
    route: str | None = None


@dataclass(frozen=True, slots=True)
class SessionContext:
    session: SessionType = SessionType.UNKNOWN
    label: str | None = None
    is_open: bool | None = None


@dataclass(frozen=True, slots=True)
class QuoteSessionContext(SessionContext):
    phase: MarketPhase = MarketPhase.UNKNOWN


@dataclass(frozen=True, slots=True)
class SessionWindow:
    session: SessionType
    opens_at: datetime | None = None
    closes_at: datetime | None = None
    label: str | None = None


@dataclass(frozen=True, slots=True)
class QuoteRequest:
    instrument: InstrumentRef
    session: SessionType | None = None


@dataclass(frozen=True, slots=True)
class QuoteResponse:
    occurred_at: datetime
    last: Decimal
    open: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    previous_close: Decimal | None = None
    change: Decimal | None = None
    change_rate: Decimal | None = None
    volume: Decimal | None = None



@dataclass(frozen=True, slots=True)
class BarCursor:
    next_opened_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class BarsRequest:
    instrument: InstrumentRef
    timeframe: str | BarTimeframe
    start: date | datetime | None = None
    end: date | datetime | None = None
    adjusted: bool = True
    session: SessionType | None = None

    def __post_init__(self) -> None:
        normalized, _, _ = resolve_bar_timeframe(self.timeframe)
        object.__setattr__(self, "timeframe", normalized)

    @property
    def timeframe_family(self) -> BarTimeframe:
        _, timeframe, _ = resolve_bar_timeframe(self.timeframe)
        return timeframe

    @property
    def timeframe_interval_minutes(self) -> int:
        _, _, interval_minutes = resolve_bar_timeframe(self.timeframe)
        return interval_minutes


@dataclass(frozen=True, slots=True)
class BarsResponse:
    timeframe: str
    bars: tuple[Bar, ...] = ()
    adjusted: bool = True
    cursor: BarCursor | None = None


@dataclass(frozen=True, slots=True)
class TradeCursor:
    """Internal continuation token for recent-trades pagination.

    Not part of the preferred public DTO contract; retained as plumbing
    until recent-trades continuation semantics are redesigned.
    """

    next_sequence: str | int | None = None
    next_occurred_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class RecentTradesRequest:
    instrument: InstrumentRef
    start: date | datetime | None = None
    end: date | datetime | None = None
    limit: int = 100
    session: SessionType | None = None


@dataclass(frozen=True, slots=True)
class RecentTradesResponse:
    trades: tuple[TradePrint, ...] = ()


@dataclass(frozen=True, slots=True)
class TradeStreamRequest:
    instrument: InstrumentRef
    session: SessionType | None = None


@dataclass(frozen=True, slots=True)
class TradeStreamStatusEvent:
    symbol: str
    scope: MarketScope | None
    venue: Venue | None
    market_segment: MarketSegment | None
    connected: bool
    occurred_at: datetime
    message: str | None = None


@dataclass(frozen=True, slots=True)
class OrderBookRequest:
    instrument: InstrumentRef
    session: SessionType | None = None


@dataclass(frozen=True, slots=True)
class OrderBookResponse:
    occurred_at: datetime
    asks: tuple[OrderBookLevel, ...] = ()
    bids: tuple[OrderBookLevel, ...] = ()
    total_ask_quantity: Decimal | None = None
    total_bid_quantity: Decimal | None = None


@dataclass(frozen=True, slots=True)
class OrderBookStreamRequest:
    instrument: InstrumentRef
    session: SessionType | None = None


@dataclass(frozen=True, slots=True)
class OrderBookStreamStatusEvent:
    symbol: str
    scope: MarketScope | None
    venue: Venue | None
    market_segment: MarketSegment | None
    connected: bool
    occurred_at: datetime
    message: str | None = None


@dataclass(frozen=True, slots=True)
class MarketStatusRequest:
    instrument: InstrumentRef | None = None
    session: SessionType | None = None


@dataclass(frozen=True, slots=True)
class MarketStatusResponse:
    phase: MarketPhase
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class MarketStatusStreamRequest:
    instrument: InstrumentRef | None = None
    session: SessionType | None = None


@dataclass(frozen=True, slots=True)
class MarketStatusEvent(SingleInstrumentContext):
    phase: MarketPhase
    occurred_at: datetime
    session_context: SessionContext | None = None
    message: str | None = None


@dataclass(frozen=True, slots=True)
class SessionTransitionEvent:
    occurred_at: datetime
    from_session: SessionType
    to_session: SessionType
    instrument: InstrumentRef | None = None
    message: str | None = None


@dataclass(frozen=True, slots=True)
class InvestorFlowRequest:
    instrument: InstrumentRef
    start: date | datetime | None = None
    end: date | datetime | None = None
    session: SessionType | None = None


@dataclass(frozen=True, slots=True)
class InvestorFlowBucket:
    """Per-category flow values within a single investor-flow snapshot.

    KIS `inquire-investor` reports one aggregate row whose fields are
    prefixed per investor category (retail / foreign / institution).
    Each bucket captures the six raw values for one such category and
    carries no independent time reference of its own.
    """

    buy_quantity: Decimal | None = None
    sell_quantity: Decimal | None = None
    net_buy_quantity: Decimal | None = None
    buy_notional: Decimal | None = None
    sell_notional: Decimal | None = None
    net_buy_notional: Decimal | None = None


@dataclass(frozen=True, slots=True)
class InvestorFlowResponse:
    """Single aggregate investor-flow snapshot at one time reference.

    The KIS investor endpoint returns one aggregate row per request, not a
    stream of independent category rows, so this response models a single
    timepoint with three grouped buckets rather than a list of records.
    """

    as_of_date: date | None = None
    retail: InvestorFlowBucket = InvestorFlowBucket()
    foreign: InvestorFlowBucket = InvestorFlowBucket()
    institution: InvestorFlowBucket = InvestorFlowBucket()


@dataclass(frozen=True, slots=True)
class InvestorFlowStreamRequest:
    instrument: InstrumentRef
    session: SessionType | None = None


@dataclass(frozen=True, slots=True)
class InvestorFlowEvent:
    snapshot: InvestorFlowResponse


@dataclass(frozen=True, slots=True)
class ProgramTradeRequest:
    instrument: InstrumentRef
    start: date | datetime | None = None
    end: date | datetime | None = None
    session: SessionType | None = None


@dataclass(frozen=True, slots=True)
class ProgramTradeResponse:
    records: tuple[ProgramTradeRecord, ...] = ()


@dataclass(frozen=True, slots=True)
class ProgramTradeStreamRequest:
    instrument: InstrumentRef
    session: SessionType | None = None


@dataclass(frozen=True, slots=True)
class ProgramTradeEvent:
    record: ProgramTradeRecord


@dataclass(frozen=True, slots=True)
class RankingsRequest:
    kind: RankingKind
    limit: int = 20
    instrument: InstrumentRef | None = None
    session: SessionType | None = None


@dataclass(frozen=True, slots=True)
class RankingEntry:
    instrument: InstrumentRef
    rank: int
    value: Decimal | None = None
    quantity: Decimal | None = None
    label: str | None = None


@dataclass(frozen=True, slots=True)
class RankingsResponse:
    entries: tuple[RankingEntry, ...] = ()


@dataclass(frozen=True, slots=True)
class MemberFlowRequest:
    instrument: InstrumentRef
    start: date | datetime | None = None
    end: date | datetime | None = None
    session: SessionType | None = None


@dataclass(frozen=True, slots=True)
class MemberFlowRecord:
    instrument: InstrumentRef
    occurred_at: datetime
    member_code: str
    member_name: str | None = None
    buy_quantity: Decimal | None = None
    sell_quantity: Decimal | None = None
    net_buy_quantity: Decimal | None = None


@dataclass(frozen=True, slots=True)
class MemberFlowResponse:
    records: tuple[MemberFlowRecord, ...] = ()


@dataclass(frozen=True, slots=True)
class AccountsRequest:
    provider: ProviderRef | None = None


@dataclass(frozen=True, slots=True)
class AccountSummary:
    provider: ProviderRef
    account_id: str
    name: str | None = None
    product_code: str | None = None


@dataclass(frozen=True, slots=True)
class AccountsResponse:
    accounts: tuple[AccountSummary, ...] = ()


@dataclass(frozen=True, slots=True)
class BalanceRequest:
    account: AccountSummary | None = None
    instrument: InstrumentRef | None = None
    session: SessionType | None = None


@dataclass(frozen=True, slots=True)
class BalanceSnapshot:
    account: AccountSummary | None = None
    as_of: datetime | None = None
    cash: Decimal | None = None
    buying_power: Decimal | None = None
    margin_available: Decimal | None = None
    net_liquidation_value: Decimal | None = None


@dataclass(frozen=True, slots=True)
class BalanceResponse:
    snapshot: BalanceSnapshot


@dataclass(frozen=True, slots=True)
class PositionsRequest:
    account: AccountSummary | None = None
    session: SessionType | None = None


@dataclass(frozen=True, slots=True)
class Position:
    instrument: InstrumentRef
    quantity: Decimal
    average_price: Decimal | None = None
    market_price: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    side: OrderSide | None = None


@dataclass(frozen=True, slots=True)
class PositionsResponse:
    positions: tuple[Position, ...]


@dataclass(frozen=True, slots=True)
class OpenOrdersRequest:
    account: AccountSummary | None = None
    instrument: InstrumentRef | None = None
    session: SessionType | None = None


@dataclass(frozen=True, slots=True)
class ProviderOrderRef:
    provider: str
    order_id: str
    original_order_id: str | None = None
    account_id: str | None = None


@dataclass(frozen=True, slots=True)
class OrderCorrelationKey:
    """Provider-side correlation key preserving KIS origin identifiers.

    Keeps `(KRX_FWDG_ORD_ORGNO, ODNO, OODER_NO, BRNC_NO)` for downstream
    correlation across modify/cancel chains and realtime notifications.
    """

    order_ref: ProviderOrderRef
    origin_org_no: str | None = None
    branch_no: str | None = None


@dataclass(frozen=True, slots=True)
class OpenOrder:
    order_ref: ProviderOrderRef
    instrument: InstrumentRef
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    remaining_quantity: Decimal | None = None
    limit_price: Decimal | None = None
    state: OrderLifecycleState = OrderLifecycleState.UNKNOWN
    occurred_at: datetime | None = None
    filled_quantity: Decimal | None = None
    cancelable_quantity: Decimal | None = None
    cancel_confirmed_quantity: Decimal | None = None
    rejected_quantity: Decimal | None = None
    exchange_code: str | None = None
    correlation_key: OrderCorrelationKey | None = None


@dataclass(frozen=True, slots=True)
class OpenOrdersResponse:
    orders: tuple[OpenOrder, ...]


@dataclass(frozen=True, slots=True)
class OrderRouteHint:
    venue: str | None = None
    session: SessionType | None = None
    strategy: str | None = None


@dataclass(frozen=True, slots=True)
class OrderInstruction:
    instrument: InstrumentRef
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    limit_price: Decimal | None = None
    stop_price: Decimal | None = None
    time_in_force: str | None = None
    route_hint: OrderRouteHint | None = None


@dataclass(frozen=True, slots=True)
class OrderAcknowledgement:
    order_ref: ProviderOrderRef | None = None
    state: OrderLifecycleState = OrderLifecycleState.UNKNOWN
    occurred_at: datetime | None = None
    message: str | None = None


@dataclass(frozen=True, slots=True)
class SubmitOrderRequest:
    instruction: OrderInstruction
    account: AccountSummary | None = None


@dataclass(frozen=True, slots=True)
class SubmitOrderResponse:
    acknowledgement: OrderAcknowledgement


@dataclass(frozen=True, slots=True)
class CancelOrderRequest:
    order_ref: ProviderOrderRef
    account: AccountSummary | None = None
    quantity: Decimal | None = None
    cancel_all: bool = True
    correlation_key: OrderCorrelationKey | None = None


@dataclass(frozen=True, slots=True)
class CancelOrderResponse:
    acknowledgement: OrderAcknowledgement


@dataclass(frozen=True, slots=True)
class OrderAmendment:
    quantity: Decimal | None = None
    limit_price: Decimal | None = None
    stop_price: Decimal | None = None
    order_type: OrderType | None = None


@dataclass(frozen=True, slots=True)
class ModifyOrderRequest:
    order_ref: ProviderOrderRef
    amendment: OrderAmendment
    account: AccountSummary | None = None
    correlation_key: OrderCorrelationKey | None = None


@dataclass(frozen=True, slots=True)
class ModifyOrderResponse:
    acknowledgement: OrderAcknowledgement


@dataclass(frozen=True, slots=True)
class OrderUpdatesStreamRequest:
    account: AccountSummary | None = None


@dataclass(frozen=True, slots=True)
class OrderUpdateEvent:
    order_ref: ProviderOrderRef
    instrument: InstrumentRef
    state: OrderLifecycleState
    occurred_at: datetime
    message: str | None = None
    filled_quantity: Decimal | None = None
    remaining_quantity: Decimal | None = None


@dataclass(frozen=True, slots=True)
class FillUpdatesStreamRequest:
    account: AccountSummary | None = None


@dataclass(frozen=True, slots=True)
class ExecutionReport:
    execution_id: str | None
    order_ref: ProviderOrderRef
    occurred_at: datetime
    price: Decimal
    quantity: Decimal


@dataclass(frozen=True, slots=True)
class FillEvent:
    report: ExecutionReport
    instrument: InstrumentRef


# --- Account / Trading / Notification DTOs (raw-field-backed per plan) ---


@dataclass(frozen=True, slots=True)
class PositionDayActivity:
    buy_quantity: Decimal | None = None
    sell_quantity: Decimal | None = None


@dataclass(frozen=True, slots=True)
class PositionLot:
    instrument: InstrumentRef
    quantity: Decimal
    orderable_quantity: Decimal | None = None
    average_price: Decimal | None = None
    cost_basis: Decimal | None = None
    market_price: Decimal | None = None
    market_value: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    unrealized_pnl_rate: Decimal | None = None
    today: PositionDayActivity | None = None
    previous_day: PositionDayActivity | None = None


@dataclass(frozen=True, slots=True)
class AccountEquitySnapshot:
    account: AccountSummary
    as_of: datetime
    cash: Decimal | None = None
    d1_settlement: Decimal | None = None
    d2_settlement: Decimal | None = None
    securities_value: Decimal | None = None
    total_value: Decimal | None = None
    net_asset_value: Decimal | None = None
    total_cost_basis: Decimal | None = None
    positions_market_value: Decimal | None = None
    total_unrealized_pnl: Decimal | None = None
    previous_total_value: Decimal | None = None
    asset_change: Decimal | None = None
    asset_change_rate: Decimal | None = None


@dataclass(frozen=True, slots=True)
class AccountOverviewCursor:
    fk100: str | None = None
    nk100: str | None = None


@dataclass(frozen=True, slots=True)
class AccountOverviewRequest:
    account: AccountSummary | None = None
    include_afterhours: bool = False
    include_fund_settlement: bool = True
    cursor: AccountOverviewCursor | None = None


@dataclass(frozen=True, slots=True)
class AccountOverviewResponse:
    equity: AccountEquitySnapshot
    positions: tuple[PositionLot, ...] = ()
    cursor: AccountOverviewCursor | None = None


@dataclass(frozen=True, slots=True)
class BuyingPowerRequest:
    instrument: InstrumentRef
    price: Decimal | None = None
    order_type: OrderType = OrderType.LIMIT
    include_cma: bool = False
    account: AccountSummary | None = None


@dataclass(frozen=True, slots=True)
class BuyingPowerSnapshot:
    available_cash: Decimal | None = None
    available_substitute: Decimal | None = None
    reusable_amount: Decimal | None = None
    non_margin_buy_amount: Decimal | None = None
    non_margin_buy_quantity: Decimal | None = None
    max_buy_amount: Decimal | None = None
    max_buy_quantity: Decimal | None = None
    price_used_for_calc: Decimal | None = None


@dataclass(frozen=True, slots=True)
class BuyingPowerResponse:
    snapshot: BuyingPowerSnapshot


@dataclass(frozen=True, slots=True)
class OrderHistoryRequest:
    start: date
    end: date
    instrument: InstrumentRef | None = None
    side_filter: OrderSide | None = None
    fill_filter: str = "all"  # "all" | "filled" | "unfilled"
    cursor: AccountOverviewCursor | None = None
    account: AccountSummary | None = None


@dataclass(frozen=True, slots=True)
class OrderHistoryRecord:
    order_ref: ProviderOrderRef
    correlation_key: OrderCorrelationKey
    instrument: InstrumentRef
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    limit_price: Decimal | None = None
    filled_quantity: Decimal = Decimal(0)
    filled_notional: Decimal | None = None
    average_fill_price: Decimal | None = None
    remaining_quantity: Decimal | None = None
    rejected_quantity: Decimal | None = None
    cancel_confirmed_quantity: Decimal | None = None
    is_canceled: bool = False
    state: OrderLifecycleState = OrderLifecycleState.UNKNOWN
    order_date: date | None = None
    submitted_at: datetime | None = None
    exchange_code: str | None = None


@dataclass(frozen=True, slots=True)
class OrderHistorySummary:
    total_buy_quantity: Decimal | None = None
    total_sell_quantity: Decimal | None = None
    total_buy_notional: Decimal | None = None
    total_sell_notional: Decimal | None = None


@dataclass(frozen=True, slots=True)
class OrderHistoryCursor:
    fk100: str | None = None
    nk100: str | None = None


@dataclass(frozen=True, slots=True)
class OrderHistoryResponse:
    records: tuple[OrderHistoryRecord, ...] = ()
    summary: OrderHistorySummary | None = None
    cursor: OrderHistoryCursor | None = None


@dataclass(frozen=True, slots=True)
class OrderAcceptedEvent:
    order_ref: ProviderOrderRef
    correlation_key: OrderCorrelationKey
    instrument: InstrumentRef
    side: OrderSide
    order_type: OrderType
    occurred_at: datetime
    quantity: Decimal
    limit_price: Decimal | None = None
    account: AccountSummary | None = None


@dataclass(frozen=True, slots=True)
class OrderAmendAckEvent:
    order_ref: ProviderOrderRef
    correlation_key: OrderCorrelationKey
    instrument: InstrumentRef
    side: OrderSide
    order_type: OrderType
    occurred_at: datetime
    quantity: Decimal
    limit_price: Decimal | None = None
    account: AccountSummary | None = None


@dataclass(frozen=True, slots=True)
class OrderCancelAckEvent:
    order_ref: ProviderOrderRef
    correlation_key: OrderCorrelationKey
    instrument: InstrumentRef
    side: OrderSide
    order_type: OrderType
    occurred_at: datetime
    canceled_quantity: Decimal
    account: AccountSummary | None = None


@dataclass(frozen=True, slots=True)
class OrderRejectedEvent:
    order_ref: ProviderOrderRef
    correlation_key: OrderCorrelationKey
    instrument: InstrumentRef
    side: OrderSide
    order_type: OrderType
    occurred_at: datetime
    quantity: Decimal
    reason_code: str | None = None
    account: AccountSummary | None = None


OrderLifecycleEvent = (
    OrderAcceptedEvent
    | OrderAmendAckEvent
    | OrderCancelAckEvent
    | OrderRejectedEvent
)


@dataclass(frozen=True, slots=True)
class FillNotificationEvent:
    order_ref: ProviderOrderRef
    correlation_key: OrderCorrelationKey
    instrument: InstrumentRef
    side: OrderSide
    order_type: OrderType
    occurred_at: datetime
    price: Decimal
    quantity: Decimal
    account: AccountSummary | None = None


@dataclass(frozen=True, slots=True)
class OrderEventsStreamRequest:
    """Unified realtime order+fill event subscription (KIS H0STCNI0)."""

    account: AccountSummary | None = None
    hts_id: str | None = None


@dataclass(frozen=True, slots=True)
class BuyingPowerSnapshotRequest:
    """Backward-compatible alias retained for potential downstream imports."""

    instrument: InstrumentRef
    account: AccountSummary | None = None
