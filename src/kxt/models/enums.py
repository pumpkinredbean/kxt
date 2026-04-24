"""Shared enums for market access contracts."""

from __future__ import annotations

from enum import StrEnum


class Venue(StrEnum):
    """Trading venue or market center identity."""

    KRX = "KRX"


class MarketSegment(StrEnum):
    """Board or listing segment within a venue."""

    KOSPI = "KOSPI"
    KOSDAQ = "KOSDAQ"
    KONEX = "KONEX"


class MarketScope(StrEnum):
    """Request or subscription scope, distinct from venue identity."""

    TOTAL = "TOTAL"
    KRX = "KRX"
    NXT = "NXT"


class AssetClass(StrEnum):
    """Broad asset classification."""

    EQUITY = "EQUITY"
    FUTURES = "FUTURES"
    OPTIONS = "OPTIONS"
    ETF = "ETF"
    ETN = "ETN"
    DERIVATIVE = "DERIVATIVE"
    INDEX = "INDEX"


class InstrumentType(StrEnum):
    """More specific instrument kind."""

    COMMON_STOCK = "COMMON_STOCK"
    PREFERRED_STOCK = "PREFERRED_STOCK"
    ETF = "ETF"
    ETN = "ETN"
    FUTURE = "FUTURE"
    OPTION = "OPTION"
    INDEX = "INDEX"


class TradeSide(StrEnum):
    """Execution aggressor or directional side when known."""

    BUY = "BUY"
    SELL = "SELL"
    UNKNOWN = "UNKNOWN"


class BarTimeframe(StrEnum):
    """Normalized K-line timeframe families."""

    MINUTE = "MINUTE"
    DAY = "DAY"
    WEEK = "WEEK"
    MONTH = "MONTH"
    YEAR = "YEAR"


class SessionType(StrEnum):
    """Trading session identity when relevant."""

    REGULAR = "REGULAR"
    NIGHT = "NIGHT"
    UNKNOWN = "UNKNOWN"


class MarketPhase(StrEnum):
    """High-level market phase used by normalized status reads."""

    PREOPEN = "PREOPEN"
    OPEN = "OPEN"
    AUCTION = "AUCTION"
    AFTER_HOURS = "AFTER_HOURS"
    CLOSED = "CLOSED"
    HALTED = "HALTED"
    UNKNOWN = "UNKNOWN"


class InvestorCategory(StrEnum):
    """Broad normalized investor categories for flow analytics."""

    FOREIGN = "FOREIGN"
    INSTITUTION = "INSTITUTION"
    RETAIL = "RETAIL"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class RankingKind(StrEnum):
    """Ranking window or category selector."""

    PRICE = "PRICE"
    VOLUME = "VOLUME"
    VALUE = "VALUE"
    MOMENTUM = "MOMENTUM"
    FLUCTUATION = "FLUCTUATION"
    MARKET_CAP = "MARKET_CAP"
    VOLUME_POWER = "VOLUME_POWER"
    TOP_INTEREST = "TOP_INTEREST"
    SHORT_SALE = "SHORT_SALE"
    CREDIT_BALANCE = "CREDIT_BALANCE"
    QUOTE_BALANCE = "QUOTE_BALANCE"
    CUSTOM = "CUSTOM"


class OrderSide(StrEnum):
    """Order intent side."""

    BUY = "BUY"
    SELL = "SELL"


class OrderType(StrEnum):
    """Normalized order instruction style."""

    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"
    BEST = "BEST"
    UNKNOWN = "UNKNOWN"


class OrderLifecycleState(StrEnum):
    """Normalized lifecycle state for order updates."""

    PENDING = "PENDING"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    WORKING = "WORKING"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    UNKNOWN = "UNKNOWN"
