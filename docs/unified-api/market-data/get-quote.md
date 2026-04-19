# get_quote

지정한 종목의 최근 체결가 스냅샷을 가져옵니다. 단일 호출로 마지막 체결가, 시가/고가/저가, 전일 대비 변동, 누적 거래량을 받을 수 있어 대시보드와 알림용 가벼운 폴링에 적합합니다. 호가창 깊이가 필요하면 [`get_orderbook`](get-orderbook.md)을 사용하세요.

## At a glance

| 항목 | 값 |
|---|---|
| 인증 필요 | 예 (KIS 앱키/시크릿) |
| 데이터 타입 | 단일 시점 시세 스냅샷 |
| 스트리밍 | 해당 없음 (실시간 체결은 [`stream_trades`](../streaming/stream-trades.md)) |
| 계좌 컨텍스트 | 불필요 |
| 시간대 | KST (Asia/Seoul) |
| Paper trading | 미지원 |

## Signature

```python
async def get_quote(symbol: str | InstrumentRef | QuoteRequest, /) -> QuoteResponse: ...
```

기본 형태는 종목 코드 문자열을 첫 위치인자로 넘기는 것입니다. 베뉴/세그먼트 컨텍스트가 필요하면 `InstrumentRef`를, 모든 필드를 명시적으로 묶고 싶으면 `QuoteRequest`를 같은 자리에 넘길 수 있습니다.

## Parameters

- **symbol** (`str`) *required* — 종목 코드. 예: `"005930"`. 내부적으로 `InstrumentRef(symbol=...)`로 정규화됩니다.
- **session** (`SessionType | None`) — 세션 필터. `QuoteRequest`로 호출하는 경우에만 의미가 있으며, 현재 KIS 구현은 정규장 기준만 지원합니다.

## Returns

`QuoteResponse` — [QuoteResponse 스키마](../../reference/schemas.md#quoterequest-quoteresponse) 참조.

| 필드 | 타입 | 설명 |
|---|---|---|
| `occurred_at` | `datetime` | 스냅샷 시각 (KST) |
| `last` | `Decimal` | 마지막 체결가 |
| `open` | `Decimal \| None` | 시가 |
| `high` | `Decimal \| None` | 고가 |
| `low` | `Decimal \| None` | 저가 |
| `previous_close` | `Decimal \| None` | 전일 종가 |
| `change` | `Decimal \| None` | 전일 대비 변동가 |
| `change_rate` | `Decimal \| None` | 전일 대비 변동률(%) |
| `volume` | `Decimal \| None` | 누적 거래량 |

## Example

```python
import asyncio

from kxt import KISClient


async def main() -> None:
    async with KISClient(
        app_key="<APP_KEY>",
        app_secret="<APP_SECRET>",
    ) as client:
        response = await client.get_quote("005930")
        print(f"last={response.last} change={response.change} ({response.change_rate}%)")


asyncio.run(main())
```

## Sample response

```python
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from kxt import QuoteResponse

KST = timezone(timedelta(hours=9))

QuoteResponse(
    occurred_at=datetime(2025, 4, 14, 11, 30, 0, tzinfo=KST),
    last=Decimal("71000"),
    open=Decimal("70900"),
    high=Decimal("71400"),
    low=Decimal("70500"),
    previous_close=Decimal("70900"),
    change=Decimal("100"),
    change_rate=Decimal("0.14"),
    volume=Decimal("10203040"),
)
```

## Notes

- **타임존은 KST**입니다.
- **장중 호출은 진행 중 시점 스냅샷**입니다. 같은 종목을 짧은 간격으로 호출하면 `last`가 변할 수 있습니다.
- **호가창 필드는 의도적으로 제외**되어 있습니다. 호가 깊이가 필요하면 `get_orderbook`을 사용하세요.
- **가격은 `Decimal`**입니다.

## KIS specifics

- **원본 엔드포인트**: `FHKST01010100` (국내주식 현재가).
- **Rate limit 버킷**: 시세 조회. [Rate limits](../../getting-started/rate-limits.md) 참조.
- **지원 범위**: 국내주식(KOSPI·KOSDAQ).
- **KIS 공식 문서**: <https://apiportal.koreainvestment.com/apiservice>

## Common pitfalls

- **호가 정보 기대**: `QuoteResponse`에는 매수/매도 호가가 포함되지 않습니다. 호가창은 별도 메서드입니다.
- **`float` 변환**: `Decimal`을 `float`으로 변환하면 정밀도가 손실될 수 있습니다.
- **휴장일 호출**: 휴장일에는 직전 영업일 스냅샷이 반환될 수 있습니다.

## See also

- [get_orderbook](get-orderbook.md) — 호가창 깊이.
- [get_recent_trades](get-recent-trades.md) — 당일 체결 프린트.
- [stream_trades](../streaming/stream-trades.md) — 실시간 체결 스트림.
- [KIS provider](../../providers/kis.md)
