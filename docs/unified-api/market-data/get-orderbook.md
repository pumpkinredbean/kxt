# get_orderbook

지정한 종목의 호가창(매수·매도 잔량 깊이) 스냅샷을 한 번에 가져옵니다. 호가 갭, 매수/매도 잔량 비율, 최우선 호가 추적 같은 분석에 사용합니다. 실시간으로 흐름을 받으려면 [`stream_orderbook`](../streaming/stream-orderbook.md)을 쓰세요.

## At a glance

| 항목 | 값 |
|---|---|
| 인증 필요 | 예 (KIS 앱키/시크릿) |
| 데이터 타입 | 호가창 스냅샷 |
| 스트리밍 | 별도 메서드 ([`stream_orderbook`](../streaming/stream-orderbook.md)) |
| 계좌 컨텍스트 | 불필요 |
| 시간대 | KST (Asia/Seoul) |
| Paper trading | 미지원 |

## Signature

```python
async def get_orderbook(symbol: str | InstrumentRef | OrderBookRequest, /) -> OrderBookResponse: ...
```

기본 형태는 종목 코드 문자열을 첫 위치인자로 넘기는 것입니다. 베뉴/세그먼트 컨텍스트가 필요하면 `InstrumentRef`를, 모든 필드를 명시적으로 묶고 싶으면 `OrderBookRequest`를 같은 자리에 넘길 수 있습니다.

## Parameters

- **symbol** (`str`) *required* — 종목 코드. 예: `"005930"`. 내부적으로 `InstrumentRef(symbol=...)`로 정규화됩니다.
- **session** (`SessionType | None`) — 세션 필터. `OrderBookRequest`로 호출하는 경우에만 의미가 있으며, 현재 KIS 구현은 정규장 기준만 지원합니다.

## Returns

`OrderBookResponse` — [OrderBookResponse 스키마](../../reference/schemas.md#orderbookresponse) 참조.

| 필드 | 타입 | 설명 |
|---|---|---|
| `occurred_at` | `datetime` | 스냅샷 시각 (KST) |
| `asks` | `tuple[QuoteLevel, ...]` | 매도 호가 레벨 (가격 오름차순) |
| `bids` | `tuple[QuoteLevel, ...]` | 매수 호가 레벨 (가격 내림차순) |
| `total_ask_quantity` | `Decimal \| None` | 총 매도 잔량 |
| `total_bid_quantity` | `Decimal \| None` | 총 매수 잔량 |

`QuoteLevel` 필드:

| 필드 | 타입 |
|---|---|
| `price` | `Decimal` |
| `quantity` | `Decimal` |

## Example

```python
import asyncio

from kxt import KISClient


async def main() -> None:
    async with KISClient(
        app_key="<APP_KEY>",
        app_secret="<APP_SECRET>",
    ) as client:
        response = await client.get_orderbook("005930")
        best_ask = response.asks[0]
        best_bid = response.bids[0]
        print(f"best ask {best_ask.price} x {best_ask.quantity}")
        print(f"best bid {best_bid.price} x {best_bid.quantity}")


asyncio.run(main())
```

## Sample response

```python
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from kxt import OrderBookResponse, QuoteLevel

KST = timezone(timedelta(hours=9))

OrderBookResponse(
    occurred_at=datetime(2025, 4, 14, 11, 30, 0, tzinfo=KST),
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

- **호가 정렬**은 `asks` 오름차순, `bids` 내림차순입니다. 인덱스 `0`이 항상 최우선입니다.
- **레벨 깊이**는 KIS 응답 한도를 그대로 따릅니다(통상 10단계).
- **타임존은 KST**입니다.
- **시점은 호출 순간**입니다. 짧은 간격으로 다시 호출하면 잔량이 크게 변동할 수 있습니다.

## KIS specifics

- **원본 엔드포인트**: `FHKST01010200` (국내주식 호가).
- **Rate limit 버킷**: 시세 조회. [Rate limits](../../getting-started/rate-limits.md) 참조.
- **지원 범위**: 국내주식(KOSPI·KOSDAQ).
- **KIS 공식 문서**: <https://apiportal.koreainvestment.com/apiservice>

## Common pitfalls

- **`asks`/`bids` 길이 가정**: 항상 같은 깊이로 오지 않을 수 있습니다. 슬라이싱 전 길이 확인을 권장합니다.
- **잔량을 정수로 가정**: 일부 종목·세션에서 소수 잔량이 가능할 수 있어 `Decimal`로 처리하세요.
- **`float` 변환**: 정밀도가 손실됩니다.

## See also

- [get_quote](get-quote.md) — 단일 시점 시세 스냅샷.
- [stream_orderbook](../streaming/stream-orderbook.md) — 실시간 호가 스트림.
- [Schemas](../../reference/schemas.md#orderbookresponse)
- [KIS provider](../../providers/kis.md)
