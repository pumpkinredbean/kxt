# get_open_orders

지정한 계좌의 미체결(또는 부분 체결) 주문 목록을 가져옵니다. 자동매매 루프에서 외부 영향(수동 주문, 미체결 잔존)을 점검하거나 정정·취소 후보를 찾을 때 사용합니다.

## At a glance

| 항목 | 값 |
|---|---|
| 인증 필요 | 예 (KIS 앱키/시크릿 + 계좌) |
| 데이터 타입 | 미체결 주문 시퀀스 |
| 스트리밍 | 별도 메서드 ([`stream_order_events`](../streaming/stream-order-events.md)) |
| 계좌 컨텍스트 | `KISClient` 기본 계좌 권장 |
| 시간대 | KST (Asia/Seoul) |
| Paper trading | 미지원 |

## Signature

```python
async def get_open_orders(
    request: OpenOrdersRequest | None = None,
    /,
    *,
    account_no: str | None = None,
    account_product_code: str | None = None,
    account: AccountSummary | None = None,
    instrument: str | InstrumentRef | None = None,
    session: SessionType | None = None,
) -> OpenOrdersResponse: ...
```

## Parameters

- **account_no** / **account_product_code** (`str | None`) — 생략 시 `KISClient` 기본 계좌.
- **account** (`AccountSummary | None`) — power-user alias.
- **instrument** (`str | InstrumentRef | None`) — 특정 종목으로 클라이언트 측 필터링 (심볼 문자열도 가능).
- **session** (`SessionType | None`)

## Returns

`OpenOrdersResponse`:

| 필드 | 타입 |
|---|---|
| `orders` | `tuple[OpenOrder, ...]` |

`OpenOrder` 주요 필드 — [Schemas](../../reference/schemas.md#openorder):

| 필드 | 타입 | 설명 |
|---|---|---|
| `order_ref` | `ProviderOrderRef` | KIS 주문 식별 |
| `instrument` | `InstrumentRef` | 종목 |
| `side` | `OrderSide` | 매수/매도 |
| `order_type` | `OrderType` | 주문 유형 |
| `quantity` | `Decimal` | 원 주문 수량 |
| `remaining_quantity` | `Decimal \| None` | 미체결 수량 |
| `limit_price` | `Decimal \| None` | 지정가 |
| `state` | `OrderLifecycleState` | 정규화 상태 |
| `correlation_key` | `OrderCorrelationKey \| None` | 정정·취소에 필요한 KIS origin 식별 묶음 |

## Example

```python
import asyncio

from kxt import KISClient


async def main() -> None:
    async with KISClient(
        app_key="<APP_KEY>",
        app_secret="<APP_SECRET>",
        account_no="<CANO>",
        account_product_code="<ACNT_PRDT_CD>",
    ) as client:
        response = await client.get_open_orders()
        for order in response.orders:
            print(
                order.order_ref.order_id,
                order.instrument.symbol,
                order.side,
                order.remaining_quantity,
                order.limit_price,
            )


asyncio.run(main())
```

## Sample response

```python
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from kxt import (
    InstrumentRef,
    OpenOrder,
    OpenOrdersResponse,
    OrderCorrelationKey,
    OrderLifecycleState,
    OrderSide,
    OrderType,
    ProviderOrderRef,
)

KST = timezone(timedelta(hours=9))
order_ref = ProviderOrderRef(provider="kis", order_id="0000000123", account_id="12345678")

OpenOrdersResponse(
    orders=(
        OpenOrder(
            order_ref=order_ref,
            instrument=InstrumentRef(symbol="005930"),
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("10"),
            remaining_quantity=Decimal("10"),
            limit_price=Decimal("70000"),
            state=OrderLifecycleState.WORKING,
            occurred_at=datetime(2025, 4, 14, 10, 0, tzinfo=KST),
            correlation_key=OrderCorrelationKey(order_ref=order_ref, origin_org_no="01234"),
        ),
    ),
)
```

## Notes

- **종목 필터는 클라이언트 측**입니다. KIS 응답을 모두 받은 뒤 `instrument.symbol`이 일치하는 항목만 남깁니다. 트래픽이 줄지는 않습니다.
- **`correlation_key`를 보존**하세요. 정정·취소 호출 시 `OpenOrder`를 그대로 `cancel_order(...)` / `modify_order(...)`에 넘기면 됩니다.
- **장 마감 후**: 일중 정상 처리된 미체결은 자동 취소되어 빈 목록이 반환될 수 있습니다.

## KIS specifics

- **원본 엔드포인트**: `TTTC8036R` (정정·취소 가능 주문 조회).
- **Rate limit 버킷**: 계좌 조회.

## Common pitfalls

- **`order_id`만으로 정정·취소 시도**: KIS는 `(order_id, origin_org_no)` 묶음이 필요할 수 있습니다. `OpenOrder` 자체를 전달해 `correlation_key`까지 자동 전파되게 하세요.
- **`state` 가정**: `WORKING`이 가장 흔하지만 부분 체결은 `PARTIALLY_FILLED`일 수 있습니다.

## See also

- [cancel_order](../trading/cancel-order.md)
- [modify_order](../trading/modify-order.md)
- [stream_order_events](../streaming/stream-order-events.md)
- [Schemas](../../reference/schemas.md#openorder)
