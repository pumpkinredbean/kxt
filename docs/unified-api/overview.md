# Unified API Overview

Unified API는 프로바이더 간 차이를 흡수한 브로커 중립 메서드 집합입니다. 현재 `kxt`는 단일 프로바이더(KIS)를 지원하지만, 메서드 이름·파라미터·반환 DTO는 추가 프로바이더를 고려해 설계되어 있습니다.

## Categories

| 구분 | 의미 |
|---|---|
| **Public** | 시세 계열. 계좌 컨텍스트가 필요 없습니다 (현재 KIS는 시세에도 앱키 필요) |
| **Private** | 계좌·주문 계열. 계좌번호와 상품코드가 필요합니다 |
| **Streaming** | WebSocket 기반 실시간 이벤트 이터레이터 |

!!! note "KIS는 공개 시세도 인증 필요"
    KIS OpenAPI는 시세 조회에도 앱키/앱시크릿이 필요합니다. `Public`이라는 표지는 "프로바이더 자격으로는 계좌 컨텍스트가 필요하지 않다"는 의미로 사용하세요.

## Assumptions

- **async-only** — 모든 메서드는 코루틴입니다. 동기 래퍼는 제공하지 않습니다.
- **Primitive in, DTO out** — 기본 호출은 종목 코드 문자열과 kwargs로 합니다. 응답·이벤트는 `*Response`/`*Event` 데이터클래스로 받습니다. 입력을 통째로 묶고 싶으면 `kxt.requests`의 `*Request` DTO를 power-user 경로로 사용할 수 있습니다.
- **불변성** — 모든 DTO는 `frozen=True` 데이터클래스입니다.
- **Decimal 가격** — 가격·수량은 `Decimal`입니다. 부동소수점 오차를 피하기 위함입니다.
- **env-free SDK** — 자격증명은 명시적 키워드 인자로만 받습니다 ([Authentication](../getting-started/authentication.md)).

## Capabilities

각 클라이언트는 `capabilities` 속성을 통해 지원 여부를 자기 서술합니다.

```python
from kxt import KISClient

async with KISClient(app_key="<APP_KEY>", app_secret="<APP_SECRET>") as client:
    print(client.capabilities)
```

이 테이블은 프로바이더별 문서([KIS](../providers/kis.md))의 지원 매트릭스와 일치합니다.

## Public — Market data

장내 시세·체결·호가·시장 상태를 다룹니다.

| 메서드 | 설명 | 문서 |
|---|---|---|
| `get_bars` | OHLCV K-line (분/일/주/월/년) | [get_bars](market-data/get-bars.md) |
| `get_quote` | 최근 체결 스냅샷 | [get_quote](market-data/get-quote.md) |
| `get_orderbook` | 호가창 스냅샷 | [get_orderbook](market-data/get-orderbook.md) |
| `get_recent_trades` | 당일 체결 프린트 | [get_recent_trades](market-data/get-recent-trades.md) |
| `get_market_status` | 시장 상태(개장/단일가) | [get_market_status](market-data/get-market-status.md) |
| `get_investor_flow` | 투자자별 매매 동향 | [get_investor_flow](market-data/get-investor-flow.md) |

## Streaming

WebSocket 기반 실시간 이터레이터입니다.

| 메서드 | 설명 | 문서 |
|---|---|---|
| `stream_trades` | 실시간 체결 | [stream_trades](streaming/stream-trades.md) |
| `stream_orderbook` | 실시간 호가 | [stream_orderbook](streaming/stream-orderbook.md) |
| `stream_order_events` | 본인 주문 라이프사이클+체결 통합 | [stream_order_events](streaming/stream-order-events.md) |
| `stream_order_updates` | 라이프사이클 별칭 | [stream_order_updates](streaming/stream-order-updates.md) |
| `stream_fill_updates` | 체결 별칭 | [stream_fill_updates](streaming/stream-fill-updates.md) |

## Private — Account

계좌 상태 조회입니다. 계좌번호·상품코드가 필요합니다.

| 메서드 | 설명 | 문서 |
|---|---|---|
| `get_account_overview` | 평가 + 포지션 풀 뷰 | [get_account_overview](account/get-account-overview.md) |
| `get_balance` | 평가 요약만 | [get_balance](account/get-balance.md) |
| `get_positions` | 보유 포지션만 | [get_positions](account/get-positions.md) |
| `get_buying_power` | 종목별 매수 가능 금액 | [get_buying_power](account/get-buying-power.md) |
| `get_open_orders` | 미체결 주문 | [get_open_orders](account/get-open-orders.md) |
| `get_order_history` | 주문 이력 | [get_order_history](account/get-order-history.md) |

## Private — Trading

실거래 주문입니다.

| 메서드 | 설명 | 문서 |
|---|---|---|
| `submit_order` | 신규 주문 제출 | [submit_order](trading/submit-order.md) |
| `cancel_order` | 주문 취소 | [trading/cancel-order](trading/cancel-order.md) |
| `modify_order` | 주문 정정 | [trading/modify-order](trading/modify-order.md) |

!!! info "문서 작성 기준"
    `get_bars`가 골드 스탠다드 템플릿입니다. 모든 메서드 페이지는 동일 구조(At a glance → Signature → Parameters → Returns → Example → Sample response → Notes → KIS specifics → Common pitfalls → See also)를 따릅니다.

## Legacy compatibility

`fetch_*` 형태의 이전 메서드와 그룹 네임스페이스(`client.market.*`, `client.streams.*`)가 하위 호환을 위해 남아 있습니다. 신규 코드에서는 평평한 `get_*`/`stream_*` 메서드를 사용하세요.
