# Schemas

`kxt`의 모든 요청·응답은 `frozen=True` 데이터클래스입니다. 프로바이더 페이로드의 필드명과 무관하게, 여기 정의된 타입이 공개 계약입니다.

!!! tip "import"
    응답·이벤트 DTO와 enum, value object는 `kxt` 최상위에서 import합니다. 입력용 `*Request`, `*Cursor`, `*Subscription`, `OrderInstruction`, `OrderAmendment`, `ProviderRef`는 `kxt.requests`에서 가져옵니다. 모든 DTO를 한 번에 introspection하려면 `kxt.models`를 사용하세요.

    ```python
    from kxt import BarsResponse, Bar, MarketBar, InstrumentRef
    from kxt.requests import BarsRequest
    ```

## Core reference types

### InstrumentRef

종목 참조. 최소 `symbol`만 있으면 대부분의 호출에 충분합니다.

- **symbol** (`str`, required) — 거래소 코드 (예: `"005930"`).
- **venue** (`Venue | None`) — 거래 장소 (KRX, KOSDAQ 등).
- **market_segment** (`MarketSegment | None`) — 시장 세그먼트.
- **instrument_id** (`str | None`) — 프로바이더 내부 식별자.
- **name** (`str | None`) — 종목명 (예: `"삼성전자"`).
- **isin** (`str | None`) — ISIN 코드.
- **asset_class** (`AssetClass | None`) — 자산군 (주식, 선물, 옵션 등).
- **instrument_type** (`InstrumentType | None`) — 세부 타입.

### BarTimeframe

정규화된 봉 주기 패밀리.

| 값 | 의미 |
|---|---|
| `MINUTE` | 분봉 (실제 간격은 `timeframe` 문자열에서 파생) |
| `DAY` | 일봉 |
| `WEEK` | 주봉 |
| `MONTH` | 월봉 |
| `YEAR` | 년봉 |

## Market data DTOs

### Bar

공개 `BarsResponse`에 담기는 봉. 단일 인스트루먼트 요청에서 식별자를 루트에서 반복하지 않도록 경량화되어 있습니다.

- **opened_at** (`datetime`) — KST 봉 시작 시각.
- **timeframe** (`str`) — 상위 응답과 동일한 timeframe 문자열.
- **open** (`Decimal`) — 시가.
- **high** (`Decimal`) — 고가.
- **low** (`Decimal`) — 저가.
- **close** (`Decimal`) — 종가.
- **volume** (`Decimal`) — 누적 거래량.

### MarketBar

내부 브로커 중립 표현. 레거시 `fetch_bars` 경로에서 튜플로 반환됩니다. 신규 코드는 `Bar`를 사용하세요.

- **instrument** (`InstrumentRef`)
- **opened_at** (`datetime`)
- **timeframe** (`BarTimeframe`)
- **interval_minutes** (`int | None`)
- **open / high / low / close / volume** (`Decimal`)
- **notional** (`Decimal | None`) — 거래대금.

### BarsRequest

- **instrument** (`InstrumentRef`, required)
- **timeframe** (`str | BarTimeframe`, required) — `"day"`, `"5m"` 등.
- **start** (`date | datetime | None`)
- **end** (`date | datetime | None`)
- **adjusted** (`bool`, 기본 `True`)
- **session** (`SessionType | None`)

### BarsResponse

- **timeframe** (`str`) — 요청한 정규화 문자열.
- **bars** (`tuple[Bar, ...]`)
- **adjusted** (`bool`)
- **cursor** (`BarCursor | None`)

### BarCursor

- **next_opened_at** (`datetime | None`) — 이번 응답의 마지막 봉 시작 시각.

### QuoteRequest / QuoteResponse

`QuoteRequest`:

- **instrument** (`InstrumentRef`, required)
- **session** (`SessionType | None`)

`QuoteResponse` (최상위 호가 필드는 일부러 제외, 호가창은 `OrderBookSnapshot` 사용):

- **occurred_at** (`datetime`)
- **last** (`Decimal`)
- **open / high / low / previous_close / change / change_rate / volume** (`Decimal | None`)

### OrderBookSnapshot

- **instrument** (`InstrumentRef`)
- **occurred_at** (`datetime`)
- **asks** (`tuple[QuoteLevel, ...]`)
- **bids** (`tuple[QuoteLevel, ...]`)
- **total_ask_quantity / total_bid_quantity** (`Decimal | None`)

### QuoteLevel

- **price** (`Decimal`)
- **quantity** (`Decimal`)

### Trade / TradePrint

`Trade` — 인스트루먼트 포함 체결 팩트.

- **instrument** (`InstrumentRef`)
- **occurred_at** (`datetime`)
- **price / quantity** (`Decimal`)
- **side** (`TradeSide | None`)
- **trade_id** (`str | None`), **sequence** (`int | str | None`)
- **ask_price / bid_price** (`Decimal | None`)

