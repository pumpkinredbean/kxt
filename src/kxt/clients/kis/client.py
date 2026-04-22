"""Concrete async KIS client for the current legacy first usable slice."""

from __future__ import annotations

import json
from contextlib import suppress
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from kxt.clients.base import MarketDataClient, MarketNamespace, StreamsNamespace
from kxt.clients.capabilities import (
    CapabilitySupport,
    ClientCapabilities,
    IntradayBarsCapability,
    MarketCapabilities,
    StreamCapabilities,
    TradeStreamCapability,
)
from kxt.errors import KXTValidationError
from kxt.models import (
    AccountEquitySnapshot,
    AccountOverviewCursor,
    AccountOverviewRequest,
    AccountOverviewResponse,
    AccountsRequest,
    AccountsResponse,
    AccountSummary,
    BalanceRequest,
    BalanceResponse,
    BalanceSnapshot,
    BarCursor,
    BarTimeframe,
    BarsRequest,
    BarsResponse,
    BuyingPowerRequest,
    BuyingPowerResponse,
    BuyingPowerSnapshot,
    CancelOrderRequest,
    CancelOrderResponse,
    ExecutionReport,
    FillEvent,
    FillNotificationEvent,
    FillUpdatesStreamRequest,
    InstrumentRef,
    IntradayBar,
    InvestorFlowRequest,
    InvestorFlowResponse,
    MarketBar,
    MarketSegment,
    MarketScope,
    MarketStatusEvent,
    MarketStatusRequest,
    MarketStatusResponse,
    MarketStatusStreamRequest,
    MemberFlowRequest,
    MemberFlowResponse,
    ModifyOrderRequest,
    ModifyOrderResponse,
    OpenOrder,
    OrderAmendment,
    OrderInstruction,
    OrderRouteHint,
    OpenOrdersRequest,
    OpenOrdersResponse,
    OrderAcceptedEvent,
    OrderAcknowledgement,
    OrderAmendAckEvent,
    OrderBookRequest,
    OrderBookEvent,
    OrderBookResponse,
    OrderBookSnapshot,
    OrderBookStreamRequest,
    OrderCancelAckEvent,
    OrderCorrelationKey,
    OrderEventsStreamRequest,
    OrderHistoryCursor,
    OrderHistoryRequest,
    OrderHistoryResponse,
    OrderLifecycleState,
    OrderRejectedEvent,
    OrderSide,
    OrderType,
    OrderUpdateEvent,
    OrderUpdatesStreamRequest,
    Position,
    PositionsRequest,
    PositionsResponse,
    ProgramTradeRequest,
    ProgramTradeResponse,
    ProviderOrderRef,
    ProviderRef,
    QuoteRequest,
    QuoteResponse,
    QuoteSnapshot,
    RankingsRequest,
    RankingsResponse,
    RecentTradesRequest,
    RecentTradesResponse,
    Bar,
    SessionType,
    SubmitOrderRequest,
    SubmitOrderResponse,
    Trade,
    TradeEvent,
    TradePrint,
    TradeStreamRequest,
    Venue,
)
from kxt.streams.subscriptions import OrderBookSubscription, TradeSubscription

from kxt.errors import KXTUnsupportedError
from .parsing import (
    KIS_BALANCE_PATH,
    KIS_BALANCE_TR_ID,
    KIS_BUYING_POWER_PATH,
    KIS_BUYING_POWER_TR_ID,
    KIS_CURRENT_MINUTE_PATH,
    KIS_CURRENT_MINUTE_TR_ID,
    KIS_HISTORICAL_MINUTE_PATH,
    KIS_HISTORICAL_MINUTE_TR_ID,
    KIS_INVESTOR_FLOW_PATH,
    KIS_INVESTOR_FLOW_TR_ID,
    KIS_OPEN_ORDERS_PATH,
    KIS_OPEN_ORDERS_TR_ID,
    KIS_ORDER_CASH_BUY_TR_ID,
    KIS_ORDER_CASH_PATH,
    KIS_ORDER_CASH_SELL_TR_ID,
    KIS_ORDER_HISTORY_PATH,
    KIS_ORDER_HISTORY_TR_ID,
    KIS_ORDER_RVSECNCL_PATH,
    KIS_ORDER_RVSECNCL_TR_ID,
    KIS_ORDERBOOK_PATH,
    KIS_ORDERBOOK_TR_ID,
    KIS_ORDERBOOK_WS_TR_ID,
    KIS_PERIOD_BARS_PATH,
    KIS_PERIOD_BARS_TR_ID,
    KIS_QUOTE_PATH,
    KIS_QUOTE_TR_ID,
    KIS_RECENT_TRADES_PATH,
    KIS_RECENT_TRADES_TR_ID,
    _kis_code_to_order_type,
    _order_type_to_kis_code,
    notification_subscription_message,
    parse_account_overview,
    parse_buying_power,
    parse_market_bars,
    parse_market_status,
    parse_investor_flow,
    parse_notification_event,
    parse_open_orders,
    parse_order_ack,
    parse_order_history,
    parse_orderbook_event,
    parse_orderbook_snapshot,
    parse_quote_snapshot,
    parse_recent_trades,
    parse_trade_event,
    websocket_subscription_message,
)
from .realtime import KISRealtimeSession, StreamKind
from .transport import KISTransport, map_websocket_exception
from .markets import KRXInstrumentMaster


class _KISMarketNamespace(MarketNamespace):
    """Legacy grouped market-data compatibility namespace for v0.1.0."""

    def __init__(self, client: KISClient) -> None:
        self._client = client

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
        /,
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
        /,
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


class _KISStreamsNamespace(StreamsNamespace):
    """Legacy grouped streaming compatibility namespace for v0.1.0."""

    def __init__(self, client: KISClient) -> None:
        self._client = client

    def stream_trades(self, symbol: str | InstrumentRef | TradeSubscription | TradeStreamRequest) -> AsyncIterator[TradeEvent]:
        return self._client.stream_trades(symbol)


