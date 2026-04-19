# kxt

[![PyPI](https://img.shields.io/pypi/v/kxt.svg)](https://pypi.org/project/kxt/)
[![Python](https://img.shields.io/pypi/pyversions/kxt.svg)](https://pypi.org/project/kxt/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

`kxt` is an async Python SDK for Korea Exchange (KRX) equities, futures, and options, backed by the Korea Investment & Securities (KIS) OpenAPI. Documentation is written in Korean and published at <https://pumpkinredbean.github.io/kxt/>.

---

`kxt`는 한국거래소(KRX) 주식·선물·옵션을 비동기 파이썬으로 다루기 위한 SDK입니다. 현재는 KIS(한국투자증권) OpenAPI 어댑터 하나를 제공하며, 브로커 중립 DTO 계층 위에 얇게 얹혀 있습니다.

## Audience

- 파이썬으로 KRX 데이터를 수집하거나 자동매매 코드를 작성하는 개발자
- `ccxt` 계열의 브로커 중립 인터페이스를 한국 시장에서 찾는 사용자
- 라이브러리 우선(runtime-free) SDK를 선호하는 사용자

## Key features

- **비동기 전용** — `async`/`await` 기반, 이벤트 루프 친화적
- **브로커 중립 DTO** — `InstrumentRef`, `Bar`, `OrderBookSnapshot` 등 정규화된 응답 타입 (입력은 종목 코드 문자열)
- **시세·주문·스트림** — `get_bars`, `get_quote`, `submit_order`, `stream_trades` 등 flat 메서드
- **얇은 CLI** — 동일한 코드 경로를 `kxt bars`, `kxt quote` 같은 명령으로 호출

## Import policy

- `from kxt import ...` — `KISClient`, 응답·이벤트 DTO, enum, 에러 등 사용자가 *읽는* 타입.
- `from kxt.requests import ...` — `BarsRequest`, `SubmitOrderRequest`, `*Cursor`, `*Subscription`, `OrderInstruction`, `OrderAmendment`, `ProviderRef` 같은 power-user 입력 DTO. 일반 호출은 primitive(`symbol` 문자열, kwargs)만으로 충분합니다.
- `from kxt.models import ...` — 모든 DTO를 통째로 introspection할 때.

## Install

```bash
pip install --pre kxt
```

현재 알파 릴리스이므로 `--pre` 플래그가 필요합니다. 1.0 이후 해제됩니다.

## Quick start

```python
import asyncio
from datetime import date, timedelta

from kxt import KISClient


async def main() -> None:
    async with KISClient(
        app_key="<APP_KEY>",
        app_secret="<APP_SECRET>",
    ) as client:
        today = date.today()
        response = await client.get_bars(
            "005930",  # 삼성전자
            timeframe="day",
            start=today - timedelta(days=14),
            end=today,
        )
        for bar in response.bars[-5:]:
            print(bar.opened_at.date(), bar.close)


asyncio.run(main())
```

`<APP_KEY>` / `<APP_SECRET>`은 본인의 KIS OpenAPI 자격증명으로 대체하세요. SDK는 환경변수에 관여하지 않습니다. 환경변수 기반 흐름은 CLI에서만 사용합니다.

## Documentation

전체 한국어 문서: <https://pumpkinredbean.github.io/kxt/>

- [Getting Started](https://pumpkinredbean.github.io/kxt/getting-started/installation/) — 설치, 인증, 5분 튜토리얼
- [Unified API](https://pumpkinredbean.github.io/kxt/unified-api/overview/) — 메서드 레퍼런스
- [KIS Provider](https://pumpkinredbean.github.io/kxt/providers/kis/) — 지원 매트릭스, TR_ID, 공식 링크
- [Schemas](https://pumpkinredbean.github.io/kxt/reference/schemas/) — 공유 DTO
- [CLI](https://pumpkinredbean.github.io/kxt/cli/)
- [Architecture](https://pumpkinredbean.github.io/kxt/development/architecture/)

로컬에서 빌드하려면:

```bash
uv sync --all-extras
uv run pytest
uv run mkdocs serve
uv build
```

## Status

현재 `0.1.0a1` (alpha) 입니다. 공개 API는 1.0 이전까지 예고 없이 변경될 수 있습니다. 실거래 전에 반드시 소량으로 검증하세요.

## License

MIT. [LICENSE](LICENSE) 참조.