`TradePrint` — 응답 DTO용 경량 변형 (단일 인스트루먼트 루트 중복 제거).

## Auto-rendered from code

핵심 모듈을 직접 참조하려면 아래를 사용하세요.

::: kxt.models.market_data
    options:
      members: [InstrumentRef, MarketBar, QuoteSnapshot, OrderBookSnapshot, QuoteLevel]
      show_root_heading: false
      heading_level: 3

::: kxt.models.api
    options:
      members: [Bar, BarsRequest, BarsResponse, BarCursor, QuoteRequest, QuoteResponse]
      show_root_heading: false
      heading_level: 3

## Additional market data DTOs

### OrderBookRequest / OrderBookResponse

<a id="orderbookresponse"></a>

`OrderBookRequest`:

- **instrument** (`InstrumentRef`, required)
- **session** (`SessionType | None`)

`OrderBookResponse` (단일 인스트루먼트 응답이라 루트에서 instrument는 생략):

- **occurred_at** (`datetime`)
- **asks** (`tuple[OrderBookLevel, ...]`) — `OrderBookLevel = QuoteLevel`
- **bids** (`tuple[OrderBookLevel, ...]`)
- **total_ask_quantity / total_bid_quantity** (`Decimal | None`)

### RecentTradesRequest / RecentTradesResponse

`RecentTradesRequest`:

- **instrument** (`InstrumentRef`, required)
- **start / end** (`date | datetime | None`) — 현재 KIS 구현은 당일 범위만 허용.
- **limit** (`int`, 기본 100)
- **session** (`SessionType | None`)

`RecentTradesResponse`:

- **trades** (`tuple[TradePrint, ...]`)

### MarketStatusRequest / MarketStatusResponse

`MarketStatusRequest`:

- **instrument** (`InstrumentRef | None`)
- **session** (`SessionType | None`)

`MarketStatusResponse`:

- **phase** (`MarketPhase`) — `PREOPEN`, `OPEN`, `AUCTION`, `AFTER_HOURS`, `CLOSED`, `HALTED`, `UNKNOWN`
- **occurred_at** (`datetime`)

### InvestorFlowRequest / InvestorFlowResponse / InvestorFlowBucket

`InvestorFlowRequest`:

- **instrument** (`InstrumentRef`, required)
- **start / end** (`date | datetime | None`) — 현재 KIS 구현은 미사용.
- **session** (`SessionType | None`) — `None` 또는 `REGULAR`만.

`InvestorFlowResponse` (한 시점의 누적 집계 단일 스냅샷):

- **as_of_date** (`date | None`)
- **retail / foreign / institution** (`InvestorFlowBucket`)

`InvestorFlowBucket`:

- **buy_quantity / sell_quantity / net_buy_quantity** (`Decimal | None`)
- **buy_notional / sell_notional / net_buy_notional** (`Decimal | None`)

## Account and trading DTOs

### AccountSummary / ProviderRef

`ProviderRef`:

- **provider** (`str`) — 예: `"kis"`
- **account_id** (`str | None`)
- **route** (`str | None`)

`AccountSummary`:

- **provider** (`ProviderRef`, required)
- **account_id** (`str`, required) — 계좌번호 (CANO)
- **name** (`str | None`)
- **product_code** (`str | None`) — 상품코드 (예: `"01"`)

### AccountOverviewRequest / AccountOverviewResponse / AccountOverviewCursor

`AccountOverviewRequest` (power-user용; 기본 사용은 `client.get_account_overview(...)` kwargs):

- **account** (`AccountSummary | None`) — 생략 시 클라이언트 기본 계좌.
- **include_afterhours** (`bool`, 기본 `False`)
- **include_fund_settlement** (`bool`, 기본 `True`)
- **cursor** (`AccountOverviewCursor | None`)

`AccountOverviewResponse`:

- **equity** (`AccountEquitySnapshot`)
- **positions** (`tuple[PositionLot, ...]`)
- **cursor** (`AccountOverviewCursor | None`)

`AccountOverviewCursor`:

- **fk100** (`str | None`)
- **nk100** (`str | None`)

### AccountEquitySnapshot

<a id="accountequitysnapshot"></a>

- **account** (`AccountSummary`)
- **as_of** (`datetime`)
- **cash, d1_settlement, d2_settlement** (`Decimal | None`)
- **securities_value, total_value, net_asset_value** (`Decimal | None`)
- **total_cost_basis, positions_market_value, total_unrealized_pnl** (`Decimal | None`)
- **previous_total_value, asset_change, asset_change_rate** (`Decimal | None`)

### PositionLot

<a id="positionlot"></a>