class KISClient(MarketDataClient):
    """Async KIS client for domestic equity K-line bars and live trades."""

    client_id = "kis"
    _CAPABILITIES = ClientCapabilities(
        provider="kis",
        requires_credentials=True,
        supported_venues=(Venue.KRX,),
        supported_scopes=(MarketScope.KRX, MarketScope.TOTAL),
        market=MarketCapabilities(
            bars=CapabilitySupport(
                True,
                notes=(
                    "Domestic equity K-line bars only.",
                    "Day/week/month/year bars use the KIS period chart endpoint and inherit its per-call row limits.",
                ),
            ),
            intraday_bars=IntradayBarsCapability(
                supported=True,
                supports_custom_intervals=True,
                supported_venues=(Venue.KRX,),
                notes=(
                    "Domestic equity K-line bars only.",
                    "Minute bars use KIS current-day or daily-intraday chart endpoints depending on the requested range.",
                    "Intervals above one minute are aggregated locally from KIS minute rows.",
                ),
            ),
            quote=CapabilitySupport(
                True,
                notes=(
                    "Lean quote snapshots are backed by the KIS current-price endpoint.",
                    "Use get_orderbook(...) for top-of-book and depth data.",
                ),
            ),
            recent_trades=CapabilitySupport(
                True,
                notes=(
                    "Recent trade history is backed by KIS inquire-time-itemconclusion.",
                    "Current implementation is limited to domestic equity same-day prints addressed by time cursor.",
                ),
            ),
            order_book=CapabilitySupport(
                True,
                notes=(
                    "Snapshot order book depth is backed by the KIS asking-price endpoint.",
                ),
            ),
            market_status=CapabilitySupport(
                True,
                notes=(
                    "Market status is derived from KIS quote payload state fields when present.",
                    "Current implementation is limited to the same domestic-equity quote slice as get_quote(...).",
                ),
            ),
            investor_flow=CapabilitySupport(
                True,
                notes=(
                    "Domestic equity per-instrument investor flow is backed by the KIS inquire-investor endpoint.",
                    "Current implementation is limited to same-day regular-session aggregates that KIS publishes after the cash session closes.",
                    "Historical/ranged investor-flow fetches are not yet normalized in kxt.",
                ),
            ),
        ),
        streams=StreamCapabilities(
            trades=TradeStreamCapability(
                supported=True,
                requires_instrument=True,
                supports_scope_subscription=False,
                supported_venues=(Venue.KRX,),
                notes=(
                    "Domestic equity live trade prints only.",
                    "Scope-wide subscriptions are not supported in v0.1.0.",
                ),
            ),
            order_book=CapabilitySupport(
                True,
                notes=(
                    "Per-instrument live order book streaming is supported.",
                ),
            ),
            program_trades=CapabilitySupport(False, "Program-trade APIs are not in scope for v0.1.0."),
            market_status=CapabilitySupport(False, "KIS market-status streaming is not yet implemented."),
            order_updates=CapabilitySupport(
                True,
                notes=(
                    "Unified realtime order + fill notification stream via H0STCNI0.",
                    "Subscription requires an HTS user id (tr_key).",
                    "stream_order_events(...) yields OrderLifecycleEvent | FillNotificationEvent.",
                ),
            ),
            fill_updates=CapabilitySupport(
                True,
                notes=(
                    "Fill events are delivered through the same H0STCNI0 channel as order events.",
                    "Use stream_fill_updates(...) for a filtered iterator over CNTG_YN=2 messages.",
                ),
            ),
        ),
        trading=CapabilitySupport(
            True,
            notes=(
                "Domestic equity cash orders via order-cash (TTTC0802U/TTTC0801U).",
                "Order modification and cancellation via order-rvsecncl (TTTC0803U).",
                "Balance/positions via inquire-balance (TTTC8434R), buying power via inquire-psbl-order (TTTC8908R).",
                "Open orders via inquire-psbl-rvsecncl (TTTC8036R); order history via inquire-daily-ccld (TTTC8001R) within 3 months.",
                "get_accounts(...) is unsupported: KIS does not expose a public account-list/discovery API. "
                "Account identity must be supplied via account_no/account_product_code on the client or "
                "AccountSummary on each request.",
            ),
        ),
        native=CapabilitySupport(True, notes=("Provider-specific internals remain under kxt.clients.kis.",)),
        notes=("KIS is the only provider implemented in v0.1.0.",),
    )

    def __init__(
        self,
        *,
        app_key: str,
        app_secret: str,
        sandbox: bool = False,
        account_no: str | None = None,
        account_product_code: str | None = None,
        hts_id: str | None = None,
    ) -> None:
        if sandbox:
            raise KXTUnsupportedError("KIS sandbox support is not yet wired for this first slice")
        self._transport = KISTransport(app_key=app_key, app_secret=app_secret)
        self._market = _KISMarketNamespace(self)
        self._streams = _KISStreamsNamespace(self)
        self._default_account_no = (account_no or "").strip() or None
        self._default_account_product_code = (account_product_code or "").strip() or None
        self._default_hts_id = (hts_id or "").strip() or None
        self._realtime: KISRealtimeSession | None = None
        self._instrument_master: KRXInstrumentMaster | None = None

    @property
    def capabilities(self) -> ClientCapabilities:
        return self._CAPABILITIES

    @property
    def market(self) -> MarketNamespace:
        return self._market

    @property
    def native(self) -> KISClient:
        return self

    @property
    def streams(self) -> StreamsNamespace:
        return self._streams

    @property
    def realtime(self) -> KISRealtimeSession:
        """Lazily-constructed multiplexed realtime session (Phase 2)."""
        if self._realtime is None:
            self._realtime = KISRealtimeSession(self._transport)
        return self._realtime

    async def aclose(self) -> None:
        if self._realtime is not None:
            with suppress(Exception):
                await self._realtime.aclose()
        await self._transport.aclose()

    async def __aenter__(self) -> KISClient:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()

    def _get_instrument_master(self) -> KRXInstrumentMaster:
        if self._instrument_master is None:
            self._instrument_master = KRXInstrumentMaster(
                http_client=self._transport._client
            )
        return self._instrument_master

    async def fetch_markets(self, *, refresh: bool = False):
        return await self._get_instrument_master().fetch_markets(refresh=refresh)

    async def resolve_instrument(self, symbol: str, *, venue=None):
        return await self._get_instrument_master().resolve_instrument(
            symbol, venue=venue
        )

    async def fetch_intraday_bars(
        self,
        symbol: str | InstrumentRef,
        /,
        *,
        interval_minutes: int = 1,
    ) -> tuple[IntradayBar, ...]:
        """Compatibility wrapper for the current legacy surface."""

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

    async def fetch_quote(self, symbol: str | InstrumentRef, /) -> QuoteSnapshot:
        instrument = self._coerce_instrument(symbol)
        instrument = self._normalize_instrument(instrument)
        payload = await self._transport.get_json(
            KIS_QUOTE_PATH,
            tr_id=KIS_QUOTE_TR_ID,
            params={
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": instrument.symbol,
            },
        )
        return parse_quote_snapshot(payload, instrument=instrument)

    async def get_quote(self, symbol: str | InstrumentRef | QuoteRequest, /) -> QuoteResponse:
        instrument = (
            symbol.instrument if isinstance(symbol, QuoteRequest) else self._coerce_instrument(symbol)
        )
        snapshot = await self.fetch_quote(instrument)
        return _quote_response_from_snapshot(snapshot)

    async def fetch_orderbook(self, symbol: str | InstrumentRef, /) -> OrderBookSnapshot:
        instrument = self._coerce_instrument(symbol)
        instrument = self._normalize_instrument(instrument)
        payload = await self._transport.get_json(
            KIS_ORDERBOOK_PATH,
            tr_id=KIS_ORDERBOOK_TR_ID,
            params={
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": instrument.symbol,
            },
        )
        return parse_orderbook_snapshot(payload, instrument=instrument)

    async def get_orderbook(self, symbol: str | InstrumentRef | OrderBookRequest, /) -> OrderBookResponse:
        instrument = (
            symbol.instrument if isinstance(symbol, OrderBookRequest) else self._coerce_instrument(symbol)
        )
        snapshot = await self.fetch_orderbook(instrument)
        return _orderbook_response_from_snapshot(snapshot)

    async def fetch_recent_trades(
        self,
        symbol: str | InstrumentRef,
        /,
        *,
        start: date | datetime | None = None,
        end: date | datetime | None = None,
        limit: int = 100,
    ) -> tuple[Trade, ...]:
        instrument = self._coerce_instrument(symbol)
        instrument = self._normalize_instrument(instrument)
        if limit < 1:
            raise KXTValidationError("limit must be >= 1")

        start_dt = _coerce_datetime(start, is_end=False)
        end_dt = _coerce_datetime(end, is_end=True)
        if start_dt is not None and end_dt is not None and start_dt > end_dt:
            raise KXTValidationError("start must be <= end")

        today = datetime.now(UTC).date()
        for bound_name, bound in (("start", start_dt), ("end", end_dt)):
            if bound is not None and bound.date() != today:
                raise KXTUnsupportedError(
                    f"KIS recent trade history currently supports same-day domestic equity prints only; {bound_name} must be today"
                )

        return await self._fetch_recent_trades_today(
            instrument,
            start_dt=start_dt,
            end_dt=end_dt,
            limit=limit,
        )

    async def get_recent_trades(self, symbol: str | InstrumentRef | RecentTradesRequest, /) -> RecentTradesResponse:
        if isinstance(symbol, RecentTradesRequest):
            normalized_request = symbol
        else:
            normalized_request = RecentTradesRequest(instrument=self._coerce_instrument(symbol))
        trades = await self.fetch_recent_trades(
            normalized_request.instrument,
            start=normalized_request.start,
            end=normalized_request.end,
            limit=normalized_request.limit,
        )
        return RecentTradesResponse(
            trades=tuple(_trade_print_from_trade(trade) for trade in trades),
        )

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
        """Compatibility wrapper for the current legacy surface."""

        instrument = self._coerce_instrument(symbol)
        instrument = self._normalize_instrument(instrument)
        if timeframe == BarTimeframe.MINUTE:
            return await self._fetch_minute_bars(
                instrument,
                start=start,
                end=end,
                interval_minutes=interval_minutes,
            )
        return await self._fetch_period_bars(
            instrument,
            timeframe=timeframe,
            start=start,
            end=end,
            adjusted=adjusted,
        )

    async def get_bars(self, symbol: str | InstrumentRef | BarsRequest, /, **kwargs) -> BarsResponse:
        normalized_request = _coerce_bars_request(symbol, **kwargs)
        timeframe = normalized_request.timeframe_family
        interval_minutes = normalized_request.timeframe_interval_minutes
        bars = await self.fetch_bars(
            normalized_request.instrument,
            timeframe=timeframe,
            start=normalized_request.start,
            end=normalized_request.end,
            interval_minutes=interval_minutes,
            adjusted=normalized_request.adjusted,
        )
        cursor = None if not bars else {"next_opened_at": bars[-1].opened_at}
        return BarsResponse(
            timeframe=normalized_request.timeframe,
            adjusted=normalized_request.adjusted,
            bars=tuple(_bar_from_market_bar(bar, timeframe=normalized_request.timeframe) for bar in bars),
            cursor=None if cursor is None else BarCursor(**cursor),
        )

    async def get_market_status(self, symbol: str | InstrumentRef | MarketStatusRequest | None = None, /) -> MarketStatusResponse:
        if isinstance(symbol, MarketStatusRequest):
            instrument_ref = symbol.instrument or InstrumentRef(symbol="005930")
        elif symbol is None:
            instrument_ref = InstrumentRef(symbol="005930")
        else:
            instrument_ref = self._coerce_instrument(symbol)
        instrument = self._normalize_instrument(instrument_ref)
        payload = await self._transport.get_json(
            KIS_QUOTE_PATH,
            tr_id=KIS_QUOTE_TR_ID,
            params={
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": instrument.symbol,
            },
        )
        response = parse_market_status(payload, instrument=instrument)
        return response

    async def get_investor_flow(self, symbol: str | InstrumentRef | InvestorFlowRequest, /) -> InvestorFlowResponse:
        if isinstance(symbol, InvestorFlowRequest):
            normalized_request = symbol
        else:
            normalized_request = InvestorFlowRequest(instrument=self._coerce_instrument(symbol))
        if normalized_request.start is not None or normalized_request.end is not None:
            raise KXTUnsupportedError("KIS investor-flow fetch currently supports the provider's current-session aggregate only; start/end filters are not available")
        if normalized_request.session not in (None, SessionType.REGULAR):
            raise KXTUnsupportedError("KIS investor-flow fetch currently supports domestic-equity regular-session aggregates only")

        instrument = self._normalize_instrument(normalized_request.instrument)
        payload = await self._transport.get_json(
            KIS_INVESTOR_FLOW_PATH,
            tr_id=KIS_INVESTOR_FLOW_TR_ID,
            params={
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": instrument.symbol,
            },
        )
        return parse_investor_flow(payload, instrument=instrument)

    async def get_program_trade(self, request: ProgramTradeRequest) -> ProgramTradeResponse:
        raise KXTUnsupportedError("KIS program-trade fetch is not yet implemented in kxt")

    async def get_rankings(self, request: RankingsRequest) -> RankingsResponse:
        raise KXTUnsupportedError("KIS rankings fetch is not yet implemented in kxt")

    async def get_member_flow(self, request: MemberFlowRequest) -> MemberFlowResponse:
        raise KXTUnsupportedError("KIS member-flow fetch is not yet implemented in kxt")

    async def get_accounts(self, request: AccountsRequest | None = None) -> AccountsResponse:
        raise KXTUnsupportedError(
            "KIS does not expose a public account-list/account-discovery API; "
            "account identity must be supplied locally via account_no/account_product_code "
            "on KISClient(...) or AccountSummary(...) on each request. "
            "Echoing back the locally-configured account would not reflect a real broker fetch, "
            "so get_accounts(...) is intentionally unsupported for the KIS provider."
        )

    async def get_balance(
        self,
        request: BalanceRequest | None = None,
        /,
        *,
        account_no: str | None = None,
        account_product_code: str | None = None,
        account: AccountSummary | None = None,
        instrument: str | InstrumentRef | None = None,
        session: SessionType | None = None,
    ) -> BalanceResponse:
        if isinstance(request, BalanceRequest):
            if account is None:
                account = request.account
            if instrument is None:
                instrument = request.instrument
            if session is None:
                session = request.session
        resolved = self._resolve_account(account, account_no, account_product_code)
        overview = await self.get_account_overview(account=resolved)
        eq = overview.equity
        snapshot = BalanceSnapshot(
            account=eq.account,
            as_of=eq.as_of,
            cash=eq.cash,
            buying_power=None,
            margin_available=None,
            net_liquidation_value=eq.net_asset_value,
        )
        return BalanceResponse(snapshot=snapshot)

    async def get_account_overview(
        self,
        request: AccountOverviewRequest | None = None,
        /,
        *,
        account_no: str | None = None,
        account_product_code: str | None = None,
        account: AccountSummary | None = None,
        include_afterhours: bool = False,
        include_fund_settlement: bool = True,
        cursor: AccountOverviewCursor | None = None,
    ) -> AccountOverviewResponse:
        if isinstance(request, AccountOverviewRequest):
            if account is None:
                account = request.account
            include_afterhours = request.include_afterhours
            include_fund_settlement = request.include_fund_settlement
            if cursor is None:
                cursor = request.cursor
        resolved = self._resolve_account(account, account_no, account_product_code)
        params = self._account_params(resolved)
        params.update(
            {
                "AFHR_FLPR_YN": "Y" if include_afterhours else "N",
                "OFL_YN": "",
                "INQR_DVSN": "02",
                "UNPR_DVSN": "01",
                "FUND_STTL_ICLD_YN": "Y" if include_fund_settlement else "N",
                "FNCG_AMT_AUTO_RDPT_YN": "N",
                "PRCS_DVSN": "01",
                "CTX_AREA_FK100": (cursor.fk100 if cursor else "") or "",
                "CTX_AREA_NK100": (cursor.nk100 if cursor else "") or "",
            }
        )
        payload = await self._transport.get_json(
            KIS_BALANCE_PATH,
            tr_id=KIS_BALANCE_TR_ID,
            params=params,
        )
        positions, equity, (fk100, nk100) = parse_account_overview(payload, account=resolved)
        next_cursor = AccountOverviewCursor(fk100=fk100, nk100=nk100) if (fk100 or nk100) else None
        return AccountOverviewResponse(
            equity=equity,
            positions=positions,
            cursor=next_cursor,
        )

    async def get_positions(
        self,
        request: PositionsRequest | None = None,
        /,
        *,
        account_no: str | None = None,
        account_product_code: str | None = None,
        account: AccountSummary | None = None,
        session: SessionType | None = None,
    ) -> PositionsResponse:
        if isinstance(request, PositionsRequest):
            if account is None:
                account = request.account
            if session is None:
                session = request.session
        resolved = self._resolve_account(account, account_no, account_product_code)
        overview = await self.get_account_overview(account=resolved)
        positions = tuple(
            Position(
                symbol=lot.symbol,
                quantity=lot.quantity,
                average_price=lot.average_price,
                market_price=lot.market_price,
                unrealized_pnl=lot.unrealized_pnl,
                side=None,
            )
            for lot in overview.positions
        )
        return PositionsResponse(positions=positions)

    async def get_buying_power(
        self,
        request: BuyingPowerRequest | None = None,
        /,
        *,
        instrument: str | InstrumentRef | None = None,
        price: Decimal | int | float | str | None = None,
        order_type: OrderType = OrderType.LIMIT,
        include_cma: bool = False,
        account_no: str | None = None,
        account_product_code: str | None = None,
        account: AccountSummary | None = None,
    ) -> BuyingPowerResponse:
        if isinstance(request, BuyingPowerRequest):
            if instrument is None:
                instrument = request.instrument
            if price is None:
                price = request.price
            order_type = request.order_type
            include_cma = request.include_cma
            if account is None:
                account = request.account
        if instrument is None:
            raise KXTValidationError("instrument is required")
        resolved = self._resolve_account(account, account_no, account_product_code)
        normalized_instrument = self._normalize_instrument(self._coerce_instrument(instrument))
        price_text = "0" if price is None else str(price)
        params = self._account_params(resolved)
        params.update(
            {
                "PDNO": normalized_instrument.symbol,
                "ORD_UNPR": price_text,
                "ORD_DVSN": _order_type_to_kis_code(order_type),
                "CMA_EVLU_AMT_ICLD_YN": "Y" if include_cma else "N",
                "OVRS_ICLD_YN": "N",
            }
        )
        payload = await self._transport.get_json(
            KIS_BUYING_POWER_PATH,
            tr_id=KIS_BUYING_POWER_TR_ID,
            params=params,
        )
        snapshot = parse_buying_power(payload)
        return BuyingPowerResponse(snapshot=snapshot)

    async def get_open_orders(
        self,
        request: OpenOrdersRequest | None = None,
        /,
        *,
        account_no: str | None = None,
        account_product_code: str | None = None,
        account: AccountSummary | None = None,
        instrument: str | InstrumentRef | None = None,
        session: SessionType | None = None,
    ) -> OpenOrdersResponse:
        if isinstance(request, OpenOrdersRequest):
            if account is None:
                account = request.account
            if instrument is None:
                instrument = request.instrument
            if session is None:
                session = request.session
        resolved = self._resolve_account(account, account_no, account_product_code)
        instrument_ref = self._resolve_instrument_opt(instrument)
        params = self._account_params(resolved)
        params.update(
            {
                "CTX_AREA_FK100": "",
                "CTX_AREA_NK100": "",
                "INQR_DVSN_1": "0",
                "INQR_DVSN_2": "0",
            }
        )
        payload = await self._transport.get_json(
            KIS_OPEN_ORDERS_PATH,
            tr_id=KIS_OPEN_ORDERS_TR_ID,
            params=params,
        )
        orders = parse_open_orders(payload, account_id=resolved.account_id)
        if instrument_ref is not None:
            sym = instrument_ref.symbol
            orders = tuple(order for order in orders if order.symbol == sym)
        return OpenOrdersResponse(orders=orders)

    async def get_order_history(
        self,
        request: OrderHistoryRequest | None = None,
        /,
        *,
        start: date | None = None,
        end: date | None = None,
        instrument: str | InstrumentRef | None = None,
        side_filter: OrderSide | None = None,
        fill_filter: str = "all",
        cursor: AccountOverviewCursor | None = None,
        account_no: str | None = None,
        account_product_code: str | None = None,
        account: AccountSummary | None = None,
    ) -> OrderHistoryResponse:
        if isinstance(request, OrderHistoryRequest):
            start = request.start
            end = request.end
            if instrument is None:
                instrument = request.instrument
            if side_filter is None:
                side_filter = request.side_filter
            fill_filter = request.fill_filter
            if cursor is None:
                cursor = request.cursor
            if account is None:
                account = request.account
        if start is None or end is None:
            raise KXTValidationError("start and end are required")
        resolved = self._resolve_account(account, account_no, account_product_code)
        instrument_ref = self._resolve_instrument_opt(instrument)
        params = self._account_params(resolved)
        side_code = {OrderSide.BUY: "02", OrderSide.SELL: "01"}.get(side_filter, "00")
        fill_code = {"all": "00", "filled": "01", "unfilled": "02"}.get(fill_filter, "00")
        params.update(
            {
                "INQR_STRT_DT": start.strftime("%Y%m%d"),
                "INQR_END_DT": end.strftime("%Y%m%d"),
                "SLL_BUY_DVSN_CD": side_code,
                "INQR_DVSN": "00",
                "PDNO": instrument_ref.symbol if instrument_ref else "",
                "CCLD_DVSN": fill_code,
                "ORD_GNO_BRNO": "",
                "ODNO": "",
                "INQR_DVSN_3": "00",
                "INQR_DVSN_1": "",
                "CTX_AREA_FK100": (cursor.fk100 if cursor else "") or "",
                "CTX_AREA_NK100": (cursor.nk100 if cursor else "") or "",
            }
        )
        payload = await self._transport.get_json(
            KIS_ORDER_HISTORY_PATH,
            tr_id=KIS_ORDER_HISTORY_TR_ID,
            params=params,
        )
        records, summary, (fk100, nk100) = parse_order_history(
            payload, account_id=resolved.account_id
        )
        next_cursor = OrderHistoryCursor(fk100=fk100, nk100=nk100) if (fk100 or nk100) else None
        return OrderHistoryResponse(
            records=records,
            summary=summary,
            cursor=next_cursor,
        )

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
        route_hint: OrderRouteHint | None = None,
        account_no: str | None = None,
        account_product_code: str | None = None,
        account: AccountSummary | None = None,
    ) -> SubmitOrderResponse:
        instruction: OrderInstruction | None = None
        if isinstance(request, SubmitOrderRequest):
            instruction = request.instruction
            if account is None:
                account = request.account
        elif isinstance(request, OrderInstruction):
            instruction = request
        if instruction is None:
            symbol_or_instrument = symbol if symbol is not None else instrument
            if symbol_or_instrument is None or side is None or order_type is None or quantity is None:
                raise KXTValidationError(
                    "submit_order requires symbol, side, order_type, and quantity"
                )
            instrument_ref = self._coerce_instrument(symbol_or_instrument)
            instruction = OrderInstruction(
                instrument=instrument_ref,
                side=side,
                order_type=order_type,
                quantity=Decimal(str(quantity)) if not isinstance(quantity, Decimal) else quantity,
                limit_price=(
                    None if limit_price is None
                    else (limit_price if isinstance(limit_price, Decimal) else Decimal(str(limit_price)))
                ),
                stop_price=stop_price,
                time_in_force=time_in_force,
                route_hint=route_hint,
            )

        resolved = self._resolve_account(account, account_no, account_product_code)
        normalized_instrument = self._normalize_instrument(instruction.instrument)
        tr_id = (
            KIS_ORDER_CASH_BUY_TR_ID
            if instruction.side == OrderSide.BUY
            else KIS_ORDER_CASH_SELL_TR_ID
        )
        if instruction.order_type == OrderType.MARKET:
            price_text = "0"
        elif instruction.limit_price is None:
            raise KXTUnsupportedError("KIS limit orders require limit_price")
        else:
            price_text = str(instruction.limit_price)
        body = {
            "CANO": resolved.account_id,
            "ACNT_PRDT_CD": resolved.product_code or "",
            "PDNO": normalized_instrument.symbol,
            "ORD_DVSN": _order_type_to_kis_code(instruction.order_type),
            "ORD_QTY": str(instruction.quantity),
            "ORD_UNPR": price_text,
        }
        payload = await self._transport.post_json(
            KIS_ORDER_CASH_PATH,
            tr_id=tr_id,
            body=body,
        )
        order_ref, correlation, occurred_at = parse_order_ack(
            payload, account_id=resolved.account_id
        )
        ack = OrderAcknowledgement(
            order_ref=order_ref,
            state=OrderLifecycleState.ACKNOWLEDGED,
            occurred_at=occurred_at,
            message=None,
        )
        return SubmitOrderResponse(acknowledgement=ack)

    async def cancel_order(
        self,
        request: CancelOrderRequest | ProviderOrderRef | OpenOrder | str | None = None,
        /,
        *,
        order_id: str | None = None,
        order_ref: ProviderOrderRef | None = None,
        quantity: Decimal | int | float | str | None = None,
        cancel_all: bool = True,
        correlation_key: OrderCorrelationKey | None = None,
        origin_org_no: str | None = None,
        branch_no: str | None = None,
        account_no: str | None = None,
        account_product_code: str | None = None,
        account: AccountSummary | None = None,
    ) -> CancelOrderResponse:
        if isinstance(request, CancelOrderRequest):
            order_ref = request.order_ref
            if quantity is None:
                quantity = request.quantity
            cancel_all = request.cancel_all
            if correlation_key is None:
                correlation_key = request.correlation_key
            if account is None:
                account = request.account
        elif isinstance(request, OpenOrder):
            order_ref = request.order_ref
            if correlation_key is None:
                correlation_key = request.correlation_key
        elif isinstance(request, ProviderOrderRef):
            order_ref = request
        elif isinstance(request, str):
            order_id = request

        if order_ref is None:
            if order_id is None:
                raise KXTValidationError("order_id or order_ref is required")
            order_ref = ProviderOrderRef(provider="kis", order_id=order_id)

        if correlation_key is None and (origin_org_no is not None or branch_no is not None):
            correlation_key = OrderCorrelationKey(
                order_ref=order_ref,
                origin_org_no=origin_org_no,
                branch_no=branch_no,
            )

        resolved = self._resolve_account(account, account_no, account_product_code)
        qty_dec = (
            None if quantity is None
            else (quantity if isinstance(quantity, Decimal) else Decimal(str(quantity)))
        )
        body = self._rvsecncl_body(
            account=resolved,
            order_ref=order_ref,
            correlation_key=correlation_key,
            dvsn_code="02",
            order_type=None,
            quantity=qty_dec,
            limit_price=None,
            cancel_all=cancel_all,
        )
        payload = await self._transport.post_json(
            KIS_ORDER_RVSECNCL_PATH,
            tr_id=KIS_ORDER_RVSECNCL_TR_ID,
            body=body,
        )
        new_ref, _, occurred_at = parse_order_ack(
            payload,
            account_id=resolved.account_id,
            original_order_id=order_ref.order_id,
        )
        ack = OrderAcknowledgement(
            order_ref=new_ref,
            state=OrderLifecycleState.CANCELED,
            occurred_at=occurred_at,
            message=None,
        )
        return CancelOrderResponse(acknowledgement=ack)

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
        correlation_key: OrderCorrelationKey | None = None,
        origin_org_no: str | None = None,
        branch_no: str | None = None,
        account_no: str | None = None,
        account_product_code: str | None = None,
        account: AccountSummary | None = None,
    ) -> ModifyOrderResponse:
        if isinstance(request, ModifyOrderRequest):
            order_ref = request.order_ref
            if amendment is None:
                amendment = request.amendment
            if correlation_key is None:
                correlation_key = request.correlation_key
            if account is None:
                account = request.account
        elif isinstance(request, OpenOrder):
            order_ref = request.order_ref
            if correlation_key is None:
                correlation_key = request.correlation_key
        elif isinstance(request, ProviderOrderRef):
            order_ref = request
        elif isinstance(request, str):
            order_id = request

        if order_ref is None:
            if order_id is None:
                raise KXTValidationError("order_id or order_ref is required")
            order_ref = ProviderOrderRef(provider="kis", order_id=order_id)

        if amendment is None:
            amendment = OrderAmendment(
                quantity=(
                    None if quantity is None
                    else (quantity if isinstance(quantity, Decimal) else Decimal(str(quantity)))
                ),
                limit_price=(
                    None if limit_price is None
                    else (limit_price if isinstance(limit_price, Decimal) else Decimal(str(limit_price)))
                ),
                stop_price=stop_price,
                order_type=order_type,
            )

        if correlation_key is None and (origin_org_no is not None or branch_no is not None):
            correlation_key = OrderCorrelationKey(
                order_ref=order_ref,
                origin_org_no=origin_org_no,
                branch_no=branch_no,
            )

        resolved = self._resolve_account(account, account_no, account_product_code)
        body = self._rvsecncl_body(
            account=resolved,
            order_ref=order_ref,
            correlation_key=correlation_key,
            dvsn_code="01",
            order_type=amendment.order_type,
            quantity=amendment.quantity,
            limit_price=amendment.limit_price,
            cancel_all=False,
        )
        payload = await self._transport.post_json(
            KIS_ORDER_RVSECNCL_PATH,
            tr_id=KIS_ORDER_RVSECNCL_TR_ID,
            body=body,
        )
        new_ref, _, occurred_at = parse_order_ack(
            payload,
            account_id=resolved.account_id,
            original_order_id=order_ref.order_id,
        )
        ack = OrderAcknowledgement(
            order_ref=new_ref,
            state=OrderLifecycleState.ACKNOWLEDGED,
            occurred_at=occurred_at,
            message=None,
        )
        return ModifyOrderResponse(acknowledgement=ack)

    def stream_market_status(self, request: MarketStatusStreamRequest) -> AsyncIterator[MarketStatusEvent]:
        raise KXTUnsupportedError("KIS market-status streaming is not yet implemented in kxt")

    async def stream_order_events(
        self,
        request: OrderEventsStreamRequest | None = None,
        /,
        *,
        hts_id: str | None = None,
        account_no: str | None = None,
        account_product_code: str | None = None,
        account: AccountSummary | None = None,
    ) -> AsyncIterator["OrderAcceptedEvent | OrderAmendAckEvent | OrderCancelAckEvent | OrderRejectedEvent | FillNotificationEvent"]:
        """Unified realtime order + fill event stream (KIS H0STCNI0)."""

        if isinstance(request, OrderEventsStreamRequest):
            if hts_id is None:
                hts_id = request.hts_id
            if account is None:
                account = request.account
        resolved_hts_id = (hts_id or self._default_hts_id or "").strip()
        if not resolved_hts_id:
            raise KXTUnsupportedError(
                "KIS realtime notifications require an HTS user id (hts_id on the request or the client)"
            )
        resolved_account = self._resolve_account_optional(
            account, account_no, account_product_code
        )

        approval_key = await self._transport.get_approval_key()
        websocket = await self._transport.connect_websocket()
        try:
            try:
                await websocket.send(
                    json.dumps(
                        notification_subscription_message(
                            approval_key=approval_key,
                            hts_id=resolved_hts_id,
                        )
                    )
                )
                async for raw_message in websocket:
                    text = raw_message.decode() if isinstance(raw_message, bytes) else raw_message
                    if text.startswith("{"):
                        payload = json.loads(text)
                        if ((payload.get("header") or {}).get("tr_id")) == "PINGPONG":
                            await websocket.pong(raw_message if isinstance(raw_message, bytes) else text.encode())
                            continue
                    event = parse_notification_event(text, account=resolved_account)
                    if event is not None:
                        yield event
            except Exception as exc:
                mapped = map_websocket_exception(exc, action="streaming order notifications")
                if mapped is not None:
                    raise mapped from exc
                raise
        finally:
            with suppress(Exception):
                await websocket.close()

    async def stream_order_updates(
        self,
        request: OrderUpdatesStreamRequest | None = None,
        /,
        *,
        hts_id: str | None = None,
        account_no: str | None = None,
        account_product_code: str | None = None,
        account: AccountSummary | None = None,
    ) -> AsyncIterator[OrderUpdateEvent]:
        """Legacy alias yielding OrderUpdateEvent values for order lifecycle notifications."""

        if isinstance(request, OrderUpdatesStreamRequest):
            if account is None:
                account = request.account
        async for event in self.stream_order_events(
            hts_id=hts_id,
            account_no=account_no,
            account_product_code=account_product_code,
            account=account,
        ):
            if isinstance(event, FillNotificationEvent):
                continue
            state = _lifecycle_event_state(event)
            yield OrderUpdateEvent(
                order_ref=event.order_ref,
                symbol=event.symbol,
                state=state,
                occurred_at=event.occurred_at,
                message=None,
                filled_quantity=None,
                remaining_quantity=None,
            )

    async def stream_fill_updates(
        self,
        request: FillUpdatesStreamRequest | None = None,
        /,
        *,
        hts_id: str | None = None,
        account_no: str | None = None,
        account_product_code: str | None = None,
        account: AccountSummary | None = None,
    ) -> AsyncIterator[FillEvent]:
        """Legacy alias yielding FillEvent values for realtime fills."""

        if isinstance(request, FillUpdatesStreamRequest):
            if account is None:
                account = request.account
        async for event in self.stream_order_events(
            hts_id=hts_id,
            account_no=account_no,
            account_product_code=account_product_code,
            account=account,
        ):
            if not isinstance(event, FillNotificationEvent):
                continue
            report = ExecutionReport(
                execution_id=None,
                order_ref=event.order_ref,
                occurred_at=event.occurred_at,
                price=event.price,
                quantity=event.quantity,
            )
            yield FillEvent(report=report, symbol=event.symbol)

    # ---- internal helpers for account/trading ----

    def _default_account_summary(self) -> AccountSummary | None:
        if not self._default_account_no:
            return None
        return AccountSummary(
            provider=ProviderRef(provider="kis"),
            account_id=self._default_account_no,
            name=None,
            product_code=self._default_account_product_code,
        )

    def _resolve_account(
        self,
        account: AccountSummary | None = None,
        account_no: str | None = None,
        account_product_code: str | None = None,
    ) -> AccountSummary:
        if account is not None:
            if not account.account_id:
                raise KXTValidationError("account.account_id is required")
            return account
        if account_no:
            aid = account_no.strip()
            if not aid:
                raise KXTValidationError("account_no must not be empty")
            return AccountSummary(
                provider=ProviderRef(provider="kis"),
                account_id=aid,
                name=None,
                product_code=(account_product_code or "").strip() or None,
            )
        default = self._default_account_summary()
        if default is None:
            raise KXTValidationError(
                "account is required (pass account_no/account_product_code or AccountSummary, "
                "or configure account_no/account_product_code on the client)"
            )
        return default

    def _resolve_account_optional(
        self,
        account: AccountSummary | None = None,
        account_no: str | None = None,
        account_product_code: str | None = None,
    ) -> AccountSummary | None:
        if account is not None:
            return account
        if account_no:
            aid = account_no.strip()
            if not aid:
                return None
            return AccountSummary(
                provider=ProviderRef(provider="kis"),
                account_id=aid,
                name=None,
                product_code=(account_product_code or "").strip() or None,
            )
        return self._default_account_summary()

    @staticmethod
    def _resolve_instrument_opt(value: str | InstrumentRef | None) -> InstrumentRef | None:
        if value is None:
            return None
        return KISClient._coerce_instrument(value)

    def _account_params(self, account: AccountSummary) -> dict[str, str]:
        return {
            "CANO": account.account_id,
            "ACNT_PRDT_CD": account.product_code or "",
        }

    def _rvsecncl_body(
        self,
        *,
        account: AccountSummary,
        order_ref: ProviderOrderRef,
        correlation_key: OrderCorrelationKey | None,
        dvsn_code: str,
        order_type: OrderType | None,
        quantity,
        limit_price,
        cancel_all: bool,
    ) -> dict[str, str]:
        origin_org_no = correlation_key.origin_org_no if correlation_key else None
        qty_text = "0" if quantity is None else str(quantity)
        price_text = "0" if limit_price is None else str(limit_price)
        order_type_code = (
            _order_type_to_kis_code(order_type) if order_type is not None else "00"
        )
        return {
            "CANO": account.account_id,
            "ACNT_PRDT_CD": account.product_code or "",
            "KRX_FWDG_ORD_ORGNO": origin_org_no or "",
            "ORGN_ODNO": order_ref.order_id,
            "ORD_DVSN": order_type_code,
            "RVSE_CNCL_DVSN_CD": dvsn_code,
            "ORD_QTY": qty_text,
            "ORD_UNPR": price_text,
            "QTY_ALL_ORD_YN": "Y" if cancel_all else "N",
        }

    async def stream_trades(self, symbol: str | InstrumentRef | TradeSubscription | TradeStreamRequest, /) -> AsyncIterator[TradeEvent]:
        """Compatibility wrapper for the current legacy surface."""

        if isinstance(symbol, TradeStreamRequest):
            subscription = TradeSubscription(instrument=symbol.instrument)
        elif isinstance(symbol, TradeSubscription):
            subscription = symbol
        else:
            subscription = TradeSubscription(instrument=self._coerce_instrument(symbol))
        if not self.capabilities.streams.trades.supported:
            raise KXTUnsupportedError("KIS trade streaming is not supported by this client")
        if subscription.instrument is None:
            raise KXTUnsupportedError("KIS trade streaming currently requires subscription.instrument")
        if subscription.scope is not None:
            raise KXTUnsupportedError("KIS trade streaming does not yet support scope-wide subscriptions")
        instrument = self._normalize_instrument(subscription.instrument)

        session = self.realtime
        sub = await session.subscribe(StreamKind.trades, instrument)
        try:
            async for event in sub.events():
                yield event
        finally:
            with suppress(Exception):
                await sub.aclose()

    async def stream_orderbook(self, symbol: str | InstrumentRef | OrderBookSubscription | OrderBookStreamRequest, /) -> AsyncIterator[OrderBookEvent]:
        if isinstance(symbol, OrderBookStreamRequest):
            subscription = OrderBookSubscription(instrument=symbol.instrument)
        elif isinstance(symbol, OrderBookSubscription):
            subscription = symbol
        else:
            subscription = OrderBookSubscription(instrument=self._coerce_instrument(symbol))
        if not self.capabilities.streams.order_book.supported:
            raise KXTUnsupportedError("KIS order book streaming is not supported by this client")
        instrument = self._normalize_instrument(subscription.instrument)

        session = self.realtime
        sub = await session.subscribe(StreamKind.order_book, instrument)
        try:
            async for event in sub.events():
                yield event
        finally:
            with suppress(Exception):
                await sub.aclose()

    @staticmethod
    def _coerce_instrument(value: str | InstrumentRef) -> InstrumentRef:
        """Normalize a public-facing primitive `symbol` (or `InstrumentRef`) to InstrumentRef.

        Public market-data and streaming methods accept a bare `symbol` string as
        the primary primitive form. `InstrumentRef` is still accepted for advanced /
        explicit forms (e.g. when a venue or market segment hint is required).
        """

        if isinstance(value, InstrumentRef):
            return value
        if isinstance(value, str):
            sym = value.strip()
            if not sym:
                raise KXTValidationError("symbol must not be empty")
            return InstrumentRef(symbol=sym)
        raise KXTValidationError(
            f"symbol must be a str or InstrumentRef (got {type(value).__name__})"
        )

    def _normalize_instrument(self, instrument: InstrumentRef) -> InstrumentRef:
        if not instrument.symbol:
            raise KXTValidationError("instrument.symbol is required")
        if instrument.venue not in (None, Venue.KRX):
            raise KXTUnsupportedError("KIS first slice supports domestic equity venues only")
        if instrument.market_segment not in (None, MarketSegment.KOSPI, MarketSegment.KOSDAQ, MarketSegment.KONEX):
            raise KXTUnsupportedError("KIS first slice supports domestic equity market segments only")
        if instrument.venue is not None:
            return instrument
        return InstrumentRef(
            symbol=instrument.symbol,
            venue=Venue.KRX,
            market_segment=instrument.market_segment,
            instrument_id=instrument.instrument_id,
            name=instrument.name,
            isin=instrument.isin,
            asset_class=instrument.asset_class,
            instrument_type=instrument.instrument_type,
        )

    async def _fetch_minute_bars(
        self,
        instrument: InstrumentRef,
        *,
        start: date | datetime | None,
        end: date | datetime | None,
        interval_minutes: int,
    ) -> tuple[MarketBar, ...]:
        if interval_minutes < 1:
            raise KXTValidationError("interval_minutes must be >= 1")
        start_dt = _coerce_datetime(start, is_end=False)
        end_dt = _coerce_datetime(end, is_end=True)
        if start_dt is not None and end_dt is not None and start_dt > end_dt:
            raise KXTValidationError("start must be <= end")

        today = datetime.now(UTC).date()
        if (start_dt is None or start_dt.date() == today) and (end_dt is None or end_dt.date() == today):
            return await self._fetch_current_day_minute_bars(instrument, start_dt=start_dt, end_dt=end_dt, interval_minutes=interval_minutes)
        return await self._fetch_historical_minute_bars(instrument, start_dt=start_dt, end_dt=end_dt, interval_minutes=interval_minutes)

    async def _fetch_current_day_minute_bars(
        self,
        instrument: InstrumentRef,
        *,
        start_dt: datetime | None,
        end_dt: datetime | None,
        interval_minutes: int,
    ) -> tuple[MarketBar, ...]:
        collected: dict[datetime, MarketBar] = {}
        cursor = (end_dt or datetime.now(UTC).replace(hour=15, minute=30, second=0, microsecond=0)).strftime("%H%M%S")
        while True:
            payload = await self._transport.get_json(
                KIS_CURRENT_MINUTE_PATH,
                tr_id=KIS_CURRENT_MINUTE_TR_ID,
                params={
                    "FID_COND_MRKT_DIV_CODE": "J",
                    "FID_INPUT_ISCD": instrument.symbol,
                    "FID_INPUT_HOUR_1": cursor,
                    "FID_PW_DATA_INCU_YN": "Y",
                    "FID_ETC_CLS_CODE": "",
                },
            )
            bars = parse_market_bars(payload, instrument=instrument, timeframe=BarTimeframe.MINUTE, interval_minutes=1)
            filtered = _filter_market_bars(bars, start_dt=start_dt, end_dt=end_dt)
            for bar in filtered:
                collected[bar.opened_at] = bar
            if not bars or len(bars) < 30:
                break
            earliest = min(bar.opened_at for bar in bars)
            if start_dt is not None and earliest <= start_dt:
                break
            next_cursor = (earliest - timedelta(minutes=1)).strftime("%H%M%S")
            if next_cursor >= cursor:
                break
            cursor = next_cursor
        return _aggregate_market_bars(tuple(collected.values()), interval_minutes=interval_minutes)

    async def _fetch_historical_minute_bars(
        self,
        instrument: InstrumentRef,
        *,
        start_dt: datetime | None,
        end_dt: datetime | None,
        interval_minutes: int,
    ) -> tuple[MarketBar, ...]:
        end_anchor = end_dt or datetime.now(UTC)
        start_anchor = start_dt or (end_anchor - timedelta(days=1))
        collected: dict[datetime, MarketBar] = {}
        trade_date = end_anchor.date()
        while trade_date >= start_anchor.date():
            day_end = min(end_anchor, datetime.combine(trade_date, time(15, 30), tzinfo=UTC)) if trade_date == end_anchor.date() else datetime.combine(trade_date, time(15, 30), tzinfo=UTC)
            day_start = max(start_anchor, datetime.combine(trade_date, time(0, 0), tzinfo=UTC)) if trade_date == start_anchor.date() else datetime.combine(trade_date, time(0, 0), tzinfo=UTC)
            cursor = day_end.strftime("%H%M%S")
            while True:
                payload = await self._transport.get_json(
                    KIS_HISTORICAL_MINUTE_PATH,
                    tr_id=KIS_HISTORICAL_MINUTE_TR_ID,
                    params={
                        "FID_COND_MRKT_DIV_CODE": "J",
                        "FID_INPUT_ISCD": instrument.symbol,
                        "FID_INPUT_HOUR_1": cursor,
                        "FID_INPUT_DATE_1": trade_date.strftime("%Y%m%d"),
                        "FID_PW_DATA_INCU_YN": "Y",
                        "FID_FAKE_TICK_INCU_YN": "",
                    },
                )
                bars = parse_market_bars(payload, instrument=instrument, timeframe=BarTimeframe.MINUTE, interval_minutes=1)
                same_day = tuple(bar for bar in bars if bar.opened_at.date() == trade_date)
                filtered = _filter_market_bars(same_day, start_dt=day_start, end_dt=day_end)
                for bar in filtered:
                    collected[bar.opened_at] = bar
                if not same_day or len(same_day) < 120:
                    break
                earliest = min(bar.opened_at for bar in same_day)
                if earliest <= day_start:
                    break
                next_cursor = (earliest - timedelta(minutes=1)).strftime("%H%M%S")
                if next_cursor >= cursor:
                    break
                cursor = next_cursor
            trade_date -= timedelta(days=1)
        return _aggregate_market_bars(tuple(collected.values()), interval_minutes=interval_minutes)

    async def _fetch_period_bars(
        self,
        instrument: InstrumentRef,
        *,
        timeframe: BarTimeframe,
        start: date | datetime | None,
        end: date | datetime | None,
        adjusted: bool,
    ) -> tuple[MarketBar, ...]:
        if timeframe == BarTimeframe.MINUTE:
            raise KXTValidationError("period fetch requires non-minute timeframe")
        start_date = _coerce_date(start) or date(1980, 1, 1)
        end_date = _coerce_date(end) or datetime.now(UTC).date()
        if start_date > end_date:
            raise KXTValidationError("start must be <= end")
        payload = await self._transport.get_json(
            KIS_PERIOD_BARS_PATH,
            tr_id=KIS_PERIOD_BARS_TR_ID,
            params={
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": instrument.symbol,
                "FID_INPUT_DATE_1": start_date.strftime("%Y%m%d"),
                "FID_INPUT_DATE_2": end_date.strftime("%Y%m%d"),
                "FID_PERIOD_DIV_CODE": _period_code_for_timeframe(timeframe),
                "FID_ORG_ADJ_PRC": "0" if adjusted else "1",
            },
        )
        bars = parse_market_bars(payload, instrument=instrument, timeframe=timeframe)
        return _filter_market_bars(bars, start_dt=_coerce_datetime(start, is_end=False), end_dt=_coerce_datetime(end, is_end=True))

    async def _fetch_recent_trades_today(
        self,
        instrument: InstrumentRef,
        *,
        start_dt: datetime | None,
        end_dt: datetime | None,
        limit: int,
    ) -> tuple[Trade, ...]:
        collected: list[Trade] = []
        seen: set[tuple[datetime, str, str, str | None]] = set()
        cursor = (end_dt or datetime.now(UTC).replace(hour=15, minute=30, second=0, microsecond=0)).strftime("%H%M%S")

        while len(collected) < limit:
            payload = await self._transport.get_json(
                KIS_RECENT_TRADES_PATH,
                tr_id=KIS_RECENT_TRADES_TR_ID,
                params={
                    "FID_COND_MRKT_DIV_CODE": "J",
                    "FID_INPUT_ISCD": instrument.symbol,
                    "FID_INPUT_HOUR_1": cursor,
                },
            )
            trades = parse_recent_trades(payload, instrument=instrument)
            filtered = _filter_trades(trades, start_dt=start_dt, end_dt=end_dt)
            for trade in reversed(filtered):
                key = (trade.occurred_at, str(trade.price), str(trade.quantity), str(trade.sequence) if trade.sequence is not None else None)
                if key in seen:
                    continue
                seen.add(key)
                collected.append(trade)
                if len(collected) >= limit:
                    break

            if not trades:
                break
            earliest = min(trade.occurred_at for trade in trades)
            if start_dt is not None and earliest <= start_dt:
                break
            next_cursor = (earliest - timedelta(seconds=1)).strftime("%H%M%S")
            if next_cursor >= cursor:
                break
            cursor = next_cursor

        return tuple(sorted(collected, key=lambda item: (item.occurred_at, str(item.sequence or ""))))[-limit:]


