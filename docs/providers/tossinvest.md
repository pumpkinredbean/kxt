# Toss Invest Provider

Toss Invest Open API 어댑터입니다. 현재 `kxt`에서는 REST 기반 시세·계좌·주문 일부를 브로커 중립 DTO로 정규화합니다.

## Official documentation

- 문서: <https://developers.tossinvest.com/docs/>
- OpenAPI JSON: <https://openapi.tossinvest.com/openapi-docs/latest/openapi.json>

## Authentication

- `client_id`, `client_secret`이 필수입니다.
- Toss Invest는 OAuth 2.0 Client Credentials Grant로 access token을 발급합니다.
- 계좌·자산·주문 API는 `X-Tossinvest-Account` 헤더가 필요합니다. `kxt`에서는 이 값을 `account_seq`로 받습니다.
- SDK는 `TossInvestClient(...)`의 명시적 키워드 인자로 자격증명을 받습니다. 환경변수에 관여하지 않습니다.
- CLI는 `TOSS_INVEST_CLIENT_ID`, `TOSS_INVEST_CLIENT_SECRET`, `TOSS_INVEST_ACCOUNT_SEQ` 환경변수를 사용합니다.
- 토큰은 로컬 캐시에 저장되어 만료 직전까지 재사용됩니다.

```python
import asyncio

from kxt import TossInvestClient


async def main() -> None:
    async with TossInvestClient(
        client_id="<CLIENT_ID>",
        client_secret="<CLIENT_SECRET>",
        account_seq="<ACCOUNT_SEQ>",
    ) as client:
        quote = await client.get_quote("005930")
        print(quote.last)


asyncio.run(main())
```

## Supported methods matrix

| 카테고리 | 메서드 | 지원 | 비고 |
|---|---|:---:|---|
| Market data | `get_quote` | ✅ | `GET /api/v1/prices` |
| Market data | `get_quotes` | ✅ | `GET /api/v1/prices`, 최대 200개 `symbols` batch 조회 |
| Market data | `get_bars` | ✅ | `1m`, `day`. 다분봉은 1분봉을 로컬 집계 |
| Market data | `get_orderbook` | ✅ | `GET /api/v1/orderbook` |
| Market data | `get_recent_trades` | ✅ | `GET /api/v1/trades`, provider limit 적용 |
| Market data | `get_market_status` | ✅ | 국내 장 운영 정보에서 파생 |
| Account | `get_accounts` | ✅ | `accountSeq` discovery |
| Account | `get_positions` | ✅ | 보유 주식 목록을 `Position`으로 정규화 |
| Account | `get_buying_power` | ✅ | 통화별 현금 기반 매수 가능 금액 |
| Account | `get_open_orders` | ✅ | `status=OPEN` 주문 목록 |
| Account | `get_order_history` | ✅ | `status=CLOSED` 주문 목록. provider 응답/제한을 따름 |
| Trading | `submit_order` | ✅ | 수량 기반 지정가·시장가. `client_order_id` 지원 |
| Trading | `cancel_order` | ✅ | `POST /api/v1/orders/{orderId}/cancel` |
| Trading | `modify_order` | ✅ | 가격·수량 정정 |
| Streams | `stream_trades` | ❌ | Toss Invest Open API는 현재 REST만 제공 |
| Streams | `stream_orderbook` | ❌ | REST만 제공 |
| Batch analytics | rankings / program trade / investor flow | ❌ | 해당 endpoint 없음 |

## Rate limits

Toss Invest는 API 그룹별 TPS 제한을 응답 헤더로 제공합니다.

- `X-RateLimit-Limit`
- `X-RateLimit-Remaining`
- `X-RateLimit-Reset`
- `Retry-After` (429 응답)

구체적인 수치는 운영 상황에 따라 바뀔 수 있으므로, 클라이언트는 응답 헤더를 기준으로 속도를 조절해야 합니다.

## Order notes

- `clientOrderId`는 provider 측 중복 방지 키로 사용됩니다. `kxt`에서는 `submit_order(..., client_order_id="...")`로 전달합니다.
- 1억원 이상 주문은 `confirm_high_value_order=True`가 필요할 수 있습니다.
- 미국 주식 금액 기반 주문(`orderAmount`)은 Toss 고유 주문 방식입니다. 현재 공통 `submit_order`의 기본 경로는 수량 기반 주문을 우선 지원합니다.

## Constraints

- 스트리밍은 지원하지 않습니다.
- `fetch_markets()`처럼 전체 종목 마스터를 내려받는 흐름은 지원하지 않습니다. Toss Invest 종목 정보 API는 명시적 `symbols` 조회를 요구하므로 `resolve_instrument("005930")`를 사용하세요.
- KIS 전용 분석 API(`rankings`, `program_trade`, `condition_search`)는 Toss Invest provider에서 사용할 수 없습니다.

## See also

- [Authentication](../getting-started/authentication.md)
- [CLI](../cli.md)
- [KIS Provider](kis.md)
