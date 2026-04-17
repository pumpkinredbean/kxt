# modify_order

지정한 미체결 주문을 정정합니다. 수량·지정가·주문 유형을 함께 변경할 수 있습니다.

## At a glance

| 항목 | 값 |
|---|---|
| 인증 필요 | 예 (KIS 앱키/시크릿 + 계좌) |
| 데이터 타입 | 정정 ack |
| 스트리밍 | 후속 상태는 [`stream_order_events`](../streaming/stream-order-events.md) |
| 계좌 컨텍스트 | `KISClient` 기본 계좌 권장 |
| 시간대 | KST (Asia/Seoul) |
| Paper trading | 미지원 |

## Signature

```python
async def modify_order(
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
    account: AccountSummary | None = None,
) -> ModifyOrderResponse: ...
```

## Parameters

첫 positional 인자로 다음을 전달할 수 있습니다:

- `OpenOrder` — `get_open_orders()` 결과를 그대로 (권장, `correlation_key` 자동 전파).
- `ProviderOrderRef`, `str`(order_id), 또는 legacy `ModifyOrderRequest`.

keyword-only:

- **amendment** (`OrderAmendment | None`) — 미리 만들어 둔 변경 명세. 생략 시 `quantity`/`limit_price`/`order_type`로 구성합니다.
- **quantity**, **limit_price**, **stop_price**, **order_type** — 변경할 필드만.
- **correlation_key** / **origin_org_no** / **branch_no** — KIS 원주문 매칭.
- **account** — 생략 시 기본 계좌.

## Returns

`ModifyOrderResponse`:

| 필드 | 타입 |
|---|---|
| `acknowledgement` | `OrderAcknowledgement` (`state=ACKNOWLEDGED`) |

## Example

```python
import asyncio
from decimal import Decimal

from kxt import KISClient, OrderType


async def main() -> None:
    async with KISClient(
        app_key="<APP_KEY>",
        app_secret="<APP_SECRET>",
        account_no="<CANO>",
        account_product_code="<ACNT_PRDT_CD>",
    ) as client:
        opens = await client.get_open_orders()
        target = opens.orders[0]
        response = await client.modify_order(
            target,
            quantity=Decimal("1"),
            limit_price=Decimal("70500"),
            order_type=OrderType.LIMIT,
        )
        ack = response.acknowledgement
        print(f"new_order_id={ack.order_ref.order_id} state={ack.state}")


asyncio.run(main())
```

## Sample response

```python
from datetime import datetime, timezone, timedelta
from kxt import (
    ModifyOrderResponse,
    OrderAcknowledgement,
    OrderLifecycleState,
    ProviderOrderRef,
)

KST = timezone(timedelta(hours=9))
ModifyOrderResponse(
    acknowledgement=OrderAcknowledgement(
        order_ref=ProviderOrderRef(
            provider="kis",
            order_id="0000000125",
            original_order_id="0000000123",
            account_id="12345678",
        ),
        state=OrderLifecycleState.ACKNOWLEDGED,
        occurred_at=datetime(2025, 4, 14, 9, 36, tzinfo=KST),
    ),
)
```

## Notes

- **정정 결과는 새 주문**입니다. KIS가 부여하는 정정 식별자가 `order_ref.order_id`로 오고, 원주문은 `original_order_id`로 보존됩니다.
- **비어 있는 정정은 의미가 없습니다** — `quantity` 또는 `limit_price` 중 하나는 반드시 채워 전달하세요.
- **`correlation_key`** 누락 시 일부 정정이 매칭되지 않을 수 있습니다. `OpenOrder`를 그대로 positional 인자로 넘기면 자동 전파됩니다.

## KIS specifics

- **원본 엔드포인트**: `TTTC0803U` (정정·취소).
- **`RVSE_CNCL_DVSN_CD`**: 정정은 `01`.
- **Rate limit 버킷**: 주문.

## Common pitfalls

- **수량 증가 정정**: KIS는 일반적으로 잔량 범위 내에서만 정정을 허용합니다. 늘리려면 신규 주문(`submit_order`)을 사용하세요.
- **이미 체결된 주문에 정정 시도**: 거부됩니다.
- **재시도 멱등성**: 멱등 키가 없습니다.

## See also

- [submit_order](submit-order.md)
- [cancel_order](cancel-order.md)
- [get_open_orders](../account/get-open-orders.md)
- [Schemas](../../reference/schemas.md)
