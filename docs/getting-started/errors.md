# Errors

`kxt`는 명시적 예외 계층을 제공합니다. 모든 라이브러리 예외는 `KXTError`에서 파생되므로, 포괄적인 오류 경계는 `KXTError` 하나로 잡을 수 있고, 세부 처리가 필요할 때 하위 타입으로 분기합니다.

## Exception hierarchy

```text
KXTError
├── KXTValidationError          # 호출부가 잘못된 입력을 줬을 때
└── KXTClientError
    ├── KXTUnsupportedError     # 프로바이더가 지원하지 않는 기능
    ├── KXTAuthenticationError  # 인증 실패
    ├── KXTAPIError             # 프로바이더가 API 레벨 오류 응답
    └── KXTTransportError       # 응답 전 전송 계층 실패
        ├── KXTTimeoutError     # 타임아웃
        └── KXTConnectionError  # 연결 실패/끊김
```

모든 타입은 `kxt` 최상위에서 import할 수 있습니다.

```python
from kxt import (
    KXTError,
    KXTValidationError,
    KXTUnsupportedError,
    KXTAuthenticationError,
    KXTAPIError,
    KXTTransportError,
    KXTTimeoutError,
    KXTConnectionError,
)
```

## When each exception is raised

| 예외 | 원인 | 재시도 가능? |
|---|---|---|
| `KXTValidationError` | 필수 파라미터 누락, 잘못된 timeframe 문자열 등 | 아니오 (코드를 고치세요) |
| `KXTUnsupportedError` | 구현되지 않은 메서드/프로바이더 호출 | 아니오 |
| `KXTAuthenticationError` | 앱키·시크릿 불일치, 토큰 발급 실패 | 자격증명 수정 후 재시도 |
| `KXTAPIError` | KIS가 에러 코드를 담아 응답 (`code` 속성 참조) | 코드에 따라 판단 |
| `KXTTimeoutError` | 네트워크 타임아웃 | 일반적으로 가능 |
| `KXTConnectionError` | 연결 실패·중단 | 일반적으로 가능 |
| `KXTTransportError` | 기타 전송 계층 오류 | 상황에 따라 |

## try/except example

```python
import asyncio

from kxt import (
    KISClient,
    KXTAPIError,
    KXTAuthenticationError,
    KXTTimeoutError,
)


async def safe_bars(client: KISClient, symbol: str):
    try:
        return await client.get_bars(symbol, timeframe="day")
    except KXTAuthenticationError:
        # 자격증명 문제: 상위로 올려 사용자 개입 유도
        raise
    except KXTTimeoutError:
        # 일시적 네트워크 지연: 짧게 대기 후 한 번 재시도
        await asyncio.sleep(1.0)
        return await client.get_bars(symbol, timeframe="day")
    except KXTAPIError as exc:
        # 프로바이더 에러 코드를 기록해 후속 조치
        print(f"KIS error: code={exc.code} message={exc}")
        raise
```

## `KXTAPIError` vs `KXTTransportError`

- `KXTAPIError` — HTTP 응답은 정상 수신했지만 **프로바이더가 에러 페이로드를 반환**했습니다. 재시도 가능 여부는 코드에 따라 다릅니다.
- `KXTTransportError` — **응답 자체를 받지 못했습니다**. 네트워크·타임아웃·연결 중단 같은 전송 계층 문제로, 보통 재시도 대상입니다.

이 구분은 `ccxt`의 `ExchangeError` vs `NetworkError` 구분과 동일한 관점입니다.

## `KXTValidationError` example

```python
import asyncio

from kxt import KISClient, KXTValidationError


async def demo(client: KISClient) -> None:
    try:
        # timeframe 키워드 누락 — 필수 인자 검증에서 실패
        await client.get_bars("005930")
    except KXTValidationError as exc:
        print(f"validation failed: {exc}")
```

`get_bars(...)`는 `timeframe` 키워드 인자가 필수입니다. 누락하면 `KXTValidationError`가 발생합니다.

## See also

- [Rate limits](rate-limits.md) — 한도 초과 시 `KXTAPIError`로 관측.
- [KIS provider](../providers/kis.md) — 프로바이더별 에러 코드 매핑 참고.
