# Rate limits

KIS OpenAPI는 호출 유형별로 분당·초당 한도가 다릅니다. `kxt`는 기본적으로 사용자 호출을 그대로 전달하되, 인증 토큰 캐싱과 전송 레벨 재시도를 내부적으로 처리합니다.

## KIS rate limits overview

KIS OpenAPI는 대략 아래 버킷으로 나뉩니다. 정확한 수치는 KIS 공식 안내를 참조하세요.

| 버킷 | 적용 대상 | 대략적 한도(참고) |
|---|---|---|
| 시세 조회 | `get_quote`, `get_bars`, `get_orderbook`, `get_recent_trades`, `get_market_status`, `get_investor_flow` | 초당 수 건 ~ 분당 수십 건 |
| 계좌/주문 | `get_balance`, `get_positions`, `submit_order`, `cancel_order`, `modify_order`, `get_order_history` | 계정 기준 초당 소량 |
| 실시간 스트림 | `stream_trades`, `stream_orderbook`, `stream_order_events` | 동시 구독 수와 초당 이벤트 처리량 기준 |

공식 한도 표: <https://apiportal.koreainvestment.com/>

## Library internal handling

- **토큰 관리** — 액세스 토큰은 로컬 캐시에 저장되어 만료 직전까지 재사용됩니다. 호출마다 토큰을 재발급하지 않습니다.
- **전송 오류 재시도** — 타임아웃·연결 실패는 `KXTTimeoutError`/`KXTConnectionError`로 올라옵니다. 자동 재시도는 적용하지 않으며, 호출부에서 명시적으로 재시도 정책을 세우는 것을 권장합니다.
- **WebSocket 재연결** — 실시간 세션은 지수 백오프(최대 30초)로 자동 재연결하고, 구독 상태를 복원합니다.

## When limits are exceeded

한도를 초과하면 KIS는 에러 코드를 담은 응답을 돌려보내며, `kxt`는 이를 `KXTAPIError`로 감쌉니다(`code` 속성에 원본 코드 포함).

```python
import asyncio
from kxt import KXTAPIError, KISClient


async def guarded_call(client, symbol):
    try:
        return await client.get_quote(symbol)
    except KXTAPIError as exc:
        if exc.code and "EGW00201" in exc.code:  # 예: 호출 빈도 초과 코드
            await asyncio.sleep(1.0)
            return await client.get_quote(symbol)
        raise
```

## Recommended patterns

- 루프 호출 시 `await asyncio.sleep(...)`을 명시적으로 삽입하세요.
- 동일 데이터를 반복 조회하지 않도록 호출 측 캐시를 고려하세요(토큰 외 응답 캐시는 라이브러리가 제공하지 않습니다).
- 대량 히스토리컬 수집은 장외 시간대에 분할 실행하세요.

## See also

- [Pagination](pagination.md)
- [Errors](errors.md)
