# get_market_calendar

KIS 국내시장 휴장일/거래일 캘린더를 조회합니다. 다운스트림 앱은 이 결과로 **시장 휴장일**, **개장일이지만 봉 데이터가 없는 상황**, **프로바이더 오류**를 구분할 수 있습니다.

## Signature

```python
async def get_market_calendar(
    start: date,
    end: date,
    *,
    market: str = "KRX",
) -> MarketCalendarResponse: ...

async def is_market_open(
    target_date: date,
    *,
    market: str = "KRX",
) -> MarketCalendarDay: ...
```

## Returns

`MarketCalendarResponse`:

| 필드 | 타입 | 설명 |
|---|---|---|
| `market` | `str` | 현재 KIS 구현은 `"KRX"` |
| `start` / `end` | `date` | 요청 범위 |
| `days` | `tuple[MarketCalendarDay, ...]` | 날짜 오름차순 캘린더 행 |

`MarketCalendarDay`:

| 필드 | KIS 필드 | 타입 |
|---|---|---|
| `date` | `bass_dt` | `date` |
| `business_day` | `bzdy_yn` | `bool | None` |
| `trading_day` | `tr_day_yn` | `bool | None` |
| `open_day` / `is_open` | `opnd_yn` | `bool | None` |
| `settlement_day` | `sttl_day_yn` | `bool | None` |
| `raw` | 원본 행 | `dict[str, object] | None` |

## Example

```python
from datetime import date

from kxt import KISClient

async with KISClient(app_key="<APP_KEY>", app_secret="<APP_SECRET>") as client:
    calendar = await client.get_market_calendar(date(2025, 1, 1), date(2025, 1, 10))
    today = await client.is_market_open(date.today())
    if today.is_open is False:
        print("KRX closed")
```

## Notes

- `get_market_calendar()`는 KIS `chk-holiday` 엔드포인트(`CTCA0903R`)를 사용합니다.
- `is_market_open()`은 불리언이 아니라 `MarketCalendarDay`를 반환합니다. 행이 없으면 해당 날짜와 `None` 상태를 담아 반환해 미확인 상태를 보존합니다.
- 프로바이더 실패는 예외로 전파됩니다. 실패를 `False`로 바꾸지 않습니다.
- 캘린더는 `get_market_status()`와 다릅니다. `get_market_status()`는 현재 시세 payload에서 시장 단계를 파생하고, 캘린더는 날짜별 휴장/개장 여부를 조회합니다.
- `get_bars()`의 빈 응답은 휴장을 의미하지 않습니다. 다운스트림은 필요한 기간의 캘린더를 자체 캐시에 저장한 뒤, 개장일인데 봉이 비어 있는 경우를 별도 데이터 공백으로 처리하세요.
