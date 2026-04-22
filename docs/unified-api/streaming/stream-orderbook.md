# stream_orderbook

지정한 종목의 실시간 호가창 스냅샷을 비동기 이터레이터로 받습니다. KIS WebSocket 채널 `H0STASP0`을 사용합니다.

## At a glance

| 항목 | 값 |
|---|---|
| 인증 필요 | 예 (KIS 앱키/시크릿) |
| 데이터 타입 | 호가 이벤트 스트림 |
| 스트리밍 | WebSocket |
| 계좌 컨텍스트 | 불필요 |
| 시간대 | KST (Asia/Seoul) |
| Paper trading | 미지원 |

## Signature

```python
def stream_orderbook(
    symbol: str | InstrumentRef | OrderBookSubscription | OrderBookStreamRequest,
    /,
) -> AsyncIterator[OrderBookEvent]: ...
```

기본 형태는 종목 코드 문자열을 첫 위치인자로 넘기는 것입니다. 베뉴 컨텍스트가 필요하거나 옵션을 묶고 싶으면 같은 자리에 `InstrumentRef`, `OrderBookSubscription`, `OrderBookStreamRequest` 중 하나를 넘기세요.

## Parameters

- **symbol** (`str`) *required* — 구독 대상 종목 코드. 예: `"005930"`. 내부적으로 `InstrumentRef(symbol=...)`로 정규화됩니다.
- 옵션은 `OrderBookSubscription` 또는 `OrderBookStreamRequest`로 호출할 때만 의미가 있습니다.
    - **session** (`SessionType | None`, `OrderBookStreamRequest`만)

## Returns

`AsyncIterator[OrderBookEvent]`:

| 필드 | 타입 | 설명 |
|---|---|---|
| `occurred_at` | `datetime` | 이벤트 시각 (KST) |
| `symbol` | `str` | 종목 코드 |
| `asks` | `tuple[OrderBookLevel, ...]` | 매도 호가 (가격 오름차순) |
| `bids` | `tuple[OrderBookLevel, ...]` | 매수 호가 (가격 내림차순) |
| `total_ask_quantity` | `Decimal \| None` | 총 매도 잔량 |
| `total_bid_quantity` | `Decimal \| None` | 총 매수 잔량 |

`OrderBookLevel = QuoteLevel`(price/quantity).

## Example

```python
import asyncio

from kxt import KISClient


async def main() -> None:
    async with KISClient(
        app_key="<APP_KEY>",
        app_secret="<APP_SECRET>",
    ) as client:
        count = 0
        async for event in client.stream_orderbook("005930"):
            best_ask = event.asks[0]
            best_bid = event.bids[0]
            print(event.occurred_at.time(), "ask", best_ask.price, "bid", best_bid.price)
            count += 1
            if count >= 5:
                break


asyncio.run(main())
```

## Sample event

```python
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from kxt import OrderBookEvent, QuoteLevel

KST = timezone(timedelta(hours=9))
OrderBookEvent(
    occurred_at=datetime(2025, 4, 14, 11, 30, 12, tzinfo=KST),
    symbol="005930",
    asks=(
        QuoteLevel(price=Decimal("71100"), quantity=Decimal("1200")),
        QuoteLevel(price=Decimal("71200"), quantity=Decimal("3500")),
    ),
    bids=(
        QuoteLevel(price=Decimal("71000"), quantity=Decimal("2200")),
        QuoteLevel(price=Decimal("70900"), quantity=Decimal("4100")),
    ),
    total_ask_quantity=Decimal("12345"),
    total_bid_quantity=Decimal("13567"),
)
```

## Notes

- **각 이벤트는 전체 호가창 스냅샷**입니다. 증분(diff)이 아닙니다.
- **장 마감 후**는 새 이벤트가 거의 발생하지 않습니다.
- **종목별 구독**만 지원합니다.

## KIS specifics

- **WebSocket TR_ID**: `H0STASP0` (실시간 호가).
- **승인키 발급**: 첫 구독 시 자동.

## Common pitfalls

- **고빈도 처리**: 호가 변화가 잦은 대형주는 초당 다수 이벤트가 발생합니다. 다운스트림 처리에 백프레셔를 두세요.
- **`asks`/`bids` 깊이 가정**: 항상 같은 길이가 아닐 수 있습니다.

## See also

- [get_orderbook](../market-data/get-orderbook.md)
- [stream_trades](stream-trades.md)
- [Schemas](../../reference/schemas.md)
- [KIS provider](../../providers/kis.md)
