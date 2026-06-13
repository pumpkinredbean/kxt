"""Concrete async client for Toss Invest Open API."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterable
from contextlib import suppress
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import httpx

from kxt.clients.base import MarketDataClient, MarketNamespace, StreamsNamespace
from kxt.clients.capabilities import (
    CapabilitySupport,
    ClientCapabilities,
    IntradayBarsCapability,
    MarketCapabilities,
    StreamCapabilities,
    TradeStreamCapability,
)
from kxt.errors import KXTAPIError, KXTUnsupportedError, KXTValidationError
from kxt.markets.master import Market
from kxt.models import (
    AccountSummary,
    AccountsRequest,
    AccountsResponse,
    BarTimeframe,
    BarsRequest,
    BarsResponse,
    BuyingPowerRequest,
    BuyingPowerResponse,
    CancelOrderRequest,
    CancelOrderResponse,
    InstrumentRef,
    IntradayBar,
    MarketBar,
    MarketScope,
    MarketStatusRequest,
    MarketStatusResponse,
    ModifyOrderRequest,
    ModifyOrderResponse,
    OpenOrder,
    OpenOrdersRequest,
    OpenOrdersResponse,
    OrderAmendment,
    OrderAcknowledgement,
    OrderBookEvent,
    OrderBookRequest,
    OrderBookResponse,
    OrderBookSnapshot,
    OrderBookStreamRequest,
    OrderCorrelationKey,
    OrderHistoryCursor,
    OrderHistoryRequest,
    OrderHistoryResponse,
    OrderInstruction,
    OrderLifecycleState,
    OrderSide,
    OrderType,
    PositionsRequest,
    PositionsResponse,
    ProviderOrderRef,
    ProviderRef,
    QuoteRequest,
    QuoteResponse,
    QuoteSnapshot,
    QuotesResponse,
    RecentTradesRequest,
    RecentTradesResponse,
    SubmitOrderRequest,
    SubmitOrderResponse,
    Trade,
    TradeEvent,
    TradeStreamRequest,
    Venue,
)
from kxt.streams.subscriptions import OrderBookSubscription, TradeSubscription

from .parsing import (
    PROVIDER,
    bars_response_from_market_bars,
    cancel_response_from_ack,
    coerce_datetime,
    modify_response_from_ack,
    orderbook_response_from_snapshot,
    parse_accounts,
    parse_buying_power,
    parse_market_bars,
    parse_market_status,
    parse_markets,
    parse_open_orders,
    parse_order_ack,
    parse_order_history,
    parse_orderbook_snapshot,
    parse_positions,
    parse_quote_snapshot,
    parse_quote_snapshots,
    parse_recent_trades,
    quote_response_from_snapshot,
    quotes_response_from_snapshots,
    recent_trades_response_from_trades,
    submit_response_from_ack,
)
from .transport import TossInvestTransport


class _TossInvestMarketNamespace(MarketNamespace):
    """Legacy grouped market-data compatibility namespace."""

    def __init__(self, client: "TossInvestClient") -> None:
        self._client = client

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
        return await self._client.fetch_bars(
            symbol,
            timeframe=timeframe,
            start=start,
            end=end,
            interval_minutes=interval_minutes,
            adjusted=adjusted,
        )

    async def fetch_intraday_bars(
        self,
        symbol: str | InstrumentRef,
        *,
        interval_minutes: int = 1,
    ) -> tuple[IntradayBar, ...]:
        return await self._client.fetch_intraday_bars(
            symbol,
            interval_minutes=interval_minutes,
        )

    async def fetch_recent_trades(
        self,
        symbol: str | InstrumentRef,
        *,
        start: date | datetime | None = None,
        end: date | datetime | None = None,
        limit: int = 100,
    ) -> tuple[Trade, ...]:
        return await self._client.fetch_recent_trades(
            symbol,
            start=start,
            end=end,
            limit=limit,
        )


class _TossInvestStreamsNamespace(StreamsNamespace):
    """Grouped stream namespace that reports REST-only Toss support accurately."""

    def stream_trades(
        self, symbol: str | InstrumentRef | TradeSubscription | TradeStreamRequest
    ) -> AsyncIterator[TradeEvent]:
        raise KXTUnsupportedError("Toss Invest Open API currently exposes REST endpoints only")


class TossInvestClient(MarketDataClient):
    """Async Toss Invest Open API client."""

    client_id = PROVIDER
    _CAPABILITIES = ClientCapabilities(
        provider=PROVIDER,
        requires_credentials=True,
        supported_venues=(Venue.KRX, Venue.NYSE, Venue.NASDAQ, Venue.AMEX),
        supported_scopes=(MarketScope.KRX, MarketScope.NXT, MarketScope.TOTAL),
        market=MarketCapabilities(
            bars=CapabilitySupport(
                True,
                notes=(
                    "Toss Invest candles support 1m and 1d provider intervals.",
                    "kxt aggregates minute bars locally for multi-minute requests.",
                ),
            ),
            intraday_bars=IntradayBarsCapability(
                supported=True,
                supports_custom_intervals=True,
                supported_venues=(Venue.KRX, Venue.NYSE, Venue.NASDAQ, Venue.AMEX),
                notes=("Backed by /api/v1/candles interval=1m.",),
            ),
            quote=CapabilitySupport(True, notes=("Backed by /api/v1/prices.",)),
            recent_trades=CapabilitySupport(True, notes=("Backed by /api/v1/trades.",)),
            order_book=CapabilitySupport(True, notes=("Backed by /api/v1/orderbook.",)),
            market_status=CapabilitySupport(
                True,
                notes=("Domestic market status is derived from /api/v1/market-calendar/KR.",),
            ),
            investor_flow=CapabilitySupport(False, reason="Toss Invest Open API does not expose investor-flow endpoints."),
            program_trade=CapabilitySupport(False, reason="Toss Invest Open API does not expose program-trade endpoints."),
            rankings=CapabilitySupport(False, reason="Toss Invest Open API does not expose ranking endpoints."),
            member_flow=CapabilitySupport(False, reason="Toss Invest Open API does not expose member-flow endpoints."),
        ),
        streams=StreamCapabilities(
            trades=TradeStreamCapability(
                supported=False,
                requires_instrument=True,
                supports_scope_subscription=False,
                notes=("Toss Invest Open API currently exposes REST endpoints only.",),
            ),
            order_book=CapabilitySupport(False, reason="Toss Invest Open API currently exposes REST endpoints only."),
            program_trades=CapabilitySupport(False, reason="Toss Invest Open API currently exposes REST endpoints only."),
            market_status=CapabilitySupport(False, reason="Toss Invest Open API currently exposes REST endpoints only."),
            member_flow=CapabilitySupport(False, reason="Toss Invest Open API currently exposes REST endpoints only."),
            order_updates=CapabilitySupport(False, reason="Toss Invest Open API currently exposes REST endpoints only."),
            fill_updates=CapabilitySupport(False, reason="Toss Invest Open API currently exposes REST endpoints only."),
        ),
        trading=CapabilitySupport(
            True,
            notes=(
                "Orders use /api/v1/orders with X-Tossinvest-Account.",
                "clientOrderId is accepted as a provider-side duplicate prevention key.",
                "Quantity-based LIMIT/MARKET orders are normalized; US amount orders remain provider-specific.",
            ),
        ),
        native=CapabilitySupport(True, notes=("Provider-specific internals remain under kxt.clients.tossinvest.",)),
        notes=("Toss Invest support is REST-only in this slice.",),
    )

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        account_seq: str | int | None = None,
        timeout: float = 10.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._transport = TossInvestTransport(
            client_id=client_id,
            client_secret=client_secret,
            timeout=timeout,
            client=http_client,
        )
        self._market = _TossInvestMarketNamespace(self)
        self._streams = _TossInvestStreamsNamespace()
        self._default_account_seq = _normalize_account_seq(account_seq)
        self._markets_cache: tuple[Market, ...] | None = None

    @property
    def capabilities(self) -> ClientCapabilities:
        return self._CAPABILITIES

    @property
    def market(self) -> MarketNamespace:
        return self._market

    @property
    def streams(self) -> StreamsNamespace:
        return self._streams

    @property
    def native(self) -> "TossInvestClient":
        return self

    async def aclose(self) -> None:
        await self._transport.aclose()

    async def __aenter__(self) -> "TossInvestClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()

    async def fetch_markets(self, *, refresh: bool = False) -> tuple[Market, ...]:
        del refresh
        raise KXTUnsupportedError(
            "Toss Invest stock master requires explicit symbols; use resolve_instrument(symbol) instead"
        )

    async def resolve_instrument(self, symbol: str, *, venue: Venue | None = None) -> InstrumentRef:
        needle = symbol.strip()
        if not needle:
            raise KXTValidationError("symbol must not be empty")
        result = await self._transport.get_result("/api/v1/stocks", params={"symbols": needle})
        markets = parse_markets(result)
        for market in markets:
            instrument = market.instrument
            if instrument.symbol.upper() == needle.upper() and (
                venue is None or instrument.venue == venue
            ):
                return instrument
        return InstrumentRef(symbol=needle, venue=venue)

    async def fetch_quote(self, symbol: str | InstrumentRef, /) -> QuoteSnapshot:
        instrument = self._coerce_instrument(symbol)
        result = await self._transport.get_result(
            "/api/v1/prices",
            params={"symbols": instrument.symbol},
        )
        return parse_quote_snapshot(result, instrument=instrument)

    async def get_quote(self, symbol: str | InstrumentRef | QuoteRequest, /) -> QuoteResponse:
        instrument = symbol.instrument if isinstance(symbol, QuoteRequest) else self._coerce_instrument(symbol)
        snapshot = await self.fetch_quote(instrument)
        return quote_response_from_snapshot(snapshot)

    async def fetch_quotes(
        self,
        symbols: Iterable[str | InstrumentRef] | str | InstrumentRef,
        /,
    ) -> tuple[QuoteSnapshot, ...]:
        instruments = _coerce_instruments(symbols)
        result = await self._transport.get_result(
            "/api/v1/prices",
            params={"symbols": ",".join(instrument.symbol for instrument in instruments)},
        )
        snapshots = parse_quote_snapshots(result)
        by_symbol = {snapshot.symbol.upper(): snapshot for snapshot in snapshots}
        missing = [instrument.symbol for instrument in instruments if instrument.symbol.upper() not in by_symbol]
        if missing:
            raise KXTAPIError(
                f"Toss Invest price response missing symbols: {', '.join(missing)}",
                provider=PROVIDER,
            )
        return tuple(by_symbol[instrument.symbol.upper()] for instrument in instruments)

    async def get_quotes(
        self,
        symbols: Iterable[str | InstrumentRef] | str | InstrumentRef,
        /,
    ) -> QuotesResponse:
        return quotes_response_from_snapshots(await self.fetch_quotes(symbols))

    async def fetch_orderbook(self, symbol: str | InstrumentRef, /) -> OrderBookSnapshot:
        instrument = self._coerce_instrument(symbol)
        result = await self._transport.get_result(
            "/api/v1/orderbook",
            params={"symbol": instrument.symbol},
        )
        return parse_orderbook_snapshot(result, instrument=instrument)

    async def get_orderbook(self, symbol: str | InstrumentRef | OrderBookRequest, /) -> OrderBookResponse:
        instrument = symbol.instrument if isinstance(symbol, OrderBookRequest) else self._coerce_instrument(symbol)
        snapshot = await self.fetch_orderbook(instrument)
        return orderbook_response_from_snapshot(snapshot)

    async def fetch_recent_trades(
        self,
        symbol: str | InstrumentRef,
        /,
        *,
        start: date | datetime | None = None,
        end: date | datetime | None = None,
        limit: int = 100,
    ) -> tuple[Trade, ...]:
        if limit < 1:
            raise KXTValidationError("limit must be >= 1")
        instrument = self._coerce_instrument(symbol)
        result = await self._transport.get_result(
            "/api/v1/trades",
            params={"symbol": instrument.symbol, "count": min(limit, 50)},
        )
        trades = parse_recent_trades(result, instrument=instrument)
        start_dt = coerce_datetime(start, is_end=False)
        end_dt = coerce_datetime(end, is_end=True)
        return tuple(
            trade
            for trade in trades
            if (start_dt is None or trade.occurred_at >= start_dt)
            and (end_dt is None or trade.occurred_at <= end_dt)
        )[:limit]

    async def get_recent_trades(self, symbol: str | InstrumentRef | RecentTradesRequest, /) -> RecentTradesResponse:
        if isinstance(symbol, RecentTradesRequest):
            request = symbol
        else:
            request = RecentTradesRequest(instrument=self._coerce_instrument(symbol))
        trades = await self.fetch_recent_trades(
            request.instrument,
            start=request.start,
            end=request.end,
            limit=request.limit,
        )
        return recent_trades_response_from_trades(trades)

    async def fetch_bars(
        self,
        symbol: str | InstrumentRef,
        /,
        *,
        timeframe: BarTimeframe,
        start: date | datetime | None = None,
        end: date | datetime | None = None,
        interval_minutes: int = 1,
        adjusted: bool = True,
    ) -> tuple[MarketBar, ...]:
        instrument = self._coerce_instrument(symbol)
        if timeframe == BarTimeframe.MINUTE:
            if interval_minutes < 1:
                raise KXTValidationError("interval_minutes must be >= 1")
            bars = await self._fetch_candles(
                instrument,
                interval="1m",
                timeframe=BarTimeframe.MINUTE,
                interval_minutes=1,
                start=start,
                end=end,
                adjusted=adjusted,
            )
            return _aggregate_minute_bars(bars, interval_minutes) if interval_minutes > 1 else bars
        if timeframe == BarTimeframe.DAY:
            return await self._fetch_candles(
                instrument,
                interval="1d",
                timeframe=BarTimeframe.DAY,
                interval_minutes=None,
                start=start,
                end=end,
                adjusted=adjusted,
            )
        raise KXTUnsupportedError("Toss Invest candles currently support minute and day timeframes only")

    async def fetch_intraday_bars(
        self,
        symbol: str | InstrumentRef,
        /,
        *,
        interval_minutes: int = 1,
    ) -> tuple[IntradayBar, ...]:
        bars = await self.fetch_bars(
            symbol,
            timeframe=BarTimeframe.MINUTE,
            interval_minutes=interval_minutes,
        )
        return tuple(
            IntradayBar(
                symbol=bar.symbol,
                opened_at=bar.opened_at,
                interval_minutes=bar.interval_minutes or interval_minutes,
                open=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close,
                volume=bar.volume,
                notional=bar.notional,
            )
            for bar in bars
        )

    async def get_bars(self, symbol: str | InstrumentRef | BarsRequest, /, **kwargs) -> BarsResponse:
        request = _coerce_bars_request(symbol, **kwargs)
        timeframe = request.timeframe_family
        interval_minutes = request.timeframe_interval_minutes
        bars = await self.fetch_bars(
            request.instrument,
            timeframe=timeframe,
            start=request.start,
            end=request.end,
            interval_minutes=interval_minutes,
            adjusted=request.adjusted,
        )
        return bars_response_from_market_bars(
            bars,
            timeframe=str(request.timeframe),
            adjusted=request.adjusted,
            next_before=None,
        )

    async def get_market_status(
        self, symbol: str | InstrumentRef | MarketStatusRequest | None = None
    ) -> MarketStatusResponse:
        del symbol
        result = await self._transport.get_result("/api/v1/market-calendar/KR")
        return parse_market_status(result)

    async def get_accounts(self, request: AccountsRequest | None = None) -> AccountsResponse:
        del request
        result = await self._transport.get_result("/api/v1/accounts")
        return AccountsResponse(accounts=parse_accounts(result))

    async def get_positions(
        self,
        request: PositionsRequest | None = None,
        /,
        *,
        account_seq: str | int | None = None,
        account_no: str | None = None,
        account_product_code: str | None = None,
        account: AccountSummary | None = None,
        **kwargs: Any,
    ) -> PositionsResponse:
        del account_product_code, kwargs
        if isinstance(request, PositionsRequest) and account is None:
            account = request.account
        resolved = self._resolve_account_seq(account=account, account_seq=account_seq, account_no=account_no)
        result = await self._transport.get_result("/api/v1/holdings", account_seq=resolved)
        return parse_positions(result)

    async def get_buying_power(
        self,
        request: BuyingPowerRequest | str | InstrumentRef | None = None,
        /,
        *,
        instrument: str | InstrumentRef | None = None,
        currency: str | None = None,
        account_seq: str | int | None = None,
        account_no: str | None = None,
        account: AccountSummary | None = None,
        **kwargs: Any,
    ) -> BuyingPowerResponse:
        del kwargs
        if isinstance(request, BuyingPowerRequest):
            resolved_instrument = request.instrument
            if account is None:
                account = request.account
        else:
            instrument_value = request if request is not None else instrument
            if instrument_value is None:
                raise KXTValidationError("get_buying_power requires instrument")
            resolved_instrument = self._coerce_instrument(instrument_value)
        resolved = self._resolve_account_seq(account=account, account_seq=account_seq, account_no=account_no)
        currency_code = currency or _currency_for_instrument(resolved_instrument)
        result = await self._transport.get_result(
            "/api/v1/buying-power",
            params={"currency": currency_code},
            account_seq=resolved,
        )
        return parse_buying_power(result)

    async def get_open_orders(
        self,
        request: OpenOrdersRequest | None = None,
        /,
        *,
        instrument: str | InstrumentRef | None = None,
        account_seq: str | int | None = None,
        account_no: str | None = None,
        account_product_code: str | None = None,
        account: AccountSummary | None = None,
        **kwargs: Any,
    ) -> OpenOrdersResponse:
        del account_product_code, kwargs
        if isinstance(request, OpenOrdersRequest):
            if instrument is None and request.instrument is not None:
                instrument = request.instrument
            if account is None:
                account = request.account
        resolved = self._resolve_account_seq(account=account, account_seq=account_seq, account_no=account_no)
        params: dict[str, Any] = {"status": "OPEN"}
        if instrument is not None:
            params["symbol"] = self._coerce_instrument(instrument).symbol
        result = await self._transport.get_result(
            "/api/v1/orders",
            params=params,
            account_seq=resolved,
        )
        return parse_open_orders(result, account_seq=resolved)

    async def get_order_history(
        self,
        request: OrderHistoryRequest | None = None,
        /,
        *,
        start: date | None = None,
        end: date | None = None,
        instrument: str | InstrumentRef | None = None,
        cursor: str | OrderHistoryCursor | None = None,
        limit: int = 100,
        account_seq: str | int | None = None,
        account_no: str | None = None,
        account: AccountSummary | None = None,
        **kwargs: Any,
    ) -> OrderHistoryResponse:
        del kwargs
        if isinstance(request, OrderHistoryRequest):
            start = request.start
            end = request.end
            instrument = request.instrument
            cursor = request.cursor
            if account is None:
                account = request.account
        resolved = self._resolve_account_seq(account=account, account_seq=account_seq, account_no=account_no)
        params: dict[str, Any] = {"status": "CLOSED", "limit": min(max(limit, 1), 100)}
        if start is not None:
            params["from"] = start.isoformat()
        if end is not None:
            params["to"] = end.isoformat()
        if instrument is not None:
            params["symbol"] = self._coerce_instrument(instrument).symbol
        cursor_text = cursor.fk100 if isinstance(cursor, OrderHistoryCursor) else cursor
        if cursor_text:
            params["cursor"] = cursor_text
        result = await self._transport.get_result(
            "/api/v1/orders",
            params=params,
            account_seq=resolved,
        )
        return parse_order_history(result, account_seq=resolved)

    async def submit_order(
        self,
        request: SubmitOrderRequest | OrderInstruction | None = None,
        /,
        *,
        symbol: str | InstrumentRef | None = None,
        instrument: str | InstrumentRef | None = None,
        side: OrderSide | None = None,
        order_type: OrderType | None = None,
        quantity: Decimal | int | float | str | None = None,
        limit_price: Decimal | int | float | str | None = None,
        stop_price: Decimal | None = None,
        time_in_force: str | None = None,
        route_hint=None,
        account_seq: str | int | None = None,
        account_no: str | None = None,
        account: AccountSummary | None = None,
        client_order_id: str | None = None,
        confirm_high_value_order: bool = False,
        order_amount: Decimal | int | float | str | None = None,
        **kwargs: Any,
    ) -> SubmitOrderResponse:
        del route_hint, kwargs
        if stop_price is not None:
            raise KXTUnsupportedError("Toss Invest order creation does not expose stop orders")
        instruction = _coerce_order_instruction(
            request,
            symbol=symbol,
            instrument=instrument,
            side=side,
            order_type=order_type,
            quantity=quantity,
            limit_price=limit_price,
            time_in_force=time_in_force,
            allow_missing_quantity=order_amount is not None,
        )
        if isinstance(request, SubmitOrderRequest) and account is None:
            account = request.account
        resolved = self._resolve_account_seq(account=account, account_seq=account_seq, account_no=account_no)
        body = _order_create_body(
            instruction,
            client_order_id=client_order_id,
            confirm_high_value_order=confirm_high_value_order,
            order_amount=order_amount,
        )
        result = await self._transport.post_result(
            "/api/v1/orders",
            body=body,
            account_seq=resolved,
        )
        ack = parse_order_ack(result, account_seq=resolved, state=OrderLifecycleState.ACKNOWLEDGED)
        return submit_response_from_ack(ack)

    async def cancel_order(
        self,
        request: CancelOrderRequest | ProviderOrderRef | OpenOrder | str | None = None,
        /,
        *,
        order_id: str | None = None,
        order_ref: ProviderOrderRef | None = None,
        account_seq: str | int | None = None,
        account_no: str | None = None,
        account: AccountSummary | None = None,
        **kwargs: Any,
    ) -> CancelOrderResponse:
        del kwargs
        if isinstance(request, CancelOrderRequest):
            order_ref = request.order_ref
            if account is None:
                account = request.account
        elif isinstance(request, OpenOrder):
            order_ref = request.order_ref
        elif isinstance(request, ProviderOrderRef):
            order_ref = request
        elif isinstance(request, str):
            order_id = request
        if order_ref is None:
            if order_id is None:
                raise KXTValidationError("order_id or order_ref is required")
            order_ref = ProviderOrderRef(provider=PROVIDER, order_id=order_id)
        resolved = self._resolve_account_seq(account=account, account_seq=account_seq, account_no=account_no)
        result = await self._transport.post_result(
            f"/api/v1/orders/{order_ref.order_id}/cancel",
            body={},
            account_seq=resolved,
        )
        ack = parse_order_ack(
            result,
            account_seq=resolved,
            state=OrderLifecycleState.CANCELED,
            original_order_id=order_ref.order_id,
        )
        return cancel_response_from_ack(ack)

    async def modify_order(
        self,
        request: ModifyOrderRequest | ProviderOrderRef | OpenOrder | str | None = None,
        /,
        *,
        order_id: str | None = None,
        order_ref: ProviderOrderRef | None = None,
        amendment: OrderAmendment | None = None,
        quantity: Decimal | int | float | str | None = None,
        limit_price: Decimal | int | float | str | None = None,
        stop_price: Decimal | None = None,
        order_type: OrderType | None = None,
        account_seq: str | int | None = None,
        account_no: str | None = None,
        account: AccountSummary | None = None,
        confirm_high_value_order: bool = False,
        **kwargs: Any,
    ) -> ModifyOrderResponse:
        del kwargs
        if stop_price is not None:
            raise KXTUnsupportedError("Toss Invest order modification does not expose stop orders")
        if isinstance(request, ModifyOrderRequest):
            order_ref = request.order_ref
            amendment = request.amendment
            if account is None:
                account = request.account
        elif isinstance(request, OpenOrder):
            order_ref = request.order_ref
        elif isinstance(request, ProviderOrderRef):
            order_ref = request
        elif isinstance(request, str):
            order_id = request
        if order_ref is None:
            if order_id is None:
                raise KXTValidationError("order_id or order_ref is required")
            order_ref = ProviderOrderRef(provider=PROVIDER, order_id=order_id)
        if amendment is not None:
            quantity = amendment.quantity if quantity is None else quantity
            limit_price = amendment.limit_price if limit_price is None else limit_price
            order_type = amendment.order_type if order_type is None else order_type
        resolved = self._resolve_account_seq(account=account, account_seq=account_seq, account_no=account_no)
        body = _order_modify_body(
            order_type=order_type,
            quantity=quantity,
            limit_price=limit_price,
            confirm_high_value_order=confirm_high_value_order,
        )
        result = await self._transport.post_result(
            f"/api/v1/orders/{order_ref.order_id}/modify",
            body=body,
            account_seq=resolved,
        )
        ack = parse_order_ack(
            result,
            account_seq=resolved,
            state=OrderLifecycleState.ACKNOWLEDGED,
            original_order_id=order_ref.order_id,
        )
        return modify_response_from_ack(ack)

    def stream_trades(
        self,
        symbol: str | InstrumentRef | TradeSubscription | TradeStreamRequest,
    ) -> AsyncIterator[TradeEvent]:
        raise KXTUnsupportedError("Toss Invest Open API currently exposes REST endpoints only")

    def stream_orderbook(
        self,
        symbol: str | InstrumentRef | OrderBookSubscription | OrderBookStreamRequest,
    ) -> AsyncIterator[OrderBookEvent]:
        raise KXTUnsupportedError("Toss Invest Open API currently exposes REST endpoints only")

    async def _fetch_candles(
        self,
        instrument: InstrumentRef,
        *,
        interval: str,
        timeframe: BarTimeframe,
        interval_minutes: int | None,
        start: date | datetime | None,
        end: date | datetime | None,
        adjusted: bool,
    ) -> tuple[MarketBar, ...]:
        start_dt = coerce_datetime(start, is_end=False)
        end_dt = coerce_datetime(end, is_end=True)
        if start_dt is not None and end_dt is not None and start_dt > end_dt:
            raise KXTValidationError("start must be <= end")
        before = end_dt.isoformat() if end_dt is not None else None
        collected: dict[datetime, MarketBar] = {}
        while True:
            params: dict[str, Any] = {
                "symbol": instrument.symbol,
                "interval": interval,
                "count": 200,
                "adjusted": str(adjusted).lower(),
            }
            if before:
                params["before"] = before
            result = await self._transport.get_result("/api/v1/candles", params=params)
            bars = parse_market_bars(
                result,
                instrument=instrument,
                timeframe=timeframe,
                interval_minutes=interval_minutes,
            )
            for bar in bars:
                if (start_dt is None or bar.opened_at >= start_dt) and (
                    end_dt is None or bar.opened_at <= end_dt
                ):
                    collected[bar.opened_at] = bar
            result_dict = result if isinstance(result, dict) else {}
            next_before = str(result_dict.get("nextBefore") or "").strip() or None
            if not next_before or not bars:
                break
            if start_dt is None:
                break
            oldest = bars[0].opened_at
            if oldest <= start_dt:
                break
            before = next_before
        return tuple(collected[key] for key in sorted(collected))

    @staticmethod
    def _coerce_instrument(value: str | InstrumentRef) -> InstrumentRef:
        if isinstance(value, InstrumentRef):
            if not value.symbol:
                raise KXTValidationError("instrument.symbol is required")
            return value
        if isinstance(value, str):
            symbol = value.strip()
            if not symbol:
                raise KXTValidationError("symbol must not be empty")
            return InstrumentRef(symbol=symbol)
        raise KXTValidationError(
            f"symbol must be a str or InstrumentRef (got {type(value).__name__})"
        )

    def _resolve_account_seq(
        self,
        *,
        account: AccountSummary | None,
        account_seq: str | int | None,
        account_no: str | None,
    ) -> str:
        resolved = (
            _normalize_account_seq(account_seq)
            or _normalize_account_seq(account_no)
            or (account.account_id if account is not None else None)
            or self._default_account_seq
        )
        if not resolved:
            raise KXTValidationError(
                "Toss Invest account_seq is required for account and order methods"
            )
        return str(resolved)


def _coerce_bars_request(request: BarsRequest | InstrumentRef | str, /, **kwargs: Any) -> BarsRequest:
    if isinstance(request, BarsRequest):
        return request
    if isinstance(request, str):
        request = TossInvestClient._coerce_instrument(request)
    timeframe = kwargs.pop("timeframe", None)
    if timeframe is None:
        raise KXTValidationError("timeframe is required when calling get_bars(...) with a symbol or InstrumentRef")
    interval_minutes = kwargs.pop("interval_minutes", None)
    if interval_minutes is not None:
        if isinstance(timeframe, BarTimeframe) and timeframe != BarTimeframe.MINUTE:
            raise KXTValidationError("interval_minutes can only be used with minute timeframes")
        timeframe = f"{interval_minutes}m"
    return BarsRequest(
        instrument=request,
        timeframe=timeframe,
        start=kwargs.pop("start", None),
        end=kwargs.pop("end", None),
        adjusted=kwargs.pop("adjusted", True),
        session=kwargs.pop("session", None),
    )


def _coerce_instruments(
    values: Iterable[str | InstrumentRef] | str | InstrumentRef,
) -> tuple[InstrumentRef, ...]:
    if isinstance(values, (str, InstrumentRef)):
        instruments = (TossInvestClient._coerce_instrument(values),)
    else:
        instruments = tuple(TossInvestClient._coerce_instrument(value) for value in values)
    if not instruments:
        raise KXTValidationError("at least one symbol is required")
    if len(instruments) > 200:
        raise KXTValidationError("Toss Invest batch quote requests support at most 200 symbols")
    seen: set[str] = set()
    duplicates: list[str] = []
    for instrument in instruments:
        key = instrument.symbol.upper()
        if key in seen:
            duplicates.append(instrument.symbol)
        seen.add(key)
    if duplicates:
        raise KXTValidationError(f"duplicate symbols are not allowed: {', '.join(duplicates)}")
    return instruments


def _coerce_order_instruction(
    request: SubmitOrderRequest | OrderInstruction | None,
    *,
    symbol: str | InstrumentRef | None,
    instrument: str | InstrumentRef | None,
    side: OrderSide | None,
    order_type: OrderType | None,
    quantity: Decimal | int | float | str | None,
    limit_price: Decimal | int | float | str | None,
    time_in_force: str | None,
    allow_missing_quantity: bool = False,
) -> OrderInstruction:
    if isinstance(request, SubmitOrderRequest):
        return request.instruction
    if isinstance(request, OrderInstruction):
        return request
    symbol_or_instrument = symbol if symbol is not None else instrument
    if symbol_or_instrument is None or side is None or order_type is None:
        raise KXTValidationError("submit_order requires symbol, side, order_type, and quantity")
    if quantity is None and not allow_missing_quantity:
        raise KXTValidationError("submit_order requires quantity")
    return OrderInstruction(
        instrument=TossInvestClient._coerce_instrument(symbol_or_instrument),
        side=side,
        order_type=order_type,
        quantity=_decimal(quantity) if quantity is not None else Decimal(0),
        limit_price=None if limit_price is None else _decimal(limit_price),
        time_in_force=time_in_force,
    )


def _order_create_body(
    instruction: OrderInstruction,
    *,
    client_order_id: str | None,
    confirm_high_value_order: bool,
    order_amount: Decimal | int | float | str | None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "symbol": instruction.instrument.symbol,
        "side": instruction.side.value,
        "orderType": instruction.order_type.value,
        "confirmHighValueOrder": bool(confirm_high_value_order),
    }
    if client_order_id:
        body["clientOrderId"] = client_order_id
    if instruction.time_in_force:
        body["timeInForce"] = instruction.time_in_force
    if order_amount is not None:
        body["orderAmount"] = str(_decimal(order_amount))
    else:
        body["quantity"] = str(instruction.quantity)
    if instruction.order_type == OrderType.LIMIT:
        if instruction.limit_price is None:
            raise KXTValidationError("Toss Invest LIMIT orders require limit_price")
        body["price"] = str(instruction.limit_price)
    elif instruction.limit_price is not None:
        raise KXTValidationError("limit_price can only be used with LIMIT orders")
    elif instruction.order_type != OrderType.MARKET:
        raise KXTUnsupportedError("Toss Invest orders currently support LIMIT and MARKET only")
    return body


def _order_modify_body(
    *,
    order_type: OrderType | None,
    quantity: Decimal | int | float | str | None,
    limit_price: Decimal | int | float | str | None,
    confirm_high_value_order: bool,
) -> dict[str, Any]:
    inferred = order_type or (OrderType.LIMIT if limit_price is not None else None)
    if inferred is None:
        raise KXTValidationError("modify_order requires order_type or limit_price")
    if inferred not in (OrderType.LIMIT, OrderType.MARKET):
        raise KXTUnsupportedError("Toss Invest order modification supports LIMIT and MARKET only")
    body: dict[str, Any] = {
        "orderType": inferred.value,
        "confirmHighValueOrder": bool(confirm_high_value_order),
    }
    if quantity is not None:
        body["quantity"] = str(_decimal(quantity))
    if inferred == OrderType.LIMIT:
        if limit_price is None:
            raise KXTValidationError("Toss Invest LIMIT order modification requires limit_price")
        body["price"] = str(_decimal(limit_price))
    elif limit_price is not None:
        raise KXTValidationError("limit_price can only be used with LIMIT order modification")
    return body


def _aggregate_minute_bars(bars: tuple[MarketBar, ...], interval_minutes: int) -> tuple[MarketBar, ...]:
    if interval_minutes <= 1:
        return bars
    aggregated: list[MarketBar] = []
    current: MarketBar | None = None
    current_key: tuple[date, int, int] | None = None
    for bar in bars:
        minute = (bar.opened_at.minute // interval_minutes) * interval_minutes
        opened_at = bar.opened_at.replace(minute=minute, second=0, microsecond=0)
        key = (opened_at.date(), opened_at.hour, opened_at.minute)
        if current is None or key != current_key:
            if current is not None:
                aggregated.append(current)
            current_key = key
            current = MarketBar(
                symbol=bar.symbol,
                opened_at=opened_at,
                timeframe=BarTimeframe.MINUTE,
                interval_minutes=interval_minutes,
                open=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close,
                volume=bar.volume,
                notional=bar.notional,
            )
            continue
        current = MarketBar(
            symbol=current.symbol,
            opened_at=current.opened_at,
            timeframe=current.timeframe,
            interval_minutes=current.interval_minutes,
            open=current.open,
            high=max(current.high, bar.high),
            low=min(current.low, bar.low),
            close=bar.close,
            volume=current.volume + bar.volume,
            notional=bar.notional or current.notional,
        )
    if current is not None:
        aggregated.append(current)
    return tuple(aggregated)


def _currency_for_instrument(instrument: InstrumentRef) -> str:
    if instrument.venue in (Venue.NYSE, Venue.NASDAQ, Venue.AMEX):
        return "USD"
    if not instrument.symbol.isdigit():
        return "USD"
    return "KRW"


def _normalize_account_seq(value: str | int | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _decimal(value: Decimal | int | float | str) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


__all__ = ["TossInvestClient"]
