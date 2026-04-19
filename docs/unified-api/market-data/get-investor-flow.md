# get_investor_flow

지정한 종목의 투자자별(개인·외국인·기관) 누적 매수/매도 흐름을 한 번에 조회합니다. 장 마감 이후 공개되는 정규장 집계입니다. 외국인 순매수 추적, 수급 보조 지표 산출에 사용합니다.

## At a glance

| 항목 | 값 |
|---|---|
| 인증 필요 | 예 (KIS 앱키/시크릿) |
| 데이터 타입 | 투자자별 일중 집계 스냅샷 |
| 스트리밍 | 해당 없음 |
| 계좌 컨텍스트 | 불필요 |
| 시간대 | KST (Asia/Seoul) |
| Paper trading | 미지원 |

## Signature

```python
async def get_investor_flow(
    symbol: str | InstrumentRef | InvestorFlowRequest,
    /,
) -> InvestorFlowResponse: ...
```

기본 형태는 종목 코드 문자열을 첫 위치인자로 넘기는 것입니다. 옵션 필드를 함께 묶고 싶으면 같은 자리에 `InvestorFlowRequest`를 넘기세요.

## Parameters

- **symbol** (`str`) *required* — 종목 코드. 예: `"005930"`. 내부적으로 `InstrumentRef(symbol=...)`로 정규화됩니다.
- 옵션은 `InvestorFlowRequest`로 호출할 때만 의미가 있습니다.
    - **start** (`date | datetime | None`) — **현재 KIS 구현은 `None`만 허용**. 값 지정 시 `KXTUnsupportedError`.
    - **end** (`date | datetime | None`) — **현재 KIS 구현은 `None`만 허용**.
    - **session** (`SessionType | None`) — `None` 또는 `SessionType.REGULAR`만 허용.

## Returns

`InvestorFlowResponse` — KIS는 한 번의 호출로 한 시점의 누적 집계 한 행만 돌려주므로, 응답도 단일 스냅샷 형태입니다.

| 필드 | 타입 | 설명 |
|---|---|---|
| `as_of_date` | `date \| None` | 집계 대상 일자 |
| `retail` | `InvestorFlowBucket` | 개인 |
| `foreign` | `InvestorFlowBucket` | 외국인 |
| `institution` | `InvestorFlowBucket` | 기관 |

`InvestorFlowBucket` 필드:

| 필드 | 타입 | 설명 |
|---|---|---|
| `buy_quantity` | `Decimal \| None` | 누적 매수 수량 |
| `sell_quantity` | `Decimal \| None` | 누적 매도 수량 |
| `net_buy_quantity` | `Decimal \| None` | 순매수 수량 |
| `buy_notional` | `Decimal \| None` | 누적 매수 대금 |
| `sell_notional` | `Decimal \| None` | 누적 매도 대금 |
| `net_buy_notional` | `Decimal \| None` | 순매수 대금 |

## Example

```python
import asyncio

from kxt import KISClient


async def main() -> None:
    async with KISClient(
        app_key="<APP_KEY>",
        app_secret="<APP_SECRET>",
    ) as client:
        response = await client.get_investor_flow("005930")
        print(f"date={response.as_of_date}")
        print(f"foreign net qty = {response.foreign.net_buy_quantity}")
        print(f"institution net notional = {response.institution.net_buy_notional}")


asyncio.run(main())
```

## Sample response

```python
from datetime import date
from decimal import Decimal
from kxt import InvestorFlowBucket, InvestorFlowResponse

InvestorFlowResponse(
    as_of_date=date(2025, 4, 14),
    retail=InvestorFlowBucket(
        buy_quantity=Decimal("1000000"),
        sell_quantity=Decimal("1100000"),
        net_buy_quantity=Decimal("-100000"),
        buy_notional=Decimal("70000000000"),
        sell_notional=Decimal("77000000000"),
        net_buy_notional=Decimal("-7000000000"),
    ),
    foreign=InvestorFlowBucket(
        buy_quantity=Decimal("500000"),
        sell_quantity=Decimal("400000"),
        net_buy_quantity=Decimal("100000"),
    ),
    institution=InvestorFlowBucket(),
)
```

## Notes

- **장 마감 이후 공개**되는 정규장 집계입니다. 실시간이 아닙니다.
- **단일 시점 집계**입니다. 시계열은 반복 호출이 아니라 KIS의 다른 엔드포인트가 필요하지만, 이번 슬라이스에서는 미연결입니다.
- **대상 시장**은 국내주식 정규장입니다.

## KIS specifics

- **원본 엔드포인트**: `FHKST01010900` (국내주식 종목별 투자자).
- **Rate limit 버킷**: 시세 조회.
- **지원 범위**: 국내주식 정규장 동일 영업일 집계.
- **KIS 공식 문서**: <https://apiportal.koreainvestment.com/apiservice>

## Common pitfalls

- **start/end 지정**: 현재 미지원. `KXTUnsupportedError`가 발생합니다.
- **장 중 호출**: 마감 전에는 빈 값이거나 부분 집계가 반환될 수 있습니다.
- **`retail`/`foreign`/`institution` 외 카테고리 가정**: 본 응답은 세 그룹만 노출합니다.

## See also

- [get_quote](get-quote.md)
- [Schemas](../../reference/schemas.md)
- [KIS provider](../../providers/kis.md)
