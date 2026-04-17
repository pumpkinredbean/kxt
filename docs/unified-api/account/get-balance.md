# get_balance

지정한 계좌의 평가 요약(예수금, 순자산가치)만 가볍게 가져옵니다. 내부적으로 [`get_account_overview`](get-account-overview.md)를 호출하고 평가 부분만 추려 반환합니다. 보유 종목 목록까지 필요하면 `get_account_overview`를 직접 호출하세요.

## At a glance

| 항목 | 값 |
|---|---|
| 인증 필요 | 예 (KIS 앱키/시크릿 + 계좌) |
| 데이터 타입 | 계좌 평가 스냅샷 |
| 스트리밍 | 해당 없음 |
| 계좌 컨텍스트 | `KISClient(account_no=..., account_product_code=...)` 권장 |
| 시간대 | KST (Asia/Seoul) |
| Paper trading | 미지원 |

## Signature

```python
async def get_balance(
    request: BalanceRequest | None = None,
    /,
    *,
    account: AccountSummary | None = None,
    instrument: InstrumentRef | None = None,
    session: SessionType | None = None,
) -> BalanceResponse: ...
```

## Parameters

- **account** (`AccountSummary | None`) — 생략 시 `KISClient` 기본 계좌 사용.
- **instrument** (`InstrumentRef | None`) — 현재 KIS 구현은 사용하지 않습니다(미래 호환).
- **session** (`SessionType | None`)

## Returns

`BalanceResponse`:

| 필드 | 타입 |
|---|---|
| `snapshot` | `BalanceSnapshot` |

`BalanceSnapshot` 주요 필드:

| 필드 | 타입 | 설명 |
|---|---|---|
| `as_of` | `datetime \| None` | 스냅샷 시각 |
| `cash` | `Decimal \| None` | 예수금 |
| `buying_power` | `Decimal \| None` | 매수 가능 금액 — 현재 KIS 구현은 `None`. [`get_buying_power`](get-buying-power.md) 사용 권장 |
| `margin_available` | `Decimal \| None` | 신용 잔여 — 현재 `None` |
| `net_liquidation_value` | `Decimal \| None` | 순자산가치 (NAV) |

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
        response = await client.get_balance()
        snap = response.snapshot
        print(f"NAV={snap.net_liquidation_value} cash={snap.cash}")


asyncio.run(main())
```

## Sample response

```python
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from kxt import BalanceResponse, BalanceSnapshot

KST = timezone(timedelta(hours=9))

BalanceResponse(
    snapshot=BalanceSnapshot(
        account=...,  # 내부에서 채워진 AccountSummary
        as_of=datetime(2025, 4, 14, 15, 30, tzinfo=KST),
        cash=Decimal("3500000"),
        net_liquidation_value=Decimal("12345678"),
    ),
)
```

## Notes

- **내부적으로 `get_account_overview` 호출**입니다. 같은 호출 비용이 발생합니다. 종목 목록까지 필요하면 처음부터 `get_account_overview`를 쓰세요.
- **`buying_power`는 항상 `None`**입니다. 종목·가격 컨텍스트 없이는 KIS가 매수 가능 금액을 계산하지 못합니다. 종목 단위 매수 가능 금액은 `get_buying_power`를 사용하세요.

## KIS specifics

- **원본 엔드포인트**: `TTTC8434R` (잔고조회 — `get_account_overview`와 동일).
- **Rate limit 버킷**: 계좌 조회.

## Common pitfalls

- **`buying_power` 의존**: `None`으로 옵니다. `get_buying_power`로 분리 호출하세요.
- **풀 뷰가 필요할 때 두 번 호출**: `get_balance` + `get_positions`는 같은 페이로드를 두 번 가져옵니다. `get_account_overview` 하나로 통합하세요.

## See also

- [get_account_overview](get-account-overview.md)
- [get_positions](get-positions.md)
- [get_buying_power](get-buying-power.md)
- [Schemas](../../reference/schemas.md#balancesnapshot)
