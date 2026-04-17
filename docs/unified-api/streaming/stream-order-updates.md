# stream_order_updates

[`stream_order_events`](stream-order-events.md)의 라이프사이클 전용 별칭입니다. 체결 통보(`FillNotificationEvent`)는 걸러내고 정규화된 `OrderUpdateEvent`만 yields합니다. 체결만 따로 받으려면 [`stream_fill_updates`](stream-fill-updates.md)를 사용하세요.

## At a glance

| 항목 | 값 |
|---|---|
| 인증 필요 | 예 (KIS 앱키/시크릿 + HTS ID) |
| 데이터 타입 | 정규화된 라이프사이클 이벤트 |
| 스트리밍 | WebSocket (`stream_order_events`와 채널 공유) |
| 계좌 컨텍스트 | 권장 |
| 시간대 | KST (Asia/Seoul) |
| Paper trading | 미지원 |

## Signature

```python
async def stream_order_updates(
    request: OrderUpdatesStreamRequest | None = None,
) -> AsyncIterator[OrderUpdateEvent]: ...
```

## Parameters

`OrderUpdatesStreamRequest`:

- **account** (`AccountSummary | None`) — 미지정 시 클라이언트 기본 계좌.

`hts_id`는 별칭 메서드에서 직접 받지 않습니다. `KISClient(hts_id=...)`로 미리 설정해 두어야 합니다(`stream_order_events`와 동일한 H0STCNI0 채널을 공유).

## Returns

`AsyncIterator[OrderUpdateEvent]`:

| 필드 | 타입 | 설명 |
|---|---|---|
| `order_ref` | `ProviderOrderRef` | 주문 식별 |
| `instrument` | `InstrumentRef` | 종목 |
| `state` | `OrderLifecycleState` | 정규화 상태 (`ACKNOWLEDGED`, `CANCELED`, `REJECTED` 등) |
| `occurred_at` | `datetime` | 이벤트 시각 (KST) |
| `message` | `str \| None` | 부가 메시지 |
| `filled_quantity` | `Decimal \| None` | 현재 별칭에서는 채워지지 않음 |
| `remaining_quantity` | `Decimal \| None` | 현재 별칭에서는 채워지지 않음 |

## Example

```python
import asyncio

from kxt import KISClient
from kxt.requests import OrderUpdatesStreamRequest


async def main() -> None:
    async with KISClient(
        app_key="<APP_KEY>",
        app_secret="<APP_SECRET>",
        account_no="<CANO>",
        account_product_code="<ACNT_PRDT_CD>",
        hts_id="<HTS_ID>",
    ) as client:
        count = 0
        async for update in client.stream_order_updates(OrderUpdatesStreamRequest()):
            print(update.order_ref.order_id, update.state, update.occurred_at)
            count += 1
            if count >= 5:
                break


asyncio.run(main())
```

## Sample event

```python
from datetime import datetime, timezone, timedelta
from kxt import (
    InstrumentRef,
    OrderLifecycleState,
    OrderUpdateEvent,
    ProviderOrderRef,
)

KST = timezone(timedelta(hours=9))
OrderUpdateEvent(
    order_ref=ProviderOrderRef(provider="kis", order_id="0000000123", account_id="12345678"),
    instrument=InstrumentRef(symbol="005930"),
    state=OrderLifecycleState.ACKNOWLEDGED,
    occurred_at=datetime(2025, 4, 14, 9, 30, tzinfo=KST),
)
```

## Notes

- **체결은 yields하지 않습니다.** 체결은 `stream_fill_updates`에서 받으세요.
- **수량 필드 미충전**: `filled_quantity`/`remaining_quantity`는 본 별칭에서 채우지 않습니다. 정밀 추적이 필요하면 `stream_order_events`로 통합 스트림을 받아 직접 누적하세요.
- **`hts_id`는 클라이언트 생성 시 필요**합니다.

## KIS specifics

- **WebSocket TR_ID**: `H0STCNI0` (`stream_order_events`와 동일 채널).

## Common pitfalls

- **체결 추적을 본 메서드로 시도**: 체결은 별도 별칭입니다.
- **`hts_id` 누락**: `KISClient` 인자에 누락하면 `KXTUnsupportedError`.

## See also

- [stream_order_events](stream-order-events.md) — 통합 스트림.
- [stream_fill_updates](stream-fill-updates.md) — 체결 전용.
- [Schemas](../../reference/schemas.md)
