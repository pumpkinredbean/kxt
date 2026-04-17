# get_recent_trades

지정한 종목의 당일 체결 프린트(틱)를 시간 역순으로 가져옵니다. 짧은 시간 단위 흐름 분석이나 라이브 스트림과 백필을 결합한 데이터 파이프라인에 사용합니다.

## At a glance

| 항목 | 값 |
|---|---|
| 인증 필요 | 예 (KIS 앱키/시크릿) |
| 데이터 타입 | 체결 프린트 시퀀스 |
| 스트리밍 | 별도 메서드 ([`stream_trades`](../streaming/stream-trades.md)) |
| 계좌 컨텍스트 | 불필요 |
| 시간대 | KST (Asia/Seoul) |
| Paper trading | 미지원 |

## Signature

```python
async def get_recent_trades(
    symbol: str | InstrumentRef | RecentTradesRequest,
    /,
) -> RecentTradesResponse: ...
```

기본 형태는 종목 코드 문자열을 첫 위치인자로 넘기는 것입니다. `start`/`end`/`limit` 같은 옵션을 함께 묶고 싶으면 같은 자리에 `RecentTradesRequest`를 넘기세요.

## Parameters

- **symbol** (`str`) *required* — 종목 코드. 예: `"005930"`. 내부적으로 `InstrumentRef(symbol=...)`로 정규화됩니다.
- 옵션(`start`, `end`, `limit`, `session`)은 `RecentTradesRequest`로 호출할 때만 의미가 있습니다.
    - **start** (`date | datetime | None`) — 조회 시작 시각. 현재 KIS 구현은 **당일** 범위만 허용합니다.
    - **end** (`date | datetime | None`) — 조회 종료 시각. 당일 범위만 허용.
    - **limit** (`int`, 기본 `100`) — 최대 반환 개수. `1` 이상.
    - **session** (`SessionType | None`) — 세션 필터. 정규장만 지원.

## Returns

`RecentTradesResponse`:

| 필드 | 타입 | 설명 |
|---|---|---|
| `trades` | `tuple[TradePrint, ...]` | 체결 프린트. 시간 오름차순 |

`TradePrint` 필드 — [Schemas](../../reference/schemas.md#trade-tradeprint):

| 필드 | 타입 | 설명 |
|---|---|---|
| `occurred_at` | `datetime` | 체결 시각 (KST) |
| `price` | `Decimal` | 체결가 |
| `quantity` | `Decimal` | 체결 수량 |
| `ask_price` | `Decimal \| None` | 동시각 매도호가 (가용 시) |
| `bid_price` | `Decimal \| None` | 동시각 매수호가 (가용 시) |

## Example

```python
import asyncio

from kxt import KISClient


async def main() -> None:
    async with KISClient(
        app_key="<APP_KEY>",
        app_secret="<APP_SECRET>",
    ) as client:
        response = await client.get_recent_trades("005930")
        for trade in response.trades[-5:]:
            print(trade.occurred_at.time(), trade.price, trade.quantity)


asyncio.run(main())
```

!!! note "Advanced: 옵션을 묶어 호출"
    `limit`이나 시간 범위를 함께 지정하려면 `RecentTradesRequest`를 같은 자리에 넘깁니다.

    ```python
    from kxt import InstrumentRef
    from kxt.requests import RecentTradesRequest

    response = await client.get_recent_trades(
        RecentTradesRequest(
            instrument=InstrumentRef(symbol="005930"),
            limit=20,
        )
    )
    ```

## Sample response

```python
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from kxt import RecentTradesResponse, TradePrint

KST = timezone(timedelta(hours=9))

RecentTradesResponse(
    trades=(
        TradePrint(
            occurred_at=datetime(2025, 4, 14, 11, 29, 58, tzinfo=KST),
            price=Decimal("71000"),
            quantity=Decimal("12"),
        ),
        TradePrint(
            occurred_at=datetime(2025, 4, 14, 11, 29, 59, tzinfo=KST),
            price=Decimal("71100"),
            quantity=Decimal("3"),
        ),
    ),
)
```

## Notes

- **당일 범위만 지원**합니다. 과거 일자를 지정하면 `KXTUnsupportedError`가 발생합니다.
- **정렬**은 시간 오름차순입니다(`trades[-1]`이 가장 최근).
- **dedup**은 내부에서 `(시각, 가격, 수량, 시퀀스)` 튜플 기준으로 처리됩니다.
- **타임존은 KST**입니다.

## KIS specifics

- **원본 엔드포인트**: `FHPST01060000` (국내주식 시간대별 체결).
- **Rate limit 버킷**: 시세 조회.
- **지원 범위**: 국내주식 동일 영업일 정규장.
- **KIS 공식 문서**: <https://apiportal.koreainvestment.com/apiservice>

## Common pitfalls

- **과거 일자 조회**: 지원되지 않습니다. 과거 데이터가 필요하면 분봉(`get_bars` minute)으로 대체하세요.
- **`limit`만 신뢰**: KIS 페이지 응답 한계로 큰 `limit`은 여러 페이지 누적 후 잘릴 수 있습니다.
- **장 시작 직후**: 데이터가 비어 있을 수 있습니다.

## See also

- [stream_trades](../streaming/stream-trades.md) — 실시간 체결.
- [get_bars](get-bars.md) — 분봉 집계.
- [Schemas](../../reference/schemas.md#trade-tradeprint)
- [KIS provider](../../providers/kis.md)
