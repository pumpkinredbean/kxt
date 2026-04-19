# get_order_history

지정한 계좌의 주문·체결 이력을 일자 범위로 조회합니다. 일·월 단위 트레이딩 리포트, 세무 자료 정리, 실거래 디버깅에 사용합니다.

## At a glance

| 항목 | 값 |
|---|---|
| 인증 필요 | 예 (KIS 앱키/시크릿 + 계좌) |
| 데이터 타입 | 주문 이력 시퀀스 + 합계 요약 |
| 스트리밍 | 해당 없음 |
| 계좌 컨텍스트 | `KISClient` 기본 계좌 권장 |
| 시간대 | KST (Asia/Seoul) |
| Paper trading | 미지원 |

## Signature

```python
async def get_order_history(
    request: OrderHistoryRequest | None = None,
    /,
    *,
    start: date | None = None,
    end: date | None = None,
    instrument: str | InstrumentRef | None = None,
    side_filter: OrderSide | None = None,
    fill_filter: str = "all",
    cursor: OrderHistoryCursor | None = None,
    account_no: str | None = None,
    account_product_code: str | None = None,
    account: AccountSummary | None = None,
) -> OrderHistoryResponse: ...
```

## Parameters

- **start** (`date`) *required* — 조회 시작일 (KST).
- **end** (`date`) *required* — 조회 종료일 (KST).
- **instrument** (`str | InstrumentRef | None`) — 종목 필터. 심볼 문자열 가능.
- **side_filter** (`OrderSide | None`) — `BUY` / `SELL` / `None`(전체).
- **fill_filter** (`str`, 기본 `"all"`) — `"all"` / `"filled"` / `"unfilled"`.
- **cursor** (`OrderHistoryCursor | None`) — 페이지네이션 토큰 (서버 발급값; 이어받기용).
- **account_no** / **account_product_code** (`str | None`) — 생략 시 `KISClient` 기본 계좌.
- **account** (`AccountSummary | None`) — power-user alias.

## Returns

`OrderHistoryResponse`:

| 필드 | 타입 | 설명 |
|---|---|---|
| `records` | `tuple[OrderHistoryRecord, ...]` | 주문 이력 |
| `summary` | `OrderHistorySummary \| None` | 누적 매수/매도 합계 |
| `cursor` | `OrderHistoryCursor \| None` | 다음 페이지 토큰 |

`OrderHistoryRecord` 핵심 필드 — [Schemas](../../reference/schemas.md#orderhistoryrecord).

## Example

```python
import asyncio
from datetime import date

from kxt import KISClient


async def main() -> None:
    async with KISClient(
        app_key="<APP_KEY>",
        app_secret="<APP_SECRET>",
        account_no="<CANO>",
        account_product_code="<ACNT_PRDT_CD>",
    ) as client:
        response = await client.get_order_history(
            start=date(2025, 1, 1),
            end=date(2025, 1, 31),
            fill_filter="filled",
        )
        for r in response.records[:10]:
            print(r.order_date, r.instrument.symbol, r.side, r.filled_quantity, r.average_fill_price)
        if response.cursor is not None:
            print("more pages available:", response.cursor)


asyncio.run(main())
```

## Sample response

```python
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from kxt import (
    InstrumentRef,
    OrderCorrelationKey,
    OrderHistoryRecord,
    OrderHistoryResponse,
    OrderHistorySummary,
    OrderLifecycleState,
    OrderSide,
    OrderType,
    ProviderOrderRef,
)
from kxt.requests import OrderHistoryCursor

KST = timezone(timedelta(hours=9))
ref = ProviderOrderRef(provider="kis", order_id="0000000123", account_id="12345678")

OrderHistoryResponse(
    records=(
        OrderHistoryRecord(
            order_ref=ref,
            correlation_key=OrderCorrelationKey(order_ref=ref, origin_org_no="01234"),
            instrument=InstrumentRef(symbol="005930"),
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("10"),
            limit_price=Decimal("70000"),
            filled_quantity=Decimal("10"),
            average_fill_price=Decimal("69950"),
            remaining_quantity=Decimal("0"),
            state=OrderLifecycleState.FILLED,
            order_date=date(2025, 1, 15),
            submitted_at=datetime(2025, 1, 15, 9, 30, tzinfo=KST),
        ),
    ),
    summary=OrderHistorySummary(
        total_buy_quantity=Decimal("10"),
        total_buy_notional=Decimal("699500"),
    ),
    cursor=OrderHistoryCursor(),
)
```

## Notes

- **KIS 조회 한계**: 본 엔드포인트는 일반적으로 **최근 3개월** 이내 범위를 권장합니다.
- **종목 필터**는 `instrument.symbol`이 KIS의 `PDNO`로 그대로 전달됩니다.
- **`fill_filter`** 매핑: `all` → `00`, `filled` → `01`, `unfilled` → `02`.
- **페이지네이션**: `cursor`가 `None`이 아닐 때만 추가 페이지가 존재합니다. 첫 페이지 결과를 보존한 채 새 `cursor`를 넘겨 반복 호출하세요.

## KIS specifics

- **원본 엔드포인트**: `TTTC8001R` (일별 주문체결조회).
- **Rate limit 버킷**: 계좌 조회.

## Common pitfalls

- **3개월 초과 범위**: KIS 측에서 거부될 수 있습니다.
- **`side_filter` 매핑**: `BUY` → `02`, `SELL` → `01`. 직접 raw 코드를 다루지 않게 enum을 사용하세요.
- **요약 누락 가정**: `summary`는 `None`일 수 있습니다.

## See also

- [get_open_orders](get-open-orders.md)
- [submit_order](../trading/submit-order.md)
- [Schemas](../../reference/schemas.md#orderhistoryrecord)
