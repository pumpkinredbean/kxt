# get_market_status

지정한 종목 또는 시장의 현재 거래 단계(개장 전, 정규장, 단일가, 장 마감 등)를 조회합니다. 자동매매 루프의 가드, 알림 트리거, UI 상태 표시에 사용합니다.

## At a glance

| 항목 | 값 |
|---|---|
| 인증 필요 | 예 (KIS 앱키/시크릿) |
| 데이터 타입 | 시장 단계 스냅샷 |
| 스트리밍 | KIS 시장 상태 스트림 미구현 — `stream_market_status` 호출 시 `KXTUnsupportedError` |
| 계좌 컨텍스트 | 불필요 |
| 시간대 | KST (Asia/Seoul) |
| Paper trading | 미지원 |

## Signature

```python
async def get_market_status(
    symbol: str | InstrumentRef | MarketStatusRequest | None = None,
    /,
) -> MarketStatusResponse: ...
```

기본 형태는 종목 코드 문자열을 첫 위치인자로 넘기는 것입니다. 인자를 생략하면 KIS 구현은 기본 종목(삼성전자 `005930`)으로 호출하여 전체 시장 단계를 도출합니다.

## Parameters

- **symbol** (`str | None`) — 상태 조회 대상 종목 코드. 미지정 시 기본 종목(`"005930"`)이 사용됩니다.
- 옵션을 함께 묶어 호출하려면 같은 자리에 `MarketStatusRequest`를 넘길 수 있습니다.
    - **instrument** (`InstrumentRef | None`) — 종목 참조.
    - **session** (`SessionType | None`) — 세션 필터.

## Returns

`MarketStatusResponse`:

| 필드 | 타입 | 설명 |
|---|---|---|
| `phase` | `MarketPhase` | 시장 단계 (`PREOPEN`, `OPEN`, `AUCTION`, `AFTER_HOURS`, `CLOSED`, `HALTED`, `UNKNOWN`) |
| `occurred_at` | `datetime` | 상태 시각 (KST) |

## Example

```python
import asyncio

from kxt import KISClient, MarketPhase


async def main() -> None:
    async with KISClient(
        app_key="<APP_KEY>",
        app_secret="<APP_SECRET>",
    ) as client:
        response = await client.get_market_status("005930")
        print(f"phase={response.phase} at={response.occurred_at}")
        if response.phase is MarketPhase.OPEN:
            print("정규장 진행 중")


asyncio.run(main())
```

!!! note "Advanced: 명시적 DTO 형태"
    같은 자리에 `MarketStatusRequest`를 넘기면 `instrument`/`session` 등을 함께 묶어 표현할 수 있습니다.

    ```python
    from kxt import InstrumentRef
    from kxt.requests import MarketStatusRequest

    response = await client.get_market_status(
        MarketStatusRequest(instrument=InstrumentRef(symbol="005930"))
    )
    ```

## Sample response

```python
from datetime import datetime, timezone, timedelta
from kxt import MarketPhase, MarketStatusResponse

KST = timezone(timedelta(hours=9))

MarketStatusResponse(
    phase=MarketPhase.OPEN,
    occurred_at=datetime(2025, 4, 14, 11, 30, 0, tzinfo=KST),
)
```

## Notes

- **시세 payload에서 파생**합니다. 별도 시장-상태 전용 엔드포인트를 호출하지 않습니다. 따라서 시세 조회와 동일한 자격증명·rate-limit 버킷을 공유합니다.
- **phase 매핑**은 KIS 응답의 시장운영구분 필드를 정규화한 것이며, 매핑이 모호한 경우 `MarketPhase.UNKNOWN`이 반환됩니다.
- **타임존은 KST**입니다.

## KIS specifics

- **원본 엔드포인트**: `FHKST01010100` (시세 payload 재사용).
- **Rate limit 버킷**: 시세 조회.
- **지원 범위**: 국내주식 단일 종목 기준.
- **KIS 공식 문서**: <https://apiportal.koreainvestment.com/apiservice>

## Common pitfalls

- **종목 무관한 정보 가정**: KIS는 종목별 시세 payload에서 단계를 도출하므로, 거래정지 종목을 지정하면 결과가 왜곡될 수 있습니다. 일반 대형주를 사용하세요.
- **스트림 기대**: `stream_market_status`는 미구현입니다. 폴링으로 사용하세요.

## See also

- [get_quote](get-quote.md) — 같은 payload에서 가격 정보를 가져옵니다.
- [Schemas](../../reference/schemas.md)
- [KIS provider](../../providers/kis.md)
