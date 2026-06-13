# kxt

> `kxt` is an async Python SDK for Korean securities market access, backed by provider adapters such as Korea Investment & Securities (KIS) and Toss Invest. The documentation below is written in Korean.

`kxt`는 한국 증권시장 데이터와 주문을 비동기 파이썬 코드로 다루기 위한 SDK입니다. 현재는 KIS(한국투자증권)와 Toss Invest Open API 어댑터를 제공하며, 브로커 중립 DTO 계층 위에 얇게 얹혀 있습니다.

## Key features

- **비동기 전용** — `async`/`await` 기반. 이벤트 루프 친화적이며 블로킹 I/O를 끌어들이지 않습니다.
- **브로커 중립 DTO** — provider 필드명을 `Trade`, `MarketBar`, `OrderBookSnapshot` 같은 통일된 데이터클래스로 정규화합니다.
- **라이브러리 우선** — 네트워크 부작용 없는 import, 백그라운드 스레드 없음, 설정 파일 강요 없음.
- **얇은 CLI** — `kxt quote`, `kxt bars` 같은 명령으로 동일한 코드 경로를 그대로 호출할 수 있습니다.

## 30-second example

```python
import asyncio
from datetime import date

from kxt import KISClient


async def main() -> None:
    async with KISClient(app_key="...", app_secret="...") as client:
        response = await client.get_bars(
            "005930",  # 삼성전자
            timeframe="day",
            start=date(2025, 4, 1),
            end=date(2025, 4, 14),
        )
        for bar in response.bars[-5:]:
            print(bar.opened_at.date(), bar.close)


asyncio.run(main())
```

## Architecture at a glance

```
┌──────────────────────────┐
│  사용자 코드 / CLI          │
└────────────┬─────────────┘
             │  Unified API (get_bars, get_quote, submit_order, ...)
┌────────────▼─────────────┐
│  Base Client 계약         │   ← 브로커 중립 DTO (models/)
└────────────┬─────────────┘
             │  adapter 경계
┌────────────▼─────────────┐
│  Provider Adapter        │   ← HTTP/WebSocket transport, 인증, parsing
└────────────┬─────────────┘
             │  HTTPS + WSS
┌────────────▼─────────────┐
│  KIS / Toss Invest APIs  │
└──────────────────────────┘
```

## Documentation structure

- **[Getting Started](getting-started/installation.md)** — 설치, 인증, 5분 튜토리얼, 공통 개념(페이지네이션·레이트 리밋·에러).
- **[Unified API](unified-api/overview.md)** — 브로커 중립 메서드 레퍼런스. 각 메서드마다 시그니처·파라미터·예제·provider 특이사항을 한 페이지에 담았습니다.
- **[Providers](providers/kis.md)** — provider별 지원 매트릭스와 공식 문서 링크.
- **[CLI](cli.md)** — `kxt` 커맨드라인 래퍼 레퍼런스.
- **[Reference](reference/schemas.md)** — 공유 스키마.
- **[Development](development/architecture.md)** — 아키텍처 원칙, 문서 스타일 가이드, 기여 절차.

!!! warning "0.x release"
    `kxt`는 현재 0.x 릴리스 단계입니다. 공개 API는 1.0 이전까지 변경될 수 있습니다.
