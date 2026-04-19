"""Thin argparse-based CLI over the current implemented kxt surface."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import traceback
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Sequence

from kxt import (
    AccountSummary,
    InstrumentRef,
    KISClient,
    MarketSegment,
    OrderSide,
    OrderType,
    ProviderOrderRef,
)
from kxt.requests import (
    AccountOverviewRequest,
    BarsRequest,
    BuyingPowerRequest,
    CancelOrderRequest,
    InvestorFlowRequest,
    MarketStatusRequest,
    ModifyOrderRequest,
    OpenOrdersRequest,
    OrderAmendment,
    OrderBookRequest,
    OrderBookStreamRequest,
    OrderEventsStreamRequest,
    OrderHistoryRequest,
    OrderInstruction,
    PositionsRequest,
    ProviderRef,
    QuoteRequest,
    RecentTradesRequest,
    SubmitOrderRequest,
    TradeStreamRequest,
)
from kxt.errors import KXTAuthenticationError, KXTError, KXTValidationError

KIS_APP_KEY_ENV = "KIS_APP_KEY"
KIS_APP_SECRET_ENV = "KIS_APP_SECRET"
KIS_ACCOUNT_NO_ENV = "KIS_ACCOUNT_NO"
KIS_ACCOUNT_PRODUCT_CODE_ENV = "KIS_ACCOUNT_PRODUCT_CODE"
KIS_HTS_ID_ENV = "KIS_HTS_ID"
SUPPORTED_PROVIDERS = ("kis",)


class _HelpFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter):
    """Preserve help layout while also showing defaults."""


def _supported_providers_text() -> str:
    return ", ".join(SUPPORTED_PROVIDERS)


def _provider_help(*, include_default: bool = True) -> str:
    del include_default
    return f"Broker/provider id. Supported today: {_supported_providers_text()}"


def _auth_help_text() -> str:
    return (
        f"Authentication stays environment-variable based. For KIS, set {KIS_APP_KEY_ENV} and "
        f"{KIS_APP_SECRET_ENV}. The CLI intentionally does not accept secrets via flags."
    )


def _scope_help_text() -> str:
    return (
        "Current implemented CLI scope is provider-neutral in grammar but KIS-only in provider support, "
        "with domestic-equity market data in practice today."
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kxt",
        description=(
            "Thin broker-neutral CLI over the currently implemented kxt SDK surface.\n\n"
            "Use this CLI to inspect capabilities, verify auth setup, fetch normalized market-data snapshots, "
            "and consume the currently exposed live streams. Command grammar stays provider-neutral via "
            "--provider even though only KIS is implemented today."
        ),
        epilog=(
            f"Provider support: {_supported_providers_text()}\n"
            f"{_scope_help_text()}\n"
            f"{_auth_help_text()}\n\n"
            "Representative commands:\n"
            "  kxt capabilities\n"
            "  kxt doctor\n"
            "  kxt quote 005930 --provider kis\n"
            "  kxt bars 005930 --provider kis --timeframe day --start 2024-01-01 --end 2024-03-31\n"
            "  kxt bars 005930 --provider kis --timeframe 5m\n"
            "  kxt recent-trades 005930 --provider kis --limit 5\n"
            "  kxt orderbook 005930 --provider kis\n"
            "  kxt orderbook 005930 --provider kis --stream --count 5\n"
            "  kxt market-status --provider kis --symbol 005930\n"
            "  kxt investor-flow 005930 --provider kis\n"
            "  kxt trades 005930 --provider kis --count 5\n\n"
            "Run `kxt <command> --help` for command-specific examples and constraints."
        ),
        formatter_class=_HelpFormatter,
    )
    parser.add_argument("--debug", action="store_true", help="Show Python tracebacks for unexpected internal errors")
    subparsers = parser.add_subparsers(dest="command", required=True)

    capabilities_parser = subparsers.add_parser(
        "capabilities",
        help="Show normalized capability metadata for a provider",
        description=(
            "Show the current kxt capability map for a provider.\n\n"
            "Useful for both people and tools that want to discover which read and stream surfaces are "
            "implemented before issuing data commands."
        ),
        epilog=(
            f"{_scope_help_text()}\n\n"
            "Examples:\n"
            "  kxt capabilities\n"
            "  kxt capabilities --provider kis"
        ),
        formatter_class=_HelpFormatter,
    )
    capabilities_parser.add_argument("--provider", choices=SUPPORTED_PROVIDERS, default="kis", help=_provider_help())
    capabilities_parser.set_defaults(handler=_handle_capabilities)

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Check auth and CLI readiness for a provider",
        description=(
            "Run a lightweight readiness check for the selected provider.\n\n"
            "This command does not make an authenticated market-data request. It reports whether the expected "
            "environment variables are present and reminds you that secrets are never accepted as CLI flags."
        ),
        epilog=(
            f"{_auth_help_text()}\n\n"
            "Examples:\n"
            "  kxt doctor\n"
            "  kxt doctor --provider kis"
        ),
        formatter_class=_HelpFormatter,
    )
    doctor_parser.add_argument("--provider", choices=SUPPORTED_PROVIDERS, default="kis", help=_provider_help())
    doctor_parser.set_defaults(handler=_handle_doctor)

    quote_parser = subparsers.add_parser(
        "quote",
        help="Fetch a normalized quote snapshot",
        description=(
            "Fetch a single normalized quote snapshot for one symbol.\n\n"
            "Use this for last trade, OHLC, change, and volume fields. For best bid/ask or market depth, use "
            "`orderbook` instead."
        ),
        epilog=(
            f"{_scope_help_text()}\n"
            f"{_auth_help_text()}\n\n"
            "Examples:\n"
            "  kxt quote 005930\n"
            "  kxt quote 005930 --provider kis\n"
            "  kxt quote 005930 --provider kis --market-segment KOSPI"
        ),
        formatter_class=_HelpFormatter,
    )
    quote_parser.add_argument("symbol", help="Instrument symbol, for example 005930")
    quote_parser.add_argument("--provider", choices=SUPPORTED_PROVIDERS, default="kis", help=_provider_help())
    quote_parser.add_argument(
        "--market-segment",
        choices=tuple(segment.value for segment in MarketSegment),
        help="Optional domestic-equity market segment hint",
    )
    quote_parser.set_defaults(handler=_handle_quote)

    bars_parser = subparsers.add_parser(
        "bars",
        help="Fetch normalized historical bars",
        description=(
            "Fetch normalized bars for one symbol using the SDK timeframe contract.\n\n"
            "Use timeframe expressions such as `1m`, `5m`, `day`, `week`, `month`, or `year`. `timeframe` is "
            "the public contract; provider-specific interval names are intentionally not exposed here."
        ),
        epilog=(
            f"{_scope_help_text()}\n"
            f"{_auth_help_text()}\n\n"
            "Examples:\n"
            "  kxt bars 005930\n"
            "  kxt bars 005930 --timeframe day --start 2024-01-01 --end 2024-03-31\n"
            "  kxt bars 005930 --timeframe 5m --market-segment KOSPI\n"
            "  kxt bars 005930 --timeframe week --unadjusted"
        ),
        formatter_class=_HelpFormatter,
    )
    bars_parser.add_argument("symbol", help="Instrument symbol, for example 005930")
    bars_parser.add_argument("--provider", choices=SUPPORTED_PROVIDERS, default="kis", help=_provider_help())
    bars_parser.add_argument(
        "--timeframe",
        default="day",
        help="Bar timeframe expression, for example 1m, 5m, day, week, month, or year",
    )
    bars_parser.add_argument("--start", help="Start date/datetime in ISO-8601 format")
    bars_parser.add_argument("--end", help="End date/datetime in ISO-8601 format")
    bars_parser.add_argument(
        "--market-segment",
        choices=tuple(segment.value for segment in MarketSegment),
        help="Optional domestic-equity market segment hint",
    )
    adjusted_group = bars_parser.add_mutually_exclusive_group()
    adjusted_group.add_argument("--adjusted", action="store_true", dest="adjusted", default=True, help="Use adjusted prices")
    adjusted_group.add_argument("--unadjusted", action="store_false", dest="adjusted", help="Use unadjusted prices")
    bars_parser.set_defaults(handler=_handle_bars)

    recent_trades_parser = subparsers.add_parser(
        "recent-trades",
        help="Fetch normalized recent trades",
        description=(
            "Fetch recent trade prints for one symbol.\n\n"
            "Current KIS support is limited to same-day domestic-equity trades. Use `trades` for the live stream "
            "surface instead of historical polling."
        ),
        epilog=(
            f"{_scope_help_text()}\n"
            f"Constraint: KIS recent-trades is same-day only today.\n"
            f"{_auth_help_text()}\n\n"
            "Examples:\n"
            "  kxt recent-trades 005930\n"
            "  kxt recent-trades 005930 --limit 5\n"
            "  kxt recent-trades 005930 --start 2026-04-16T09:00:00 --end 2026-04-16T09:05:00"
        ),
        formatter_class=_HelpFormatter,
    )
    recent_trades_parser.add_argument("symbol", help="Instrument symbol, for example 005930")
    recent_trades_parser.add_argument("--provider", choices=SUPPORTED_PROVIDERS, default="kis", help=_provider_help())
    recent_trades_parser.add_argument(
        "--market-segment",
        choices=tuple(segment.value for segment in MarketSegment),
        help="Optional domestic-equity market segment hint",
    )
    recent_trades_parser.add_argument("--start", help="Start date/datetime in ISO-8601 format")
    recent_trades_parser.add_argument("--end", help="End date/datetime in ISO-8601 format")
    recent_trades_parser.add_argument("--limit", type=int, default=100, help="Maximum trades to return")
    recent_trades_parser.set_defaults(handler=_handle_recent_trades)

    orderbook_parser = subparsers.add_parser(
        "orderbook",
        help="Fetch or stream a normalized order book",
        description=(
            "Fetch a snapshot order book or stream live order book updates for one symbol.\n\n"
            "Without `--stream`, this command performs a one-shot snapshot read. With `--stream`, it keeps "
            "printing normalized updates until interrupted or until `--count` is reached."
        ),
        epilog=(
            f"{_scope_help_text()}\n"
            "Constraint: `--count` matters only with `--stream`.\n"
            f"{_auth_help_text()}\n\n"
            "Examples:\n"
            "  kxt orderbook 005930\n"
            "  kxt orderbook 005930 --stream\n"
            "  kxt orderbook 005930 --stream --count 5\n"
            "  kxt orderbook 005930 --market-segment KOSPI"
        ),
        formatter_class=_HelpFormatter,
    )
    orderbook_parser.add_argument("symbol", help="Instrument symbol, for example 005930")
    orderbook_parser.add_argument("--provider", choices=SUPPORTED_PROVIDERS, default="kis", help=_provider_help())
    orderbook_parser.add_argument(
        "--market-segment",
        choices=tuple(segment.value for segment in MarketSegment),
        help="Optional domestic-equity market segment hint",
    )
    orderbook_parser.add_argument("--stream", action="store_true", help="Stream live order book updates")
    orderbook_parser.add_argument("--count", type=int, help="Stop after emitting this many streamed snapshots; only applies with --stream")
    orderbook_parser.set_defaults(handler=_handle_orderbook)

    market_status_parser = subparsers.add_parser(
        "market-status",
        help="Fetch normalized market status",
        description=(
            "Fetch the current normalized market status.\n\n"
            "For KIS, this is derived from provider quote-state fields. Use `--symbol` when you want to anchor the "
            "lookup to a representative instrument."
        ),
        epilog=(
            f"{_scope_help_text()}\n"
            "Constraint: current KIS market-status is derived from quote payload state fields, not a dedicated stream.\n"
            f"{_auth_help_text()}\n\n"
            "Examples:\n"
            "  kxt market-status\n"
            "  kxt market-status --symbol 005930\n"
            "  kxt market-status --provider kis --symbol 005930 --market-segment KOSPI"
        ),
        formatter_class=_HelpFormatter,
    )
    market_status_parser.add_argument("--provider", choices=SUPPORTED_PROVIDERS, default="kis", help=_provider_help())
    market_status_parser.add_argument("--symbol", help="Optional instrument symbol to anchor the status lookup")
    market_status_parser.add_argument(
        "--market-segment",
        choices=tuple(segment.value for segment in MarketSegment),
        help="Optional domestic-equity market segment hint",
    )
    market_status_parser.set_defaults(handler=_handle_market_status)

    investor_flow_parser = subparsers.add_parser(
        "investor-flow",
        help="Fetch normalized investor-flow analytics",
        description=(
            "Fetch investor-flow analytics for one symbol.\n\n"
            "Current KIS support is limited to the domestic-equity per-symbol regular-session aggregate published "
            "after the cash session closes."
        ),
        epilog=(
            f"{_scope_help_text()}\n"
            "Constraint: current KIS investor-flow is regular-session aggregate data, not intraday streaming data.\n"
            f"{_auth_help_text()}\n\n"
            "Examples:\n"
            "  kxt investor-flow 005930\n"
            "  kxt investor-flow 005930 --provider kis\n"
            "  kxt investor-flow 005930 --market-segment KOSPI"
        ),
        formatter_class=_HelpFormatter,
    )
    investor_flow_parser.add_argument("symbol", help="Instrument symbol, for example 005930")
    investor_flow_parser.add_argument("--provider", choices=SUPPORTED_PROVIDERS, default="kis", help=_provider_help())
    investor_flow_parser.add_argument(
        "--market-segment",
        choices=tuple(segment.value for segment in MarketSegment),
        help="Optional domestic-equity market segment hint",
    )
    investor_flow_parser.set_defaults(handler=_handle_investor_flow)

    trades_parser = subparsers.add_parser(
        "trades",
        help="Stream normalized live trades",
        description=(
            "Stream normalized live trades for one symbol.\n\n"
            "This is a streaming command, not a historical query. It keeps printing events until interrupted or "
            "until `--count` is reached."
        ),
        epilog=(
            f"{_scope_help_text()}\n"
            "Constraint: `trades` is stream-only; use `recent-trades` for same-day snapshot-style trade retrieval.\n"
            f"{_auth_help_text()}\n\n"
            "Examples:\n"
            "  kxt trades 005930\n"
            "  kxt trades 005930 --count 5\n"
            "  kxt trades 005930 --provider kis --market-segment KOSPI --count 20"
        ),
        formatter_class=_HelpFormatter,
    )
    trades_parser.add_argument("symbol", help="Instrument symbol, for example 005930")
    trades_parser.add_argument("--provider", choices=SUPPORTED_PROVIDERS, default="kis", help=_provider_help())
    trades_parser.add_argument(
        "--market-segment",
        choices=tuple(segment.value for segment in MarketSegment),
        help="Optional domestic-equity market segment hint",
    )
    trades_parser.add_argument("--count", type=int, help="Stop after emitting this many trades")
    trades_parser.set_defaults(handler=_handle_trades)

    # ---- account / trading / notifications ----

    balance_parser = subparsers.add_parser(
        "balance",
        help="Fetch account equity snapshot + positions (KIS inquire-balance)",
        formatter_class=_HelpFormatter,
    )
    _add_account_args(balance_parser)
    balance_parser.set_defaults(handler=_handle_balance)

    positions_parser = subparsers.add_parser(
        "positions",
        help="Fetch positions (projection of inquire-balance output1)",
        formatter_class=_HelpFormatter,
    )
    _add_account_args(positions_parser)
    positions_parser.set_defaults(handler=_handle_positions)

    buying_power_parser = subparsers.add_parser(
        "buying-power",
        help="Fetch buying power for a symbol (KIS inquire-psbl-order)",
        formatter_class=_HelpFormatter,
    )
    buying_power_parser.add_argument("symbol", help="Instrument symbol, e.g. 005930")
    buying_power_parser.add_argument("--price", help="Reference price (ORD_UNPR). '0' for market")
    buying_power_parser.add_argument(
        "--order-type",
        choices=tuple(t.value for t in OrderType),
        default=OrderType.LIMIT.value,
    )
    buying_power_parser.add_argument("--include-cma", action="store_true")
    _add_account_args(buying_power_parser)
    buying_power_parser.set_defaults(handler=_handle_buying_power)

    open_orders_parser = subparsers.add_parser(
        "open-orders",
        help="Fetch cancelable/modifiable open orders (KIS inquire-psbl-rvsecncl)",
        formatter_class=_HelpFormatter,
    )
    open_orders_parser.add_argument("--symbol", help="Optional symbol filter")
    _add_account_args(open_orders_parser)
    open_orders_parser.set_defaults(handler=_handle_open_orders)

    order_history_parser = subparsers.add_parser(
        "order-history",
        help="Fetch 3-month order/fill history (KIS inquire-daily-ccld)",
        formatter_class=_HelpFormatter,
    )
    order_history_parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    order_history_parser.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    order_history_parser.add_argument("--symbol", help="Optional symbol filter")
    order_history_parser.add_argument(
        "--side",
        choices=tuple(s.value for s in OrderSide),
        help="Optional side filter",
    )
    order_history_parser.add_argument(
        "--fill-filter",
        choices=("all", "filled", "unfilled"),
        default="all",
    )
    _add_account_args(order_history_parser)
    order_history_parser.set_defaults(handler=_handle_order_history)

    place_order_parser = subparsers.add_parser(
        "place-order",
        help="Submit a cash order (KIS order-cash)",
        formatter_class=_HelpFormatter,
    )
    place_order_parser.add_argument("symbol", help="Instrument symbol, e.g. 005930")
    place_order_parser.add_argument(
        "--side",
        choices=tuple(s.value for s in OrderSide),
        required=True,
    )
    place_order_parser.add_argument(
        "--order-type",
        choices=tuple(t.value for t in OrderType),
        default=OrderType.LIMIT.value,
    )
    place_order_parser.add_argument("--quantity", required=True)
    place_order_parser.add_argument("--limit-price", help="Required for non-market orders")
    _add_account_args(place_order_parser)
    place_order_parser.set_defaults(handler=_handle_place_order)

    cancel_order_parser = subparsers.add_parser(
        "cancel-order",
        help="Cancel an existing order (KIS order-rvsecncl, 02)",
        formatter_class=_HelpFormatter,
    )
    cancel_order_parser.add_argument("--order-id", required=True)
    cancel_order_parser.add_argument("--origin-org-no", help="KRX_FWDG_ORD_ORGNO")
    cancel_order_parser.add_argument("--quantity", help="Partial cancel quantity")
    cancel_order_parser.add_argument("--partial", action="store_true", help="Disable QTY_ALL_ORD_YN")
    _add_account_args(cancel_order_parser)
    cancel_order_parser.set_defaults(handler=_handle_cancel_order)

    modify_order_parser = subparsers.add_parser(
        "modify-order",
        help="Modify an existing order (KIS order-rvsecncl, 01)",
        formatter_class=_HelpFormatter,
    )
    modify_order_parser.add_argument("--order-id", required=True)
    modify_order_parser.add_argument("--origin-org-no", help="KRX_FWDG_ORD_ORGNO")
    modify_order_parser.add_argument("--quantity")
    modify_order_parser.add_argument("--limit-price")
    modify_order_parser.add_argument(
        "--order-type",
        choices=tuple(t.value for t in OrderType),
    )
    _add_account_args(modify_order_parser)
    modify_order_parser.set_defaults(handler=_handle_modify_order)

    order_events_parser = subparsers.add_parser(
        "order-events",
        help="Stream realtime order+fill notifications (KIS H0STCNI0)",
        formatter_class=_HelpFormatter,
    )
    order_events_parser.add_argument(
        "--hts-id",
        help=f"HTS user id for subscription (fallback: {KIS_HTS_ID_ENV} env var)",
    )
    order_events_parser.add_argument("--count", type=int, help="Stop after N events")
    _add_account_args(order_events_parser)
    order_events_parser.set_defaults(handler=_handle_order_events)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = args.handler
    try:
        result = handler(args)
        if asyncio.iscoroutine(result):
            return asyncio.run(result)
        return int(result)
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130
    except KXTError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        if args.debug:
            traceback.print_exception(exc, file=sys.stderr)
        else:
            detail = str(exc).strip() or type(exc).__name__
            print(f"Unexpected error: {detail}", file=sys.stderr)
        return 1


def _handle_capabilities(args: argparse.Namespace) -> int:
    print(_to_json(_capabilities_for_provider(args.provider)))
    return 0


def _handle_doctor(args: argparse.Namespace) -> int:
    _require_supported_provider(args.provider)

    app_key = bool(os.getenv(KIS_APP_KEY_ENV, "").strip())
    app_secret = bool(os.getenv(KIS_APP_SECRET_ENV, "").strip())
    ready = app_key and app_secret
    result = {
        "provider": "kis",
        "requires_credentials": True,
        "credential_env": {
            KIS_APP_KEY_ENV: "set" if app_key else "missing",
            KIS_APP_SECRET_ENV: "set" if app_secret else "missing",
        },
        "ready": ready,
        "checks": (
            "SDK import OK",
            "CLI help does not require credentials",
            "No secrets are accepted as CLI arguments",
        ),
        "notes": (
            f"Currently implemented providers: {_supported_providers_text()}.",
            "Set credentials with environment variables before running authenticated commands.",
            "KIS websocket streaming connects directly by default; set KXT_KIS_WS_PROXY=auto or a proxy URL to opt into websocket proxying.",
        ),
    }
    print(_to_json(result))
    return 0 if ready else 1


async def _handle_quote(args: argparse.Namespace) -> int:
    _require_supported_provider(args.provider)

    async with _build_kis_client() as client:
        quote = await client.get_quote(QuoteRequest(instrument=_instrument_from_args(args)))

    print(_to_json(quote))
    return 0


async def _handle_bars(args: argparse.Namespace) -> int:
    _require_supported_provider(args.provider)
    instrument = _instrument_from_args(args)
    start = _parse_temporal_arg(args.start, field_name="start")
    end = _parse_temporal_arg(args.end, field_name="end")

    async with _build_kis_client() as client:
        bars = await client.get_bars(
            BarsRequest(
                instrument=instrument,
                timeframe=args.timeframe,
                start=start,
                end=end,
                adjusted=args.adjusted,
            )
        )

    print(_to_json(bars))
    return 0


async def _handle_recent_trades(args: argparse.Namespace) -> int:
    _require_supported_provider(args.provider)
    if args.limit < 1:
        raise KXTValidationError("--limit must be >= 1")

    async with _build_kis_client() as client:
        trades = await client.get_recent_trades(
            RecentTradesRequest(
                instrument=_instrument_from_args(args),
                start=_parse_temporal_arg(args.start, field_name="start"),
                end=_parse_temporal_arg(args.end, field_name="end"),
                limit=args.limit,
            )
        )

    print(_to_json(trades))
    return 0


async def _handle_orderbook(args: argparse.Namespace) -> int:
    _require_supported_provider(args.provider)
    if args.count is not None and args.count < 1:
        raise KXTValidationError("--count must be >= 1 when provided")

    instrument = _instrument_from_args(args)
    async with _build_kis_client() as client:
        if not args.stream:
            orderbook = await client.get_orderbook(OrderBookRequest(instrument=instrument))
            print(_to_json(orderbook))
            return 0

        emitted = 0
        async for orderbook in client.stream_orderbook(OrderBookStreamRequest(instrument=instrument)):
            print(_to_json(orderbook))
            emitted += 1
            if args.count is not None and emitted >= args.count:
                break

    return 0


async def _handle_market_status(args: argparse.Namespace) -> int:
    _require_supported_provider(args.provider)
    instrument = None if not args.symbol else _instrument_from_args(args)

    async with _build_kis_client() as client:
        status = await client.get_market_status(MarketStatusRequest(instrument=instrument))

    print(_to_json(status))
    return 0


async def _handle_investor_flow(args: argparse.Namespace) -> int:
    _require_supported_provider(args.provider)

    async with _build_kis_client() as client:
        investor_flow = await client.get_investor_flow(InvestorFlowRequest(instrument=_instrument_from_args(args)))

    print(_to_json(investor_flow))
    return 0


async def _handle_trades(args: argparse.Namespace) -> int:
    _require_supported_provider(args.provider)
    if args.count is not None and args.count < 1:
        raise KXTValidationError("--count must be >= 1 when provided")

    subscription = TradeStreamRequest(instrument=_instrument_from_args(args))
    emitted = 0

    async with _build_kis_client() as client:
        async for trade in client.stream_trades(subscription):
            print(_to_json(trade))
            emitted += 1
            if args.count is not None and emitted >= args.count:
                break

    return 0


def _instrument_from_args(args: argparse.Namespace) -> InstrumentRef:
    market_segment = MarketSegment(args.market_segment) if args.market_segment else None
    return InstrumentRef(symbol=args.symbol, market_segment=market_segment)


def _require_supported_provider(provider: str) -> None:
    if provider not in SUPPORTED_PROVIDERS:
        raise KXTValidationError(f"Unsupported provider: {provider}")


def _capabilities_for_provider(provider: str) -> Any:
    _require_supported_provider(provider)
    if provider == "kis":
        return KISClient._CAPABILITIES
    raise KXTValidationError(f"Unsupported provider: {provider}")


def _build_kis_client() -> KISClient:
    app_key = os.getenv(KIS_APP_KEY_ENV, "").strip()
    app_secret = os.getenv(KIS_APP_SECRET_ENV, "").strip()
    if not app_key or not app_secret:
        missing = []
        if not app_key:
            missing.append(KIS_APP_KEY_ENV)
        if not app_secret:
            missing.append(KIS_APP_SECRET_ENV)
        missing_text = ", ".join(missing)
        raise KXTAuthenticationError(
            f"Missing KIS credentials: {missing_text}. Set them as environment variables. "
            "The kxt CLI intentionally does not accept secrets via command arguments."
        )
    return KISClient(
        app_key=app_key,
        app_secret=app_secret,
        account_no=os.getenv(KIS_ACCOUNT_NO_ENV, "").strip() or None,
        account_product_code=os.getenv(KIS_ACCOUNT_PRODUCT_CODE_ENV, "").strip() or None,
        hts_id=os.getenv(KIS_HTS_ID_ENV, "").strip() or None,
    )


def _parse_temporal_arg(value: str | None, *, field_name: str) -> date | datetime | None:
    if value is None:
        return None
    try:
        if "T" in value or " " in value:
            return datetime.fromisoformat(value)
        return date.fromisoformat(value)
    except ValueError as exc:
        raise KXTValidationError(f"{field_name} must be a valid ISO-8601 date or datetime") from exc


def _to_json(value: Any) -> str:
    return json.dumps(value, default=_json_default, ensure_ascii=False, indent=2)


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, tuple):
        return list(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


if __name__ == "__main__":
    raise SystemExit(main())


# ---- account / trading / notification CLI helpers ------------------------------


def _add_account_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--provider",
        choices=SUPPORTED_PROVIDERS,
        default="kis",
        help=_provider_help(),
    )
    parser.add_argument(
        "--account-no",
        help=f"Account number (CANO). Fallback: {KIS_ACCOUNT_NO_ENV} env var.",
    )
    parser.add_argument(
        "--account-product-code",
        help=f"Account product code (ACNT_PRDT_CD). Fallback: {KIS_ACCOUNT_PRODUCT_CODE_ENV} env var.",
    )


def _account_from_args(args: argparse.Namespace) -> AccountSummary:
    account_no = (getattr(args, "account_no", None) or os.getenv(KIS_ACCOUNT_NO_ENV, "")).strip()
    product_code = (
        getattr(args, "account_product_code", None)
        or os.getenv(KIS_ACCOUNT_PRODUCT_CODE_ENV, "")
    ).strip()
    if not account_no:
        raise KXTValidationError(
            f"account number is required (pass --account-no or set {KIS_ACCOUNT_NO_ENV})"
        )
    return AccountSummary(
        provider=ProviderRef(provider="kis"),
        account_id=account_no,
        name=None,
        product_code=product_code or None,
    )


def _decimal_arg(value: str | None, *, name: str) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(value)
    except Exception as exc:
        raise KXTValidationError(f"{name} must be a valid decimal number") from exc


async def _handle_balance(args: argparse.Namespace) -> int:
    _require_supported_provider(args.provider)
    account = _account_from_args(args)
    async with _build_kis_client() as client:
        overview = await client.get_account_overview(AccountOverviewRequest(account=account))
    print(_to_json(overview))
    return 0


async def _handle_positions(args: argparse.Namespace) -> int:
    _require_supported_provider(args.provider)
    account = _account_from_args(args)
    async with _build_kis_client() as client:
        response = await client.get_positions(PositionsRequest(account=account))
    print(_to_json(response))
    return 0


async def _handle_buying_power(args: argparse.Namespace) -> int:
    _require_supported_provider(args.provider)
    account = _account_from_args(args)
    request = BuyingPowerRequest(
        account=account,
        instrument=InstrumentRef(symbol=args.symbol),
        price=_decimal_arg(args.price, name="--price"),
        order_type=OrderType(args.order_type),
        include_cma=bool(args.include_cma),
    )
    async with _build_kis_client() as client:
        response = await client.get_buying_power(request)
    print(_to_json(response))
    return 0


async def _handle_open_orders(args: argparse.Namespace) -> int:
    _require_supported_provider(args.provider)
    account = _account_from_args(args)
    request = OpenOrdersRequest(
        account=account,
        instrument=InstrumentRef(symbol=args.symbol) if args.symbol else None,
    )
    async with _build_kis_client() as client:
        response = await client.get_open_orders(request)
    print(_to_json(response))
    return 0


async def _handle_order_history(args: argparse.Namespace) -> int:
    _require_supported_provider(args.provider)
    account = _account_from_args(args)
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    side = OrderSide(args.side) if args.side else None
    request = OrderHistoryRequest(
        account=account,
        start=start,
        end=end,
        instrument=InstrumentRef(symbol=args.symbol) if args.symbol else None,
        side_filter=side,
        fill_filter=args.fill_filter,
    )
    async with _build_kis_client() as client:
        response = await client.get_order_history(request)
    print(_to_json(response))
    return 0


async def _handle_place_order(args: argparse.Namespace) -> int:
    _require_supported_provider(args.provider)
    account = _account_from_args(args)
    quantity = _decimal_arg(args.quantity, name="--quantity")
    if quantity is None:
        raise KXTValidationError("--quantity is required")
    instruction = OrderInstruction(
        instrument=InstrumentRef(symbol=args.symbol),
        side=OrderSide(args.side),
        order_type=OrderType(args.order_type),
        quantity=quantity,
        limit_price=_decimal_arg(args.limit_price, name="--limit-price"),
    )
    request = SubmitOrderRequest(account=account, instruction=instruction)
    async with _build_kis_client() as client:
        response = await client.submit_order(request)
    print(_to_json(response))
    return 0


async def _handle_cancel_order(args: argparse.Namespace) -> int:
    _require_supported_provider(args.provider)
    account = _account_from_args(args)
    order_ref = ProviderOrderRef(provider="kis", order_id=args.order_id, account_id=account.account_id)
    from kxt import OrderCorrelationKey as _OCK
    correlation = _OCK(order_ref=order_ref, origin_org_no=args.origin_org_no)
    request = CancelOrderRequest(
        account=account,
        order_ref=order_ref,
        quantity=_decimal_arg(args.quantity, name="--quantity"),
        cancel_all=not args.partial,
        correlation_key=correlation,
    )
    async with _build_kis_client() as client:
        response = await client.cancel_order(request)
    print(_to_json(response))
    return 0


async def _handle_modify_order(args: argparse.Namespace) -> int:
    _require_supported_provider(args.provider)
    account = _account_from_args(args)
    order_ref = ProviderOrderRef(provider="kis", order_id=args.order_id, account_id=account.account_id)
    from kxt import OrderCorrelationKey as _OCK
    correlation = _OCK(order_ref=order_ref, origin_org_no=args.origin_org_no)
    amendment = OrderAmendment(
        quantity=_decimal_arg(args.quantity, name="--quantity"),
        limit_price=_decimal_arg(args.limit_price, name="--limit-price"),
        order_type=OrderType(args.order_type) if args.order_type else None,
    )
    request = ModifyOrderRequest(
        account=account,
        order_ref=order_ref,
        amendment=amendment,
        correlation_key=correlation,
    )
    async with _build_kis_client() as client:
        response = await client.modify_order(request)
    print(_to_json(response))
    return 0


async def _handle_order_events(args: argparse.Namespace) -> int:
    _require_supported_provider(args.provider)
    if args.count is not None and args.count < 1:
        raise KXTValidationError("--count must be >= 1 when provided")
    account_no = (getattr(args, "account_no", None) or os.getenv(KIS_ACCOUNT_NO_ENV, "")).strip()
    account: AccountSummary | None = None
    if account_no:
        account = AccountSummary(
            provider=ProviderRef(provider="kis"),
            account_id=account_no,
            name=None,
            product_code=(
                getattr(args, "account_product_code", None)
                or os.getenv(KIS_ACCOUNT_PRODUCT_CODE_ENV, "")
            ).strip()
            or None,
        )
    hts_id = (args.hts_id or os.getenv(KIS_HTS_ID_ENV, "")).strip() or None
    request = OrderEventsStreamRequest(account=account, hts_id=hts_id)
    emitted = 0
    async with _build_kis_client() as client:
        async for event in client.stream_order_events(request):
            print(_to_json(event))
            emitted += 1
            if args.count is not None and emitted >= args.count:
                break
    return 0
