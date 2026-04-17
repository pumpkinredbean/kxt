# get_bars

지정한 종목의 OHLCV K-line(일·주·월·년·분 단위)을 가져옵니다. 차트 렌더링, 지표 계산, 백테스트 데이터 수집의 기본 블록입니다. 최근 조회는 당일 미완성 봉을 포함할 수 있으며, KIS는 일봉 계열과 분봉 계열에 서로 다른 엔드포인트를 사용합니다.

## At a glance

| 항목 | 값 |
|---|---|
| 인증 필요 | 예 (KIS 앱키/시크릿) |
| 데이터 타입 | 시계열 OHLCV |
| 스트리밍 | 해당 없음 (분봉 실시간이 필요하면 [`stream_trades`] 기반 집계 권장) |
| 계좌 컨텍스트 | 불필요 |
| 시간대 | KST (Asia/Seoul) |
| Paper trading | 미지원 (KIS 샌드박스 미연결) |

[`stream_trades`]: ../streaming/stream-trades.md

## Signature

```python
async def get_bars(
    symbol: str | InstrumentRef | BarsRequest,
    /,
    **kwargs,
) -> BarsResponse: ...
```

기본 호출 형태는 종목 코드 문자열(`symbol`)을 첫 위치인자로 넘기고 `timeframe` 등 나머지 파라미터를 키워드로 전달합니다. 베뉴/마켓 세그먼트 같은 추가 컨텍스트가 필요하면 `InstrumentRef`를, 모든 필드를 명시적으로 묶고 싶으면 `BarsRequest`를 같은 자리에 넘길 수 있습니다.

## Parameters

`BarsRequest` 필드 기준입니다 (느슨한 호출 형태에서는 `symbol` + 나머지 키워드 인자가 같은 의미를 갖습니다).

- **symbol** (`str`) *required* — 종목 코드. 예: `"005930"` (삼성전자). 내부적으로 `InstrumentRef(symbol=...)`로 정규화됩니다.
- **timeframe** (`str | BarTimeframe`) *required* — 봉 주기. 지원하는 값:
    - 분봉: `"1m"`, `"3m"`, `"5m"`, `"10m"`, `"15m"`, `"30m"`, `"60m"` (내부적으로 1분 원천을 집계)
    - `"day"`, `"week"`, `"month"`, `"year"`
- **start** (`date | datetime | None`) — 조회 시작 시각. 미지정이면 프로바이더 기본값(최신 구간).
- **end** (`date | datetime | None`) — 조회 종료 시각.
- **adjusted** (`bool`, 기본 `True`) — 수정주가 적용 여부 (일봉 계열에서만 의미).
- **session** (`SessionType | None`) — 세션 필터. 현재 KIS 구현은 정규장(`REGULAR`) 기준만 지원.

## Returns

