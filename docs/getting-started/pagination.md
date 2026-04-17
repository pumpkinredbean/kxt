# Pagination

KIS OpenAPI는 호출당 반환 개수에 상한이 있고, 일부 엔드포인트는 연속 조회용 커서를 돌려줍니다. `kxt`는 이를 응답 DTO의 `cursor` 필드로 노출합니다.

## 커서의 역할

- `BarsResponse.cursor`는 마지막으로 받은 봉의 시작 시각(`next_opened_at`)을 담습니다.
- `None`이면 더 이상 이어질 데이터가 없음을 의미합니다.
- 현재 구현은 단일 호출 단위 응답을 그대로 반환하며, 기간이 넓어 한 번에 모이지 않을 경우 호출부에서 커서를 사용해 다음 요청의 `end`를 앞당기는 방식으로 이어 붙입니다.

## 커서로 이어 받기 (일봉 예)

```python
import asyncio
from datetime import date

from kxt import InstrumentRef, KISClient
from kxt.requests import BarsRequest


async def main() -> None:
    async with KISClient(app_key="...", app_secret="...") as client:
        end = date(2025, 4, 14)
        start = date(2024, 1, 1)
        collected = []

        while True:
            response = await client.get_bars(
                BarsRequest(
                    instrument=InstrumentRef(symbol="005930"),
                    timeframe="day",
                    start=start,
                    end=end,
                )
            )
            if not response.bars:
                break

            collected.extend(response.bars)
            if response.cursor is None or response.cursor.next_opened_at is None:
                break

            # 다음 페이지: 이번에 받은 가장 이른 봉 하루 전까지로 end를 옮긴다
            oldest = min(bar.opened_at.date() for bar in response.bars)
            if oldest <= start:
                break
            end = oldest

        print(f"총 {len(collected)}봉 수집")


asyncio.run(main())
```

## 자동 페이지네이션

`limit` 기반 자동 페이지네이션은 아직 구현되어 있지 않습니다. 넓은 기간 조회는 위 패턴처럼 호출부에서 커서를 따라가며 누적해야 합니다. 향후 공용 헬퍼로 승격될 예정입니다.

## 중복·순서 주의

- KIS 응답의 경계 일자는 인접 페이지에서 겹칠 수 있습니다. 누적 시 `opened_at` 기준 중복 제거를 권장합니다.
- 일반적으로 최신 → 과거 순으로 돌아옵니다. 차트 렌더링 용도라면 마지막에 한 번 `sorted(..., key=lambda b: b.opened_at)`로 재정렬하세요.

## 연관 문서

- [get_bars](../unified-api/market-data/get-bars.md)
- [Rate limits](rate-limits.md) — 루프 돌릴 때 유의할 호출 속도.
