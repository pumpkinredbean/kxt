# stream_fill_updates

[`stream_order_events`](stream-order-events.md)의 체결 전용 별칭입니다. 라이프사이클 이벤트는 걸러내고 체결만 `FillEvent`로 yields합니다. 체결과 라이프사이클을 같이 받으려면 통합 메서드를 직접 사용하세요.

## At a glance

| 항목 | 값 |
|---|---|
| 인증 필요 | 예 (KIS 앱키/시크릿 + HTS ID) |
| 데이터 타입 | 체결 이벤트 (`FillEvent`) |
| 스트리밍 | WebSocket (`stream_order_events`와 채널 공유) |
| 계좌 컨텍스트 | 권장 |
| 시간대 | KST (Asia/Seoul) |
| Paper trading | 미지원 |

## Signature

```python
async def stream_fill_updates(
    request: FillUpdatesStreamRequest | None = None,
    /,
    *,
    hts_id: str | None = None,
    account_no: str | None = None,
    account_product_code: str | None = None,
    account: AccountSummary | None = None,
) -> AsyncIterator[FillEvent]: ...
```

## Parameters

- **hts_id** (`str | None`) — HTS 사용자 ID. 미지정 시 `KISClient(hts_id=...)` 기본값 사용. 둘 다 비면 `KXTUnsupportedError`.
- **account_no** / **account_product_code** (`str | None`) — 생략 시 클라이언트 기본 계좌.
- **account** (`AccountSummary | None`) — power-user alias.

## Returns

`AsyncIterator[FillEvent]`:

| 필드 | 타입 |
|---|---|
| `report` | `ExecutionReport` |
| `symbol` | `str` |

`ExecutionReport` 필드:

| 필드 | 타입 | 설명 |
|---|---|---|
| `execution_id` | `str \| None` | 체결 식별 (현재 별칭에서는 `None`) |
| `order_ref` | `ProviderOrderRef` | 원주문 식별 |
| `occurred_at` | `datetime` | 체결 시각 (KST) |
| `price` | `Decimal` | 체결가 |
| `quantity` | `Decimal` | 체결 수량 |

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
        hts_id="<HTS_ID>",
    ) as client:
        count = 0
        async for fill in client.stream_fill_updates():
            r = fill.report
            print("FILL", fill.symbol, r.order_ref.order_id, r.price, r.quantity)
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
    ExecutionReport,
    FillEvent,
    ProviderOrderRef,
)

KST = timezone(timedelta(hours=9))
FillEvent(
    report=ExecutionReport(
        execution_id=None,
        order_ref=ProviderOrderRef(provider="kis", order_id="0000000123", account_id="12345678"),
        occurred_at=datetime(2025, 4, 14, 9, 30, 5, tzinfo=KST),
        price=Decimal("69950"),
        quantity=Decimal("10"),
    ),
    symbol="005930",
)
```

## Notes

- **`execution_id`는 항상 `None`**입니다. 체결 고유 식별이 필요하면 `(order_ref.order_id, occurred_at, price, quantity)` 조합으로 dedup하세요.
- **부분 체결도 별도 이벤트**로 도착합니다. 누적 처리는 호출자 책임입니다.
- **라이프사이클은 yields하지 않습니다.**

## KIS specifics

- **WebSocket TR_ID**: `H0STCNI0`.

## Common pitfalls

- **`execution_id` 의존**: `None`입니다.
- **라이프사이클까지 받으려는 시도**: `stream_order_events`를 사용하세요.

## See also

- [stream_order_events](stream-order-events.md)
- [stream_order_updates](stream-order-updates.md)
- [submit_order](../trading/submit-order.md)
- [Schemas](../../reference/schemas.md)