`BarsResponse` — [BarsResponse 스키마](../../reference/schemas.md#barsresponse) 참조.

핵심 필드:

| 필드 | 타입 | 설명 |
|---|---|---|
| `timeframe` | `str` | 요청한 정규화 문자열 (예: `"day"`, `"5m"`) |
| `adjusted` | `bool` | 수정주가 적용 여부 |
| `bars` | `tuple[Bar, ...]` | 시계열 봉. 시간 오름차순이 기본 |
| `cursor` | `BarCursor \| None` | 연속 조회용 커서 ([Pagination](../../getting-started/pagination.md) 참조) |

`Bar` 필드 — [Bar 스키마](../../reference/schemas.md#bar):

| 필드 | 타입 | 설명 |
|---|---|---|
| `opened_at` | `datetime` | KST 기준 봉 시작 시각 |
| `timeframe` | `str` | 봉 주기 (상위 응답과 동일) |
| `open` | `Decimal` | 시가 |
| `high` | `Decimal` | 고가 |
| `low` | `Decimal` | 저가 |
| `close` | `Decimal` | 종가 |
| `volume` | `Decimal` | 누적 거래량 |

## Example

삼성전자 최근 10 영업일 일봉을 받아 종가 추이를 출력합니다.

```python
import asyncio
from datetime import date, timedelta

from kxt import KISClient


async def main() -> None:
    async with KISClient(
        app_key="<APP_KEY>",
        app_secret="<APP_SECRET>",
    ) as client:
        today = date.today()
        response = await client.get_bars(
            "005930",  # 삼성전자
            timeframe="day",
            start=today - timedelta(days=21),
            end=today,
            adjusted=True,
        )

        print(f"timeframe={response.timeframe} adjusted={response.adjusted}")
        for bar in response.bars[-10:]:
            print(bar.opened_at.date(), "close=", bar.close, "volume=", bar.volume)


asyncio.run(main())
```

5분봉 버전:

```python
response = await client.get_bars(
    "000660",  # SK하이닉스
    timeframe="5m",
)
```

!!! note "Advanced: 명시적 DTO 형태"
    베뉴 힌트나 모든 필드를 한꺼번에 표현해야 하면 동일 자리에 `BarsRequest`를 넘길 수 있습니다.

    ```python
    from kxt import InstrumentRef
    from kxt.requests import BarsRequest

    response = await client.get_bars(
        BarsRequest(
            instrument=InstrumentRef(symbol="005930"),
            timeframe="day",
        )
    )
    ```

## Sample response

```python
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from kxt import BarsResponse, Bar
from kxt.requests import BarCursor

KST = timezone(timedelta(hours=9))

BarsResponse(
    timeframe="day",
    adjusted=True,
    bars=(
        Bar(
            opened_at=datetime(2025, 4, 10, 0, 0, tzinfo=KST),
            timeframe="day",
            open=Decimal("72100"),
            high=Decimal("72400"),
            low=Decimal("71700"),
            close=Decimal("71900"),
            volume=Decimal("9988776"),
        ),
        Bar(
            opened_at=datetime(2025, 4, 11, 0, 0, tzinfo=KST),
            timeframe="day",
            open=Decimal("71900"),
            high=Decimal("72000"),
            low=Decimal("70800"),
            close=Decimal("70900"),
            volume=Decimal("15556677"),
        ),
    ),
    cursor=BarCursor(next_opened_at=datetime(2025, 4, 11, 0, 0, tzinfo=KST)),
)
```

## Notes

- **타임존은 KST**입니다. UTC로 변환하려면 `bar.opened_at.astimezone(timezone.utc)`를 사용하세요.
- **장중 마지막 봉은 미완성**일 수 있습니다. 특히 분봉은 현재 진행 중인 봉이 포함됩니다.
- **KRX 휴장일**은 데이터 공백으로 나타납니다. 인접 봉 사이 간격으로 감지 가능합니다.
- **가격은 `Decimal`**입니다. `float`로 변환하면 정밀도가 손실될 수 있습니다.
- **수정주가(`adjusted`)**는 일봉 계열에만 실질적 영향이 있습니다. 분봉 집계는 내부적으로 1분 원천을 합산한 것이라 수정주가 플래그가 무의미합니다.
- **분봉 timeframe**은 내부적으로 1분봉을 집계해 구성됩니다. 따라서 `5m`은 연속 5개의 1분봉 합산과 동일한 OHLCV입니다.

## KIS specifics

- **원본 엔드포인트**
    - 일/주/월/년봉: `FHKST03010100` (국내주식 기간별 시세)
    - 당일 분봉: `FHKST03010200` (주식 당일 분봉조회)
    - 과거 분봉: `FHKST03010230` (주식 일별 분봉조회)
- **Rate limit 버킷**: 시세 조회. [Rate limits](../../getting-started/rate-limits.md) 참조.
- **지원 범위**: 국내주식(장내·코스닥). 해외주식·파생은 이번 슬라이스에서 미연결.
- **KIS 공식 문서**: <https://apiportal.koreainvestment.com/apiservice>
- `response.cursor.next_opened_at`은 이번 응답에서 마지막으로 받은 봉의 시작 시각입니다. 다음 호출에서 `end`를 이 값 직전으로 이동시켜 연속 조회합니다.

## Common pitfalls

- **`timeframe` 생략**: `timeframe`은 필수 키워드 인자입니다. 종목 코드만 넘긴 채 `client.get_bars("005930")`로 호출하면 `KXTValidationError`가 발생합니다.
- **`interval_minutes`에 의존**: 내부 표현으로 존재하지만 공개 계약이 아닙니다. 분봉 주기는 반드시 `"5m"` 같은 `timeframe` 문자열로 표현하세요.
- **넓은 기간을 한 번에**: KIS는 호출당 반환 개수가 제한적입니다. 1년치 일봉·분봉을 한 번에 모두 받지 못할 수 있습니다. [Pagination](../../getting-started/pagination.md)의 커서 패턴을 사용하세요.
- **경계 중복**: 연속 조회 시 인접 페이지 경계 봉이 중복될 수 있습니다. `opened_at` 기준 dedup을 권장합니다.
- **UTC 혼용**: `start`/`end`를 `datetime`으로 넘길 때 타임존이 없으면 KST로 해석되는지 UTC로 해석되는지 모호해질 수 있습니다. 명시적으로 tz-aware `datetime`을 넘기거나 `date` 객체를 사용하세요.

## See also

- [get_quote](get-quote.md) — 최근 체결 스냅샷.
- [Pagination](../../getting-started/pagination.md)
- [Errors](../../getting-started/errors.md)
- [Rate limits](../../getting-started/rate-limits.md)
- [KIS provider](../../providers/kis.md)
