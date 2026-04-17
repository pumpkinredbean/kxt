# get_buying_power

특정 종목·가격·주문 유형 조합에서 매수 가능한 금액과 수량을 조회합니다. 주문 직전 자본 점검과 위험 한도 검증에 사용합니다.

## At a glance

| 항목 | 값 |
|---|---|
| 인증 필요 | 예 (KIS 앱키/시크릿 + 계좌) |
| 데이터 타입 | 매수 가능 한도 스냅샷 |
| 스트리밍 | 해당 없음 |
| 계좌 컨텍스트 | `KISClient` 기본 계좌 권장 |
| 시간대 | KST (Asia/Seoul) |
| Paper trading | 미지원 |

## Signature

```python
async def get_buying_power(
    request: BuyingPowerRequest | None = None,
    /,
    *,
    instrument: InstrumentRef | None = None,
    price: Decimal | int | float | str | None = None,
    order_type: OrderType = OrderType.LIMIT,
    include_cma: bool = False,
    account: AccountSummary | None = None,
) -> BuyingPowerResponse: ...
```

## Parameters

- **instrument** (`InstrumentRef`) *required* — 매수 대상 종목.
- **price** (`Decimal \| int \| float \| str \| None`) — 매수 단가. 시장가는 `None`.
- **order_type** (`OrderType`, 기본 `OrderType.LIMIT`)
- **include_cma** (`bool`, 기본 `False`) — CMA 평가 금액 포함 여부.
- **account** (`AccountSummary | None`) — 생략 시 기본 계좌 사용.

## Returns

`BuyingPowerResponse`:

| 필드 | 타입 |
|---|---|
| `snapshot` | `BuyingPowerSnapshot` |

`BuyingPowerSnapshot` 필드:

| 필드 | 타입 | 설명 |
|---|---|---|
| `available_cash` | `Decimal \| None` | 주문 가능 현금 |
| `available_substitute` | `Decimal \| None` | 주문 가능 대용 |
| `reusable_amount` | `Decimal \| None` | 재사용 가능 금액 |
| `non_margin_buy_amount` | `Decimal \| None` | 미수 없이 매수 가능 금액 |
| `non_margin_buy_quantity` | `Decimal \| None` | 미수 없이 매수 가능 수량 |
| `max_buy_amount` | `Decimal \| None` | 최대 매수 금액 (미수 포함) |
| `max_buy_quantity` | `Decimal \| None` | 최대 매수 수량 |
| `price_used_for_calc` | `Decimal \| None` | 계산에 사용된 단가 |

## Example

```python
import asyncio
from decimal import Decimal

from kxt import InstrumentRef, KISClient, OrderType


async def main() -> None:
    async with KISClient(
        app_key="<APP_KEY>",
        app_secret="<APP_SECRET>",
        account_no="<CANO>",
        account_product_code="<ACNT_PRDT_CD>",
    ) as client:
        response = await client.get_buying_power(
            instrument=InstrumentRef(symbol="005930"),
            price=Decimal("70000"),
            order_type=OrderType.LIMIT,
        )
        snap = response.snapshot
        print(f"max_buy_qty={snap.max_buy_quantity} non_margin_qty={snap.non_margin_buy_quantity}")


asyncio.run(main())
```

## Sample response

```python
from decimal import Decimal
from kxt import BuyingPowerResponse, BuyingPowerSnapshot

BuyingPowerResponse(
    snapshot=BuyingPowerSnapshot(
        available_cash=Decimal("3500000"),
        non_margin_buy_amount=Decimal("3500000"),
        non_margin_buy_quantity=Decimal("50"),
        max_buy_amount=Decimal("7000000"),
        max_buy_quantity=Decimal("100"),
        price_used_for_calc=Decimal("70000"),
    ),
)
```

## Notes

- **종목·가격이 항상 필요**합니다. 계좌 전체 매수 가능 금액 같은 일반화된 필드는 노출하지 않습니다.
- **`max_buy_*`는 미수 한도를 포함**할 수 있습니다. 미수 없이 운용한다면 `non_margin_buy_*`를 사용하세요.

## KIS specifics

- **원본 엔드포인트**: `TTTC8908R` (매수 가능 조회).
- **Rate limit 버킷**: 계좌 조회.

## Common pitfalls

- **시장가 단가**: `price=None`으로 호출 시 KIS는 직전 체결가를 기준으로 계산합니다. 정확한 사이징이 필요하면 `price`를 명시하세요.
- **미수 포함 가정**: 자동매매에서는 `non_margin_buy_quantity`가 안전 기준입니다.

## See also

- [submit_order](../trading/submit-order.md)
- [get_balance](get-balance.md)
- [Schemas](../../reference/schemas.md#buyingpowersnapshot)
- [KIS provider](../../providers/kis.md)
