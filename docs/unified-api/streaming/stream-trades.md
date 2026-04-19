# stream_trades

지정한 종목의 실시간 체결 프린트(틱)를 비동기 이터레이터로 받습니다. KIS WebSocket 채널 `H0STCNT0`을 사용합니다.

## At a glance

| 항목 | 값 |
|---|---|
| 인증 필요 | 예 (KIS 앱키/시크릿) |
| 데이터 타입 | 체결 이벤트 스트림 |
| 스트리밍 | WebSocket |
| 계좌 컨텍스트 | 불필요 |
| 시간대 | KST (Asia/Seoul) |
| Paper trading | 미지원 |

## Signature

```python
def stream_trades(
    symbol: str | InstrumentRef | TradeSubscription | TradeStreamRequest,
    /,
) -> AsyncIterator[TradeEvent]: ...
```

기본 형태는 종목 코드 문자열을 첫 위치인자로 넘기는 것입니다. 베뉴 컨텍스트가 필요하거나 옵션을 묶어 표현하고 싶으면 같은 자리에 `InstrumentRef`, `TradeSubscription`, `TradeStreamRequest` 중 하나를 넘기세요.

## Parameters

- **symbol** (`str`) *required* — 구독 대상 종목 코드. 예: `"005930"`. 내부적으로 `InstrumentRef(symbol=...)`로 정규화됩니다.
- 옵션은 `TradeSubscription` 또는 `TradeStreamRequest`로 호출할 때만 의미가 있습니다.
    - **scope** (`MarketScope | None`, `TradeSubscription`만) — 시장 단위 구독은 현재 KIS 슬라이스에서 미지원.
    - **session** (`SessionType | None`, `TradeStreamRequest`만)

## Returns

`AsyncIterator[TradeEvent]` — 무한 비동기 이터레이터. 각 이벤트는 다음을 가집니다.

| 필드 | 타입 | 설명 |
|---|---|---|
| `occurred_at` | `datetime` | 체결 시각 (KST) |
| `instrument` | `InstrumentRef` | 종목 |
| `price` | `Decimal` | 체결가 |
| `quantity` | `Decimal` | 체결 수량 |
| `side` | `TradeSide \| None` | 체결 측 (가용 시) |

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
        async for event in client.stream_trades("005930"):
            print(event.occurred_at.time(), event.price, event.quantity)
            count += 1
            if count >= 5:
                break


asyncio.run(main())
```

## Sample event

```python
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from kxt import InstrumentRef, TradeEvent, TradeSide

KST = timezone(timedelta(hours=9))
TradeEvent(
    occurred_at=datetime(2025, 4, 14, 11, 30, 12, tzinfo=KST),
    instrument=InstrumentRef(symbol="005930"),
    price=Decimal("71000"),
    quantity=Decimal("3"),
    side=TradeSide.BUY,
)
```

## Notes

- **무한 스트림**입니다. 호출자가 명시적으로 break/cancel 해야 종료됩니다.
- **종목별 구독**입니다. 시장 전체 구독(`scope`)은 현재 슬라이스에서 미지원이며 `KXTUnsupportedError`가 발생합니다.
- **장 마감 후**는 새 이벤트가 발생하지 않으며, 다음 개장까지 대기합니다.
- **재연결**은 내부 realtime 세션이 시도하지만, 영구적 네트워크 문제는 예외로 전파됩니다.

## KIS specifics

- **WebSocket TR_ID**: `H0STCNT0` (실시간 체결).
- **승인키 발급**: 첫 구독 시 자동으로 처리됩니다.
- **프록시**: `KXT_KIS_WS_PROXY` 환경변수가 설정되어 있으면 CLI에서 사용됩니다(SDK는 transport 옵션을 통해 별도 처리).

## Common pitfalls

- **break 없이 무한 루프**: 종료 시점을 명시적으로 두세요.
- **여러 종목 동시 구독**: 각 종목마다 별도 `stream_trades(...)` 호출이 필요합니다. 동일 세션에서 멀티플렉싱됩니다.
- **`async for` 외 반복 시도**: 이 메서드는 비동기 이터레이터입니다. 동기 컨텍스트에서는 사용할 수 없습니다.

## See also

- [get_recent_trades](../market-data/get-recent-trades.md)
- [stream_orderbook](stream-orderbook.md)
- [Schemas](../../reference/schemas.md)
- [KIS provider](../../providers/kis.md)