- **instrument** (`InstrumentRef`)
- **quantity** (`Decimal`)
- **orderable_quantity, average_price, cost_basis** (`Decimal | None`)
- **market_price, market_value** (`Decimal | None`)
- **unrealized_pnl, unrealized_pnl_rate** (`Decimal | None`)
- **today / previous_day** (`PositionDayActivity | None`) — 각각 `buy_quantity` / `sell_quantity`

### BalanceRequest / BalanceResponse / BalanceSnapshot

<a id="balancesnapshot"></a>

`BalanceRequest`:

- **account** (`AccountSummary | None`)
- **instrument** (`InstrumentRef | None`)
- **session** (`SessionType | None`)

`BalanceSnapshot`:

- **account** (`AccountSummary | None`)
- **as_of** (`datetime | None`)
- **cash, buying_power, margin_available, net_liquidation_value** (`Decimal | None`)

### PositionsRequest / PositionsResponse / Position

`Position`:

- **instrument** (`InstrumentRef`)
- **quantity** (`Decimal`)
- **average_price, market_price, unrealized_pnl** (`Decimal | None`)
- **side** (`OrderSide | None`) — KIS 현물 잔고는 항상 `None`

### BuyingPowerRequest / BuyingPowerResponse / BuyingPowerSnapshot

<a id="buyingpowersnapshot"></a>

`BuyingPowerRequest` (power-user용):

- **instrument** (`InstrumentRef`, required)
- **price** (`Decimal | None`)
- **order_type** (`OrderType`, 기본 `LIMIT`)
- **include_cma** (`bool`, 기본 `False`)
- **account** (`AccountSummary | None`)

`BuyingPowerSnapshot`:

- **available_cash, available_substitute, reusable_amount** (`Decimal | None`)
- **non_margin_buy_amount, non_margin_buy_quantity** (`Decimal | None`)
- **max_buy_amount, max_buy_quantity** (`Decimal | None`)
- **price_used_for_calc** (`Decimal | None`)

### OpenOrdersRequest / OpenOrdersResponse / OpenOrder

<a id="openorder"></a>

`OpenOrder` 핵심 필드:

- **order_ref** (`ProviderOrderRef`)
- **instrument** (`InstrumentRef`)
- **side** (`OrderSide`), **order_type** (`OrderType`)
- **quantity, remaining_quantity** (`Decimal | None`)
- **limit_price** (`Decimal | None`)
- **state** (`OrderLifecycleState`)
- **occurred_at** (`datetime | None`)
- **filled_quantity, cancelable_quantity, cancel_confirmed_quantity, rejected_quantity** (`Decimal | None`)
- **exchange_code** (`str | None`)
- **correlation_key** (`OrderCorrelationKey | None`)

### ProviderOrderRef / OrderCorrelationKey

`ProviderOrderRef`:

- **provider** (`str`), **order_id** (`str`)
- **original_order_id** (`str | None`) — 정정·취소 응답에서 원주문 보존
- **account_id** (`str | None`)

`OrderCorrelationKey`:

- **order_ref** (`ProviderOrderRef`)
- **origin_org_no** (`str | None`) — KIS `KRX_FWDG_ORD_ORGNO`
- **branch_no** (`str | None`)

### OrderHistoryRequest / OrderHistoryResponse / OrderHistoryRecord / OrderHistorySummary / OrderHistoryCursor

<a id="orderhistoryrecord"></a>

`OrderHistoryRequest` (power-user용):

- **start, end** (`date`, required)
- **instrument** (`InstrumentRef | None`)
- **side_filter** (`OrderSide | None`)
- **fill_filter** (`str`, 기본 `"all"`) — `"all" | "filled" | "unfilled"`
- **cursor** (`AccountOverviewCursor | None`)
- **account** (`AccountSummary | None`)

`OrderHistoryRecord`:

- **order_ref** (`ProviderOrderRef`)
- **correlation_key** (`OrderCorrelationKey`)
- **instrument** (`InstrumentRef`)
- **side** (`OrderSide`), **order_type** (`OrderType`)
- **quantity** (`Decimal`)
- **limit_price, average_fill_price** (`Decimal | None`)
- **filled_quantity** (`Decimal`)
- **filled_notional, remaining_quantity, rejected_quantity, cancel_confirmed_quantity** (`Decimal | None`)
- **is_canceled** (`bool`), **state** (`OrderLifecycleState`)
- **order_date** (`date | None`), **submitted_at** (`datetime | None`)
- **exchange_code** (`str | None`)

`OrderHistorySummary`:

- **total_buy_quantity, total_sell_quantity** (`Decimal | None`)
- **total_buy_notional, total_sell_notional** (`Decimal | None`)

`OrderHistoryCursor`: `fk100`, `nk100`.

