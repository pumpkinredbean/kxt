# submit_order

지정한 계좌로 신규 주식 주문(현금 매수/매도)을 제출합니다. 시장가/지정가 모두 지원하며, 응답으로 KIS가 부여한 주문 식별자(`ProviderOrderRef`)와 정규화된 ack을 받습니다.

!!! danger "실거래"
    본 메서드는 실제 KIS 계좌에 주문을 보냅니다. 충분한 검증과 위험 관리 없이 자동매매에 연결하지 마세요. 샌드박스는 미연결 상태입니다.

## At a glance

| 항목 | 값 |
|---|---|
| 인증 필요 | 예 (KIS 앱키/시크릿 + 계좌) |
| 데이터 타입 | 주문 ack |
| 스트리밍 | 후속 체결은 [`stream_order_events`](../streaming/stream-order-events.md) |
| 계좌 컨텍스트 | `KISClient` 기본 계좌 권장 |
| 시간대 | KST (Asia/Seoul) |
| Paper trading | 미지원 |

## Signature

```python
async def submit_order(
    request: SubmitOrderRequest | OrderInstruction | None = None,
    /,
    *,
    symbol: str | InstrumentRef | None = None,
    side: OrderSide | None = None,
    order_type: OrderType | None = None,
    quantity: Decimal | int | float | str | None = None,
    limit_price: Decimal | int | float | str | None = None,
    stop_price: Decimal | None = None,
    time_in_force: str | None = None,
    route_hint: OrderRouteHint | None = None,
    account_no: str | None = None,
    account_product_code: str | None = None,
    account: AccountSummary | None = None,
) -> SubmitOrderResponse: ...
```

## Parameters

- **symbol** (`str | InstrumentRef`) *required* — 종목. 보통 심볼 문자열(예: `"005930"`)로 충분합니다.
- **side** (`OrderSide`) *required* — `BUY` / `SELL`.
- **order_type** (`OrderType`) *required* — `MARKET` 또는 `LIMIT` (KIS 슬라이스 범위).
- **quantity** (`Decimal | int | str`) *required* — 수량.
- **limit_price** (`Decimal | int | str | None`) — 지정가 (LIMIT일 때 필수).
- **stop_price** (`Decimal | None`) — 현재 KIS 슬라이스에서는 사용하지 않음.
- **time_in_force** (`str | None`) — 미사용.
- **route_hint** (`OrderRouteHint | None`) — 미사용.
- **account_no** / **account_product_code** (`str | None`) — 생략 시 `KISClient` 기본 계좌.
- **account** (`AccountSummary | None`) — power-user alias.

미리 만들어 둔 `OrderInstruction` 또는 `SubmitOrderRequest`를 첫 positional 인자로 전달하는 것도 가능합니다.

## Returns

`SubmitOrderResponse`:

| 필드 | 타입 |
|---|---|
| `acknowledgement` | `OrderAcknowledgement` |

`OrderAcknowledgement` 필드:

| 필드 | 타입 | 설명 |
|---|---|---|
| `order_ref` | `ProviderOrderRef \| None` | KIS 주문 식별 (이후 정정·취소에 필요) |
| `state` | `OrderLifecycleState` | 제출 직후 상태 (`ACKNOWLEDGED`) |
| `occurred_at` | `datetime \| None` | 응답 시각 (KST) |
| `message` | `str \| None` | 추가 메시지 |

## Example

```python
import asyncio
from decimal import Decimal

from kxt import KISClient, OrderSide, OrderType


async def main() -> None:
    async with KISClient(
        app_key="<APP_KEY>",
        app_secret="<APP_SECRET>",
        account_no="<CANO>",
        account_product_code="<ACNT_PRDT_CD>",
    ) as client:
        response = await client.submit_order(
            symbol="005930",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("1"),
            limit_price=Decimal("70000"),
        )
        ack = response.acknowledgement
        print(f"order_id={ack.order_ref.order_id} state={ack.state}")


asyncio.run(main())
```

시장가 매수:

```python
await client.submit_order(
    symbol="005930",
    side=OrderSide.BUY,
    order_type=OrderType.MARKET,
    quantity=Decimal("1"),
)
```

## Sample response

```python
from datetime import datetime, timezone, timedelta
from kxt import (
    OrderAcknowledgement,
    OrderLifecycleState,
    ProviderOrderRef,
    SubmitOrderResponse,
)

KST = timezone(timedelta(hours=9))
SubmitOrderResponse(
    acknowledgement=OrderAcknowledgement(
        order_ref=ProviderOrderRef(provider="kis", order_id="0000000123", account_id="12345678"),
        state=OrderLifecycleState.ACKNOWLEDGED,
        occurred_at=datetime(2025, 4, 14, 9, 30, tzinfo=KST),
    ),
)
```

## Notes

- **`ACKNOWLEDGED`는 KIS가 주문을 접수했다는 의미**입니다. 체결을 보장하지 않습니다. 후속 상태는 [`stream_order_events`](../streaming/stream-order-events.md) 또는 [`get_order_history`](../account/get-order-history.md)로 확인합니다.
- **`order_ref.order_id`를 보존**하세요. 정정·취소·이력 조회의 키입니다.
- **`OrderType.LIMIT`은 `limit_price` 필수**. 누락 시 `KXTUnsupportedError`.

## KIS specifics

- **원본 엔드포인트**: `TTTC0802U` (현금 매수) / `TTTC0801U` (현금 매도) — `KIS_ORDER_CASH_PATH`.
- **Rate limit 버킷**: 주문 (계좌 단위 별도 버킷).
- **지원 범위**: 국내주식 현물 cash 주문. 신용·해외·파생은 슬라이스 범위 외.

## Common pitfalls

- **`limit_price` 누락 LIMIT 주문**: 거부됩니다. 지정가가 필요 없으면 `OrderType.MARKET`을 사용하세요.
- **계좌 미설정**: `KISClient(account_no=..., account_product_code=...)` 또는 호출 시 `account=`를 전달하지 않으면 `KXTValidationError`.
- **수량을 `int`/`float`로 전달**: `Decimal` 사용을 권장합니다(라이브러리는 `str(...)` 변환에 의존).
- **재시도 멱등성**: KIS는 멱등 키를 받지 않습니다. 네트워크 타임아웃 시 동일 요청을 무작정 재시도하면 중복 주문 위험이 있습니다.

## See also

- [cancel_order](cancel-order.md)
- [modify_order](modify-order.md)
- [stream_order_events](../streaming/stream-order-events.md)
- [get_buying_power](../account/get-buying-power.md)
- [Schemas](../../reference/schemas.md)
