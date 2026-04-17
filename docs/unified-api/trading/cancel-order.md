# cancel_order

지정한 미체결 주문을 취소합니다. 부분 취소(`quantity`)와 전량 취소(`cancel_all=True`) 모두 지원합니다.

## At a glance

| 항목 | 값 |
|---|---|
| 인증 필요 | 예 (KIS 앱키/시크릿 + 계좌) |
| 데이터 타입 | 취소 ack |
| 스트리밍 | 후속 상태는 [`stream_order_events`](../streaming/stream-order-events.md) |
| 계좌 컨텍스트 | `KISClient` 기본 계좌 권장 |
| 시간대 | KST (Asia/Seoul) |
| Paper trading | 미지원 |

## Signature

```python
async def cancel_order(
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
    account: AccountSummary | None = None,
) -> CancelOrderResponse: ...
```

## Parameters

첫 positional 인자로 다음 중 하나를 전달할 수 있습니다 (편의용):

- `OpenOrder` — `get_open_orders()`가 반환한 그대로 넘기면 `order_ref`와 `correlation_key`가 자동 추출됩니다 (권장).
- `ProviderOrderRef` — `order_ref`만.
- `str` — `order_id` 문자열만 (correlation 정보 없음).
- `CancelOrderRequest` — legacy power-user 경로.

keyword-only 파라미터:

- **order_id** (`str | None`) — 원주문 번호 (ODNO).
- **order_ref** (`ProviderOrderRef | None`) — 원주문 식별.
- **quantity** (`Decimal | int | str | None`) — 부분 취소 수량. `cancel_all=True`이면 무시.
- **cancel_all** (`bool`, 기본 `True`) — 잔량 전체 취소.
- **correlation_key** (`OrderCorrelationKey | None`) — KIS 원주문 매칭 묶음.
- **origin_org_no** / **branch_no** (`str | None`) — `correlation_key`를 직접 만들지 않고 원 필드만 넘길 때 사용.
- **account** (`AccountSummary | None`) — 생략 시 기본 계좌.

## Returns

`CancelOrderResponse`:

| 필드 | 타입 |
|---|---|
| `acknowledgement` | `OrderAcknowledgement` (`state=CANCELED`) |

## Example

가장 자연스러운 사용 — 열린 주문을 그대로 넘기기:

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
        opens = await client.get_open_orders()
        for order in opens.orders:
            response = await client.cancel_order(order)
            print(order.order_ref.order_id, "->", response.acknowledgement.state)


asyncio.run(main())
```

`order_id`만 있을 때:

```python
await client.cancel_order(order_id="0000000123", origin_org_no="01234")
```

## Sample response

```python
from datetime import datetime, timezone, timedelta
from kxt import (
    CancelOrderResponse,
    OrderAcknowledgement,
    OrderLifecycleState,
    ProviderOrderRef,
)

KST = timezone(timedelta(hours=9))
CancelOrderResponse(
    acknowledgement=OrderAcknowledgement(
        order_ref=ProviderOrderRef(provider="kis", order_id="0000000124", original_order_id="0000000123", account_id="12345678"),
        state=OrderLifecycleState.CANCELED,
        occurred_at=datetime(2025, 4, 14, 9, 35, tzinfo=KST),
    ),
)
```

## Notes

- **취소도 KIS 입장에서는 새 주문**입니다. ack의 `order_ref.order_id`는 취소 자체의 식별자이며, 원주문 식별은 `original_order_id`에 보존됩니다.
- **`correlation_key`는 강력 권장**. KIS는 원주문을 `(주문번호, 영업점 코드)` 같은 묶음으로 식별합니다. `OpenOrder`를 그대로 전달하면 자동으로 채워집니다.
- **`cancel_all=False`로 부분 취소** 시 `quantity`가 필요합니다.

## KIS specifics

- **원본 엔드포인트**: `TTTC0803U` (정정·취소).
- **`RVSE_CNCL_DVSN_CD`**: 취소는 `02`.
- **Rate limit 버킷**: 주문.

## Common pitfalls

- **이미 체결된 주문에 취소 호출**: KIS가 거부합니다. 호출 전 [`get_open_orders`](../account/get-open-orders.md)로 잔량을 확인하세요.
- **`origin_org_no` 누락**: 매칭이 실패할 수 있습니다. `OpenOrder`를 그대로 넘기세요.
- **재시도 멱등성**: 동일 취소를 여러 번 보내면 중복 시도로 거부될 수 있습니다.

## See also

- [submit_order](submit-order.md)
- [modify_order](modify-order.md)
- [get_open_orders](../account/get-open-orders.md)
- [Schemas](../../reference/schemas.md)
