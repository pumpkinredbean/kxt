"""Base client interfaces for the current legacy provider integration surface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from datetime import date, datetime
from typing import TYPE_CHECKING

from .capabilities import ClientCapabilities

if TYPE_CHECKING:
    from kxt.markets.master import Market
    from kxt.models.enums import Venue

from kxt.models import (
    BarTimeframe,
    BarsRequest,
    BarsResponse,
    InstrumentRef,
    IntradayBar,
    MarketBar,
    MarketStatusRequest,
    MarketStatusResponse,
    InvestorFlowRequest,
    InvestorFlowResponse,
    OrderBookEvent,
    OrderBookRequest,
    OrderBookResponse,
    OrderBookSnapshot,
    OrderBookStreamRequest,
    QuoteRequest,
    QuoteResponse,
    QuoteSnapshot,
    RecentTradesRequest,
    RecentTradesResponse,
    Trade,
    TradeEvent,
    TradeStreamRequest,
)
from kxt.streams.subscriptions import OrderBookSubscription, TradeSubscription


class MarketNamespace(ABC):
    """Legacy grouped market-data compatibility namespace."""

    @abstractmethod
    async def fetch_bars(
        self,
        symbol: str | InstrumentRef,
        *,
        timeframe: BarTimeframe,
        start: date | datetime | None = None,
        end: date | datetime | None = None,
        interval_minutes: int = 1,
        adjusted: bool = True,
    ) -> tuple[MarketBar, ...]:
        """Fetch normalized K-line bars for an instrument."""

    @abstractmethod
    async def fetch_intraday_bars(
        self,
        symbol: str | InstrumentRef,
        *,
        interval_minutes: int = 1,
    ) -> tuple[IntradayBar, ...]:
        """Fetch intraday bars for an instrument."""

    @abstractmethod
    async def fetch_recent_trades(
        self,
        symbol: str | InstrumentRef,
        *,
        start: date | datetime | None = None,
        end: date | datetime | None = None,
        limit: int = 100,
    ) -> tuple[Trade, ...]:
        """Fetch normalized recent trades for an instrument."""


class StreamsNamespace(ABC):
    """Legacy grouped streaming compatibility namespace."""

    @abstractmethod
    def stream_trades(
        self, symbol: str | InstrumentRef | TradeSubscription | TradeStreamRequest
    ) -> AsyncIterator[TradeEvent]:
        """Yield trade events for a single-instrument subscription."""


class MarketDataClient(ABC):
    """Legacy broker-facing client contract kept while the repo-facing v2 design is rebuilt."""

    client_id: str

    @property
    @abstractmethod
    def capabilities(self) -> ClientCapabilities:
        """Return typed capability metadata for this client."""

    @abstractmethod
    async def fetch_bars(
        self,
        symbol: str | InstrumentRef,
        *,
        timeframe: BarTimeframe,
        start: date | datetime | None = None,
        end: date | datetime | None = None,
        interval_minutes: int = 1,
        adjusted: bool = True,
    ) -> tuple[MarketBar, ...]:
        """Fetch normalized K-line bars for an instrument."""

    @abstractmethod
    async def fetch_intraday_bars(
        self,
        symbol: str | InstrumentRef,
        *,
        interval_minutes: int = 1,
    ) -> tuple[IntradayBar, ...]:
        """Fetch intraday bars for an instrument."""

    @abstractmethod
    async def fetch_quote(self, symbol: str | InstrumentRef) -> QuoteSnapshot:
        """Fetch a normalized quote snapshot for an instrument."""

    async def get_quote(self, symbol: str | InstrumentRef | QuoteRequest) -> QuoteResponse:
        """Fetch a v2 normalized quote response."""

        raise NotImplementedError

    @abstractmethod
    async def fetch_orderbook(self, symbol: str | InstrumentRef) -> OrderBookSnapshot:
        """Fetch a normalized order book snapshot for an instrument."""

    async def get_orderbook(self, symbol: str | InstrumentRef | OrderBookRequest) -> OrderBookResponse:
        """Fetch a v2 normalized order book response."""

        raise NotImplementedError

    @abstractmethod
    async def fetch_recent_trades(
        self,
        symbol: str | InstrumentRef,
        *,
        start: date | datetime | None = None,
        end: date | datetime | None = None,
        limit: int = 100,
    ) -> tuple[Trade, ...]:
        """Fetch normalized recent trades for an instrument."""

    async def get_recent_trades(self, symbol: str | InstrumentRef | RecentTradesRequest) -> RecentTradesResponse:
        """Fetch a v2 normalized recent-trades response."""

        raise NotImplementedError

    async def get_bars(self, symbol: str | InstrumentRef | BarsRequest, /, **kwargs) -> BarsResponse:
        """Fetch a v2 normalized bars response."""

        raise NotImplementedError

    async def get_market_status(
        self, symbol: str | InstrumentRef | MarketStatusRequest | None = None
    ) -> MarketStatusResponse:
        """Fetch normalized market status when the provider supports it."""

        raise NotImplementedError

    async def get_investor_flow(
        self, symbol: str | InstrumentRef | InvestorFlowRequest
    ) -> InvestorFlowResponse:
        """Fetch normalized investor-flow analytics when the provider supports it."""

        raise NotImplementedError

    @abstractmethod
    def stream_trades(
        self,
        symbol: str | InstrumentRef | TradeSubscription | TradeStreamRequest,
    ) -> AsyncIterator[TradeEvent]:
        """Yield trade events for a single-instrument subscription."""

    @abstractmethod
    def stream_orderbook(
        self,
        symbol: str | InstrumentRef | OrderBookSubscription | OrderBookStreamRequest,
    ) -> AsyncIterator[OrderBookEvent]:
        """Yield order book events for a single-instrument subscription."""

    async def fetch_markets(self, *, refresh: bool = False) -> "tuple[Market, ...]":
        """Return listing metadata for instruments supported by this client."""

        raise NotImplementedError

    async def resolve_instrument(
        self, symbol: str, *, venue: "Venue | None" = None
    ) -> InstrumentRef:
        """Resolve a provider-native symbol to a normalized :class:`InstrumentRef`."""

        raise NotImplementedError

    @property
    @abstractmethod
    def market(self) -> MarketNamespace:
        """Return the legacy grouped market-data compatibility namespace."""

    @property
    @abstractmethod
    def streams(self) -> StreamsNamespace:
        """Return the legacy grouped streaming compatibility namespace."""

    @property
    def native(self) -> MarketDataClient:
        """Return the provider-native surface for overflow operations."""

        return self