def _period_code_for_timeframe(timeframe: BarTimeframe) -> str:
    return {
        BarTimeframe.DAY: "D",
        BarTimeframe.WEEK: "W",
        BarTimeframe.MONTH: "M",
        BarTimeframe.YEAR: "Y",
    }[timeframe]


def _coerce_datetime(value: date | datetime | None, *, is_end: bool) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    base_time = time(23, 59, 59) if is_end else time(0, 0, 0)
    return datetime.combine(value, base_time, tzinfo=UTC)


def _coerce_date(value: date | datetime | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    return value


def _filter_market_bars(
    bars: tuple[MarketBar, ...],
    *,
    start_dt: datetime | None,
    end_dt: datetime | None,
) -> tuple[MarketBar, ...]:
    return tuple(
        bar
        for bar in sorted(bars, key=lambda item: item.opened_at)
        if (start_dt is None or bar.opened_at >= start_dt) and (end_dt is None or bar.opened_at <= end_dt)
    )


def _filter_trades(
    trades: tuple[Trade, ...],
    *,
    start_dt: datetime | None,
    end_dt: datetime | None,
) -> tuple[Trade, ...]:
    return tuple(
        trade
        for trade in sorted(trades, key=lambda item: (item.occurred_at, str(item.sequence or "")))
        if (start_dt is None or trade.occurred_at >= start_dt) and (end_dt is None or trade.occurred_at <= end_dt)
    )


def _aggregate_market_bars(bars: tuple[MarketBar, ...], *, interval_minutes: int) -> tuple[MarketBar, ...]:
    if interval_minutes == 1:
        return _filter_market_bars(bars, start_dt=None, end_dt=None)
    source = _filter_market_bars(bars, start_dt=None, end_dt=None)
    if not source:
        return ()
    aggregated: list[MarketBar] = []
    current: MarketBar | None = None
    current_key: tuple[date, int, int] | None = None
    for bar in source:
        minute = (bar.opened_at.minute // interval_minutes) * interval_minutes
        bucket_opened_at = bar.opened_at.replace(minute=minute, second=0, microsecond=0)
        bucket_key = (bucket_opened_at.date(), bucket_opened_at.hour, bucket_opened_at.minute)
        if current_key != bucket_key:
            if current is not None:
                aggregated.append(current)
            current_key = bucket_key
            current = MarketBar(
                symbol=bar.symbol,
                opened_at=bucket_opened_at,
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
        assert current is not None
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


def _coerce_bars_request(request: BarsRequest | InstrumentRef | str, /, **kwargs) -> BarsRequest:
    if isinstance(request, BarsRequest):
        return request
    if isinstance(request, str):
        sym = request.strip()
        if not sym:
            raise KXTValidationError("symbol must not be empty")
        request = InstrumentRef(symbol=sym)
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


def _quote_response_from_snapshot(snapshot: QuoteSnapshot) -> QuoteResponse:
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


def _bar_from_market_bar(bar: MarketBar, *, timeframe: str) -> Bar:
    return Bar(
        opened_at=bar.opened_at,
        timeframe=timeframe,
        open=bar.open,
        high=bar.high,
        low=bar.low,
        close=bar.close,
        volume=bar.volume,
    )


def _trade_print_from_trade(trade: Trade) -> TradePrint:
    return TradePrint(
        occurred_at=trade.occurred_at,
        price=trade.price,
        quantity=trade.quantity,
        ask_price=trade.ask_price,
        bid_price=trade.bid_price,
    )


def _trade_event_from_trade(trade: Trade) -> TradeEvent:
    return TradeEvent(
        occurred_at=trade.occurred_at,
        symbol=trade.symbol,
        price=trade.price,
        quantity=trade.quantity,
        side=trade.side,
    )


def _orderbook_response_from_snapshot(snapshot: OrderBookSnapshot) -> OrderBookResponse:
    return OrderBookResponse(
        occurred_at=snapshot.occurred_at,
        asks=snapshot.asks,
        bids=snapshot.bids,
        total_ask_quantity=snapshot.total_ask_quantity,
        total_bid_quantity=snapshot.total_bid_quantity,
    )


def _orderbook_event_from_snapshot(snapshot: OrderBookSnapshot) -> OrderBookEvent:
    return OrderBookEvent(
        occurred_at=snapshot.occurred_at,
        symbol=snapshot.symbol,
        asks=snapshot.asks,
        bids=snapshot.bids,
        total_ask_quantity=snapshot.total_ask_quantity,
        total_bid_quantity=snapshot.total_bid_quantity,
    )


def _lifecycle_event_state(event) -> OrderLifecycleState:
    if isinstance(event, OrderAcceptedEvent):
        return OrderLifecycleState.ACKNOWLEDGED
    if isinstance(event, OrderAmendAckEvent):
        return OrderLifecycleState.ACKNOWLEDGED
    if isinstance(event, OrderCancelAckEvent):
        return OrderLifecycleState.CANCELED
    if isinstance(event, OrderRejectedEvent):
        return OrderLifecycleState.REJECTED
    return OrderLifecycleState.UNKNOWN
