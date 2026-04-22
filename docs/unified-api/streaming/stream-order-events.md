# stream_order_events

본인 계좌의 실시간 주문 라이프사이클 이벤트와 체결 알림을 단일 통합 스트림으로 받습니다. KIS WebSocket 채널 `H0STCNI0`을 사용하며 HTS ID 기반 구독이 필요합니다.

이 메서드는 `OrderAcceptedEvent`, `OrderAmendAckEvent`, `OrderCancelAckEvent`, `OrderRejectedEvent`, `FillNotificationEvent` 다섯 종류 이벤트를 한 이터레이터에서 yields합니다. 자체 분류가 필요한 경우 [`stream_order_updates`](stream-order-updates.md)·[`stream_fill_updates`](stream-fill-updates.md) 별칭을 사용하세요.

## At a glance

| 항목 | 값 |
|---|---|
| 인증 필요 | 예 (KIS 앱키/시크릿 + HTS ID) |
| 데이터 타입 | 라이프사이클 이벤트 + 체결 통보 통합 스트림 |
| 스트리밍 | WebSocket |
| 계좌 컨텍스트 | 권장 (`AccountSummary`로 식별 보강) |
| 시간대 | KST (Asia/Seoul) |
| Paper trading | 미지원 |

## Signature

```python
async def stream_order_events(
    request: OrderEventsStreamRequest | None = None,
    /,
    *,
    hts_id: str | None = None,
    account_no: str | None = None,
    account_product_code: str | None = None,
    account: AccountSummary | None = None,
) -> AsyncIterator[
    OrderAcceptedEvent
    | OrderAmendAckEvent
    | OrderCancelAckEvent
    | OrderRejectedEvent
    | FillNotificationEvent
]: ...
```

## Parameters

- **hts_id** (`str | None`) — HTS 사용자 ID. 미지정 시 `KISClient(hts_id=...)` 기본값을 사용. 둘 다 비면 `KXTUnsupportedError`.
- **account_no** / **account_product_code** (`str | None`) — 계좌 식별. 생략 시 클라이언트 기본 계좌.
- **account** (`AccountSummary | None`) — power-user alias.

## Returns

다섯 종류 이벤트 중 하나가 yields됩니다. 모든 이벤트는 다음을 공유합니다:

| 필드 | 타입 |
|---|---|
| `order_ref` | `ProviderOrderRef` |
| `correlation_key` | `OrderCorrelationKey` |
| `symbol` | `str` |
| `side` | `OrderSide` |
| `order_type` | `OrderType` |
| `occurred_at` | `datetime` |
| `account` | `AccountSummary \| None` |

이벤트별 추가 필드 — [Schemas](../../reference/schemas.md):

- `OrderAcceptedEvent`, `OrderAmendAckEvent`: `quantity`, `limit_price`
- `OrderCancelAckEvent`: `canceled_quantity`
- `OrderRejectedEvent`: `quantity`, `reason_code`
- `FillNotificationEvent`: `price`, `quantity`

## Example

```python
import asyncio

from kxt import (
    FillNotificationEvent,
    KISClient,
    OrderAcceptedEvent,
)


async def main() -> None:
    async with KISClient(
        app_key="<APP_KEY>",
        app_secret="<APP_SECRET>",
        account_no="<CANO>",
        account_product_code="<ACNT_PRDT_CD>",
        hts_id="<HTS_ID>",
    ) as client:
        count = 0
        async for event in client.stream_order_events():
            if isinstance(event, FillNotificationEvent):
                print("FILL", event.order_ref.order_id, event.price, event.quantity)
            elif isinstance(event, OrderAcceptedEvent):
                print("ACCEPTED", event.order_ref.order_id, event.quantity)
            else:
                print(type(event).__name__, event.order_ref.order_id)
            count += 1
            if count >= 5:
                break


asyncio.run(main())
```

## Sample event

```python
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from kxt import (
    FillNotificationEvent,
    OrderCorrelationKey,
    OrderSide,
    OrderType,
    ProviderOrderRef,
)

KST = timezone(timedelta(hours=9))
ref = ProviderOrderRef(provider="kis", order_id="0000000123", account_id="12345678")
FillNotificationEvent(
    order_ref=ref,
    correlation_key=OrderCorrelationKey(order_ref=ref, origin_org_no="01234"),
    symbol="005930",
    side=OrderSide.BUY,
    order_type=OrderType.LIMIT,
    occurred_at=datetime(2025, 4, 14, 9, 30, 5, tzinfo=KST),
    price=Decimal("69950"),
    quantity=Decimal("10"),
)
```

## Notes

- **HTS ID는 KIS의 실시간 통보 구독 키**입니다. 일반 사용자 ID와 동일합니다.
- **PINGPONG**은 내부에서 자동 응답됩니다.
- **장 시작 전 구독**은 가능하나 이벤트는 장중에 발생합니다.
- **타임존은 KST**입니다.

## KIS specifics

- **WebSocket TR_ID**: `H0STCNI0` (실시간 체결 통보).
- **구독 메시지**: 자동 생성. `tr_key`로 HTS ID가 사용됩니다.
- **승인키**: 첫 구독 시 자동.

## Common pitfalls

- **`hts_id` 누락**: `KXTUnsupportedError`. 클라이언트 또는 request 어느 쪽이라도 채워야 합니다.
- **다섯 이벤트 타입 분기 누락**: `isinstance` 분기를 빠짐없이 두거나, 분류된 별칭 메서드(`stream_order_updates`/`stream_fill_updates`)를 쓰세요.
- **세션 공유 가정**: 다른 종목의 거래 스트림과 동일 WebSocket을 공유하지 않습니다.

## See also

- [stream_order_updates](stream-order-updates.md) — 체결 제외 라이프사이클 별칭.
- [stream_fill_updates](stream-fill-updates.md) — 체결 전용 별칭.
- [submit_order](../trading/submit-order.md)
- [Schemas](../../reference/schemas.md)
- [KIS provider](../../providers/kis.md)
