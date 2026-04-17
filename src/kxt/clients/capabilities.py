"""Typed capability models for provider clients."""

from __future__ import annotations

from dataclasses import dataclass

from kxt.models.enums import MarketScope, Venue


@dataclass(frozen=True, slots=True)
class CapabilitySupport:
    """Whether a public capability group or operation is supported."""

    supported: bool
    reason: str | None = None
    notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class IntradayBarsCapability:
    """Capability details for normalized intraday bar fetches."""

    supported: bool
    supports_custom_intervals: bool
    supported_scopes: tuple[MarketScope, ...] = ()
    supported_venues: tuple[Venue, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TradeStreamCapability:
    """Capability details for normalized live trade streaming."""

    supported: bool
    requires_instrument: bool
    supports_scope_subscription: bool
    supported_scopes: tuple[MarketScope, ...] = ()
    supported_venues: tuple[Venue, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MarketCapabilities:
    """Public normalized market-data capability surface."""

    bars: CapabilitySupport = CapabilitySupport(False)
    intraday_bars: IntradayBarsCapability = IntradayBarsCapability(False, False)
    recent_trades: CapabilitySupport = CapabilitySupport(False)
    quote: CapabilitySupport = CapabilitySupport(False)
    order_book: CapabilitySupport = CapabilitySupport(False)
    market_status: CapabilitySupport = CapabilitySupport(False)
    investor_flow: CapabilitySupport = CapabilitySupport(False)
    program_trade: CapabilitySupport = CapabilitySupport(False)
    rankings: CapabilitySupport = CapabilitySupport(False)
    member_flow: CapabilitySupport = CapabilitySupport(False)


@dataclass(frozen=True, slots=True)
class StreamCapabilities:
    """Public normalized streaming capability surface."""

    trades: TradeStreamCapability = TradeStreamCapability(False, False, False)
    order_book: CapabilitySupport = CapabilitySupport(False)
    program_trades: CapabilitySupport = CapabilitySupport(False)
    market_status: CapabilitySupport = CapabilitySupport(False)
    investor_flow: CapabilitySupport = CapabilitySupport(False)
    order_updates: CapabilitySupport = CapabilitySupport(False)
    fill_updates: CapabilitySupport = CapabilitySupport(False)


@dataclass(frozen=True, slots=True)
class ClientCapabilities:
    """Inspectable normalized capability metadata for a provider client."""

    provider: str
    requires_credentials: bool
    supported_venues: tuple[Venue, ...] = ()
    supported_scopes: tuple[MarketScope, ...] = ()
    market: MarketCapabilities = MarketCapabilities()
    streams: StreamCapabilities = StreamCapabilities()
    trading: CapabilitySupport = CapabilitySupport(False)
    native: CapabilitySupport = CapabilitySupport(False)
    notes: tuple[str, ...] = ()

    @property
    def intraday_bars(self) -> IntradayBarsCapability:
        """Compatibility alias for the normalized market capability."""

        return self.market.intraday_bars

    @property
    def trade_stream(self) -> TradeStreamCapability:
        """Compatibility alias for the normalized stream capability."""

        return self.streams.trades

    @property
    def order_book_stream(self) -> CapabilitySupport:
        """Compatibility alias for the normalized stream capability."""

        return self.streams.order_book

    @property
    def quote(self) -> CapabilitySupport:
        """Compatibility alias for the normalized market capability."""

        return self.market.quote

    @property
    def recent_trades(self) -> CapabilitySupport:
        """Compatibility alias for the normalized market capability."""

        return self.market.recent_trades

    @property
    def order_book(self) -> CapabilitySupport:
        """Compatibility alias for the normalized market capability."""

        return self.market.order_book

    @property
    def program_trade_stream(self) -> CapabilitySupport:
        """Compatibility alias for the normalized stream capability."""

        return self.streams.program_trades

    @property
    def order_entry(self) -> CapabilitySupport:
        """Compatibility alias for the normalized trading capability."""

        return self.trading
