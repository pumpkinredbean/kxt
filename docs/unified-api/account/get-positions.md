# get_positions

지정한 계좌의 보유 포지션 목록을 가져옵니다. 내부적으로 [`get_account_overview`](get-account-overview.md)를 호출하고 평가 부분을 떼어 종목별 포지션만 평탄화한 뷰입니다. 평균단가·시가·평가손익을 한 번에 받습니다.

## At a glance

| 항목 | 값 |
|---|---|
| 인증 필요 | 예 (KIS 앱키/시크릿 + 계좌) |
| 데이터 타입 | 보유 포지션 시퀀스 |
| 스트리밍 | 해당 없음 |
| 계좌 컨텍스트 | `KISClient` 기본 계좌 권장 |
| 시간대 | KST (Asia/Seoul) |
| Paper trading | 미지원 |

## Signature

```python
async def get_positions(
    request: PositionsRequest | None = None,
    /,
    *,
    account: AccountSummary | None = None,
    session: SessionType | None = None,
) -> PositionsResponse: ...
```

## Parameters

- **account** (`AccountSummary | None`) — 미지정 시 기본 계좌 사용.
- **session** (`SessionType | None`)

## Returns

`PositionsResponse`:

| 필드 | 타입 |
|---|---|
| `positions` | `tuple[Position, ...]` |

`Position` 필드:

| 필드 | 타입 | 설명 |
|---|---|---|
| `instrument` | `InstrumentRef` | 종목 |
| `quantity` | `Decimal` | 보유 수량 |
| `average_price` | `Decimal \| None` | 평균 단가 |
| `market_price` | `Decimal \| None` | 시가 평가 |
| `unrealized_pnl` | `Decimal \| None` | 평가손익 |
| `side` | `OrderSide \| None` | 현재 KIS 구현은 `None`(현물 잔고는 매수 lot으로 단순화) |

## Example

```python
import asyncio

from kxt import KISClient


async def main() -> None:
    async with KISClient(
        app_key="<APP_KEY>",
        app_secret="<APP_SECRET>",
        account_no="<CANO>",
        account_product_code="<ACNT_PRDT_CD>",
    ) as client:
        response = await client.get_positions()
        for p in response.positions:
            print(p.instrument.symbol, p.quantity, p.unrealized_pnl)


asyncio.run(main())
```

## Sample response

```python
from decimal import Decimal
from kxt import InstrumentRef, Position, PositionsResponse

PositionsResponse(
    positions=(
        Position(
            instrument=InstrumentRef(symbol="005930", name="삼성전자"),
            quantity=Decimal("100"),
            average_price=Decimal("70000"),
            market_price=Decimal("71000"),
            unrealized_pnl=Decimal("100000"),
        ),
        Position(
            instrument=InstrumentRef(symbol="000660", name="SK하이닉스"),
            quantity=Decimal("20"),
            average_price=Decimal("180000"),
            market_price=Decimal("182000"),
            unrealized_pnl=Decimal("40000"),
        ),
    ),
)
```

## Notes

- **`Position.side`는 항상 `None`**입니다(현물 잔고). 공매도/파생 포지션 모델은 이번 슬라이스 범위 밖입니다.
- **풀 뷰가 필요하면** `get_account_overview`를 사용하세요. 같은 호출을 중복하지 않습니다.

## KIS specifics

- **원본 엔드포인트**: `TTTC8434R` (잔고조회 — `get_account_overview`와 동일).
- **Rate limit 버킷**: 계좌 조회.

## Common pitfalls

- **잔고 0 종목 가정**: 응답에 등장하지 않습니다.
- **페이지네이션 누락**: 보유 종목이 많으면 `get_account_overview`로 직접 호출해 `cursor`를 처리하세요. `get_positions`는 첫 페이지만 평탄화합니다.

## See also

- [get_account_overview](get-account-overview.md)
- [get_balance](get-balance.md)
- [Schemas](../../reference/schemas.md)
- [KIS provider](../../providers/kis.md)