### SubmitOrderRequest / SubmitOrderResponse / OrderInstruction / OrderAcknowledgement

`OrderInstruction`:

- **instrument** (`InstrumentRef`)
- **side** (`OrderSide`), **order_type** (`OrderType`)
- **quantity** (`Decimal`)
- **limit_price** (`Decimal | None`) — `LIMIT`일 때 필수
- **stop_price** (`Decimal | None`) — KIS 슬라이스 미사용
- **time_in_force** (`str | None`) — 미사용
- **route_hint** (`OrderRouteHint | None`) — 미사용

`OrderAcknowledgement`:

- **order_ref** (`ProviderOrderRef | None`)
- **state** (`OrderLifecycleState`)
- **occurred_at** (`datetime | None`)
- **message** (`str | None`)

### CancelOrderRequest / CancelOrderResponse

`CancelOrderRequest` (power-user용; 기본은 `client.cancel_order(open_order)` 또는 kwargs):

- **order_ref** (`ProviderOrderRef`, required)
- **account** (`AccountSummary | None`)
- **quantity** (`Decimal | None`)
- **cancel_all** (`bool`, 기본 `True`)
- **correlation_key** (`OrderCorrelationKey | None`)

### ModifyOrderRequest / ModifyOrderResponse / OrderAmendment

`OrderAmendment`:

- **quantity** (`Decimal | None`)
- **limit_price** (`Decimal | None`)
- **stop_price** (`Decimal | None`) — 미사용
- **order_type** (`OrderType | None`)

## Streaming DTOs

### TradeEvent

- **occurred_at** (`datetime`)
- **instrument** (`InstrumentRef`)
- **price, quantity** (`Decimal`)
- **side** (`TradeSide | None`)

### OrderBookEvent

- **occurred_at** (`datetime`)
- **instrument** (`InstrumentRef`)
- **asks, bids** (`tuple[OrderBookLevel, ...]`)
- **total_ask_quantity, total_bid_quantity** (`Decimal | None`)

### OrderEventsStreamRequest

- **account** (`AccountSummary | None`)
- **hts_id** (`str | None`)

### OrderAcceptedEvent / OrderAmendAckEvent / OrderCancelAckEvent / OrderRejectedEvent

공통 필드:

- **order_ref** (`ProviderOrderRef`)
- **correlation_key** (`OrderCorrelationKey`)
- **instrument** (`InstrumentRef`)
- **side** (`OrderSide`), **order_type** (`OrderType`)
- **occurred_at** (`datetime`)
- **account** (`AccountSummary | None`)

추가 필드:

- `OrderAcceptedEvent`, `OrderAmendAckEvent`: **quantity** (`Decimal`), **limit_price** (`Decimal | None`)
- `OrderCancelAckEvent`: **canceled_quantity** (`Decimal`)
- `OrderRejectedEvent`: **quantity** (`Decimal`), **reason_code** (`str | None`)

타입 별칭: `OrderLifecycleEvent = OrderAcceptedEvent | OrderAmendAckEvent | OrderCancelAckEvent | OrderRejectedEvent`.

### FillNotificationEvent

- 공통 필드 + **price** (`Decimal`), **quantity** (`Decimal`)

### OrderUpdatesStreamRequest / OrderUpdateEvent

`OrderUpdateEvent`:

- **order_ref** (`ProviderOrderRef`)
- **instrument** (`InstrumentRef`)
- **state** (`OrderLifecycleState`)
- **occurred_at** (`datetime`)
- **message** (`str | None`)
- **filled_quantity, remaining_quantity** (`Decimal | None`) — 별칭에서는 미충전

### FillUpdatesStreamRequest / FillEvent / ExecutionReport

`ExecutionReport`:

- **execution_id** (`str | None`)
- **order_ref** (`ProviderOrderRef`)
- **occurred_at** (`datetime`)
- **price, quantity** (`Decimal`)

`FillEvent`:

- **report** (`ExecutionReport`)
- **instrument** (`InstrumentRef`)

## Enums (summary)

- **OrderSide**: `BUY`, `SELL`
- **OrderType**: `MARKET`, `LIMIT`, `STOP`, `STOP_LIMIT`, `BEST`, `UNKNOWN`
- **OrderLifecycleState**: `PENDING`, `ACKNOWLEDGED`, `WORKING`, `PARTIALLY_FILLED`, `FILLED`, `CANCELED`, `REJECTED`, `EXPIRED`, `UNKNOWN`
- **MarketPhase**: `PREOPEN`, `OPEN`, `AUCTION`, `AFTER_HOURS`, `CLOSED`, `HALTED`, `UNKNOWN`
- **SessionType**: `REGULAR`, `NIGHT`, `UNKNOWN`
- **TradeSide**: `BUY`, `SELL`, `UNKNOWN`
