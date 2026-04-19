# Quickstart

이 문서는 `kxt`가 설치되어 있고 KIS 앱키·앱시크릿이 발급되어 있다는 전제에서 시작합니다. 설정을 먼저 끝내려면 [Installation](installation.md)과 [Authentication](authentication.md)을 먼저 읽어주세요.

이번 예제에서는 삼성전자(`005930`)의 최근 영업일 5개 일봉을 가져와 출력합니다.

## Complete example

아래 스크립트를 `quickstart.py`로 저장합니다. `<APP_KEY>`와 `<APP_SECRET>`은 본인의 KIS OpenAPI 자격증명으로 대체하세요. 자격증명을 어떤 경로로 보관·로딩할지는 호출자가 결정합니다.

```python
# quickstart.py
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
            start=today - timedelta(days=14),
            end=today,
        )

        print(f"timeframe={response.timeframe} adjusted={response.adjusted}")
        print(f"{'date':<12} {'open':>8} {'high':>8} {'low':>8} {'close':>8} {'volume':>12}")
        for bar in response.bars[-5:]:
            print(
                f"{bar.opened_at.date().isoformat():<12} "
                f"{bar.open:>8} {bar.high:>8} {bar.low:>8} {bar.close:>8} "
                f"{bar.volume:>12}"
            )


if __name__ == "__main__":
    asyncio.run(main())
```

실행:

```bash
python quickstart.py
```

## Expected output

실제 값은 영업일에 따라 다르지만, 형태는 아래와 같습니다.

```text
timeframe=day adjusted=True
date             open     high      low    close       volume
2025-04-08      71200    71800    70900    71500     12345678
2025-04-09      71500    72300    71300    72100     11112222
2025-04-10      72100    72400    71700    71900      9988776
2025-04-11      71900    72000    70800    70900     15556677
2025-04-14      70900    71400    70500    71000     10203040
```

## What happened

1. `KISClient`가 컨텍스트 매니저로 들어가며 내부 트랜스포트(HTTP 세션, 토큰)가 준비됩니다.
2. `get_bars(...)`는 종목 코드 문자열(`symbol`)을 첫 인자로 받고, `timeframe`·`start`·`end` 같은 옵션을 키워드 인자로 받습니다.
3. `get_bars(...)`는 KIS 일봉 엔드포인트(`FHKST03010100`)를 호출하고 응답을 `Bar` 튜플로 정규화합니다.
4. 컨텍스트를 빠져나오면 HTTP 커넥션이 반환됩니다.

## Same call via CLI

라이브러리와 동일한 결과를 CLI로도 얻을 수 있습니다. CLI는 `KIS_APP_KEY` / `KIS_APP_SECRET` 환경변수를 사용합니다 ([Authentication](authentication.md) 참조).

```bash
kxt bars 005930 --provider kis --timeframe day \
  --start 2025-04-01 --end 2025-04-14
```

## Next steps

- [get_bars 레퍼런스](../unified-api/market-data/get-bars.md) — 파라미터와 KIS 특이사항.
- [Pagination](pagination.md) — 기간이 길 때 커서가 어떻게 움직이는지.
- [Errors](errors.md) — 실패 처리 패턴.
