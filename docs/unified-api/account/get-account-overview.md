# get_account_overview

지정한 계좌의 종합 스냅샷을 한 번에 가져옵니다. 평가금액·예수금·D+1/D+2 결제 예상금액·총 평가손익과 함께 보유 포지션 목록(`PositionLot`)을 함께 반환합니다. 대시보드 메인 화면, 일일 포트폴리오 리포트, 주문 전 자본 점검의 출발점입니다.

## At a glance

| 항목 | 값 |
|---|---|
| 인증 필요 | 예 (KIS 앱키/시크릿 + 계좌) |
| 데이터 타입 | 계좌 평가 + 포지션 묶음 스냅샷 |
| 스트리밍 | 해당 없음 |
| 계좌 컨텍스트 | `KISClient(account_no=..., account_product_code=...)` 권장 |
| 시간대 | KST (Asia/Seoul) |
| Paper trading | 미지원 |

## Signature

```python
async def get_account_overview(
    request: AccountOverviewRequest | None = None,
    /,
    *,
    account: AccountSummary | None = None,
    include_afterhours: bool = False,
    include_fund_settlement: bool = True,
    cursor: AccountOverviewCursor | None = None,
) -> AccountOverviewResponse: ...
```

## Parameters

- **account** (`AccountSummary | None`) — 생략 시 `KISClient(account_no=..., account_product_code=...)`에서 가져옵니다.
- **include_afterhours** (`bool`, 기본 `False`) — 시간외 단일가 평가가격을 포함할지 여부.
- **include_fund_settlement** (`bool`, 기본 `True`) — 펀드 결제 포함 여부.
- **cursor** (`AccountOverviewCursor | None`) — 페이지네이션 토큰.

power-user용으로 `AccountOverviewRequest`를 첫 positional 인자로 전달하는 것도 가능합니다(legacy 호환).

## Returns

`AccountOverviewResponse`:

| 필드 | 타입 | 설명 |
|---|---|---|
| `equity` | `AccountEquitySnapshot` | 계좌 평가 요약 |
| `positions` | `tuple[PositionLot, ...]` | 보유 종목 lot 목록 |
| `cursor` | `AccountOverviewCursor \| None` | 다음 페이지 토큰 |

`AccountEquitySnapshot` 주요 필드 — [Schemas](../../reference/schemas.md#accountequitysnapshot):

| 필드 | 타입 | 설명 |
|---|---|---|
| `as_of` | `datetime` | 스냅샷 시각 |
| `cash` | `Decimal \| None` | 예수금 |
| `d1_settlement` / `d2_settlement` | `Decimal \| None` | 결제 예상금액 |
| `securities_value` | `Decimal \| None` | 증권 평가 금액 |
| `net_asset_value` | `Decimal \| None` | 순자산가치 |
| `total_unrealized_pnl` | `Decimal \| None` | 총 평가손익 |

`PositionLot`은 평균단가, 보유수량, 평가금액, 평가손익률, 당일/전일 매매 활동을 포함합니다 — [Schemas](../../reference/schemas.md#positionlot).

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
        response = await client.get_account_overview()
        eq = response.equity
        print(f"NAV={eq.net_asset_value} cash={eq.cash}")
        for lot in response.positions[:5]:
            print(lot.instrument.symbol, lot.quantity, lot.unrealized_pnl)


asyncio.run(main())
```

다른 계좌를 임시로 조회하려면 `account=`에 `AccountSummary`를 넘길 수 있습니다.

## Sample response

```python
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from kxt import (
    AccountEquitySnapshot,
    AccountOverviewResponse,
    InstrumentRef,
    PositionLot,
)
from kxt.requests import AccountOverviewCursor

KST = timezone(timedelta(hours=9))

AccountOverviewResponse(
    equity=AccountEquitySnapshot(
        account=...,  # 내부에서 채워진 AccountSummary
        as_of=datetime(2025, 4, 14, 15, 30, tzinfo=KST),
        cash=Decimal("3500000"),
        d1_settlement=Decimal("0"),
        d2_settlement=Decimal("0"),
        net_asset_value=Decimal("12345678"),
        total_unrealized_pnl=Decimal("123456"),
    ),
    positions=(
        PositionLot(
            instrument=InstrumentRef(symbol="005930", name="삼성전자"),
            quantity=Decimal("100"),
            average_price=Decimal("70000"),
            market_price=Decimal("71000"),
            unrealized_pnl=Decimal("100000"),
        ),
    ),
    cursor=AccountOverviewCursor(),
)
```

## Notes

- **단일 호출에 모든 정보**가 들어옵니다. `get_balance`/`get_positions`는 동일 호출의 부분 뷰입니다.
- **`cursor`는 KIS의 `CTX_AREA_FK100`/`NK100` 그대로**입니다. 비어 있으면 더 받을 페이지가 없습니다.
- **장중/장외**: `include_afterhours`로 시간외 단가 반영 여부 제어.

## KIS specifics

- **원본 엔드포인트**: `TTTC8434R` (주식잔고조회).
- **Rate limit 버킷**: 계좌 조회.
- **계좌 식별**: `KISClient(account_no=..., account_product_code=...)`를 생성자에 한 번 설정하면 매 호출마다 `account`를 넘길 필요가 없습니다.

## Common pitfalls

- **계좌 미설정**: 생성자에 `account_no`도 없고 호출에도 `account=`도 없으면 `KXTValidationError`.
- **포지션 페이지네이션 미처리**: 보유 종목이 많으면 `cursor`로 이어 받아야 합니다.
- **부분 뷰 중복 호출**: `get_balance` + `get_positions`를 함께 호출하면 같은 페이로드를 두 번 받습니다.

## See also

- [get_balance](get-balance.md) — 평가 요약만.
- [get_positions](get-positions.md) — 보유 종목만.
- [Schemas](../../reference/schemas.md#accountequitysnapshot)
- [KIS provider](../../providers/kis.md)
