# Authentication

`kxt`가 실제 KRX 데이터를 호출하려면 KIS(한국투자증권) OpenAPI 앱키와 앱시크릿이 필요합니다. 계좌 기반 메서드(주문·잔고)까지 사용한다면 계좌번호와 상품코드도, 체결 알림 스트림까지 사용한다면 HTS ID까지 함께 준비해야 합니다.

## Two usage paths

`kxt`의 자격증명은 사용 경로에 따라 다르게 주입됩니다.

| 경로 | 자격증명 주입 방식 |
|---|---|
| **SDK** (`KISClient(...)`) | 명시적 키워드 인자 |
| **CLI** (`kxt ...`) | 환경변수 또는 일부 명령에서는 `--account-no` 등 플래그 |

SDK 코어는 환경변수에 관여하지 않습니다. 환경변수 인터페이스는 CLI 전용 편의이며, `KIS_APP_KEY` 같은 변수명을 SDK 코드가 직접 읽지 않습니다.

## Prerequisites

| 항목 | 설명 |
|---|---|
| App key | KIS OpenAPI 포털에서 발급 |
| App secret | App key와 함께 발급되는 시크릿 |
| Account number (CANO) | 계좌 기반 메서드(주문·잔고)에서 필요 |
| Account product code | 보통 `01` (위탁) — 계좌별로 상이 |
| HTS ID | 주문 체결 실시간 알림(`stream_order_events`)에 필요 |

## Issue app keys

KIS OpenAPI 포털의 안내를 따릅니다.

- KIS OpenAPI 포털: <https://apiportal.koreainvestment.com/>
- 발급 절차와 약관은 공식 안내를 참조하세요. 본 문서에서는 재현하지 않습니다.

## SDK authentication — explicit keyword args

`KISClient` 생성자는 자격증명을 모두 키워드 인자로 받습니다. 환경변수, 설정 파일, 시크릿 매니저, 사용자 입력 — 어떤 경로로 값을 가져오든 호출부의 자유입니다.

```python
import asyncio

from kxt import KISClient


async def main() -> None:
    async with KISClient(
        app_key="<APP_KEY>",
        app_secret="<APP_SECRET>",
        # 아래는 계좌 기반 메서드와 체결 알림 스트림에서만 필요
        account_no="<CANO>",
        account_product_code="<ACNT_PRDT_CD>",
        hts_id="<HTS_ID>",
    ) as client:
        ...


asyncio.run(main())
```

`<APP_KEY>` 같은 placeholder는 실제 값으로 대체하세요. 자격증명을 어떻게 보관·로딩할지는 사용자 결정 사항입니다.

!!! danger "시크릿 관리"
    앱키·앱시크릿·토큰 캐시 파일은 절대 커밋하지 마세요. 시크릿을 하드코드한 채 공개 저장소에 올리지 않도록 주의하세요.

## CLI authentication — environment variables

CLI는 시크릿을 플래그로 받지 않습니다. 아래 환경변수를 사용합니다.

| 환경변수 | 필수 여부 | 설명 |
|---|---|---|
| `KIS_APP_KEY` | 필수 | App key |
| `KIS_APP_SECRET` | 필수 | App secret |
| `KIS_ACCOUNT_NO` | 계좌·주문 명령에서 필수 (또는 `--account-no` 플래그) | 계좌번호(CANO) |
| `KIS_ACCOUNT_PRODUCT_CODE` | 계좌·주문 명령에서 필수 (또는 `--account-product-code` 플래그) | 상품코드 (예: `01`) |
| `KIS_HTS_ID` | `kxt order-events`에서 필수 (또는 `--hts-id` 플래그) | HTS ID |
| `KXT_KIS_WS_PROXY` | 선택 | 웹소켓 프록시 URL (`auto` 또는 URL) |

### `.env` example

CLI 사용 시 프로젝트 루트에 `.env`를 두고 셸에서 export 하는 패턴이 일반적입니다.

```bash
# .env — 절대 커밋 금지
KIS_APP_KEY=PSxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
KIS_APP_SECRET=yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
KIS_ACCOUNT_NO=12345678
KIS_ACCOUNT_PRODUCT_CODE=01
KIS_HTS_ID=myhtsid
```

### CLI check

```bash
kxt doctor
# {
#   "KIS_APP_KEY": "set",
#   "KIS_APP_SECRET": "set",
#   ...
# }
```

자세한 CLI 사용법은 [CLI 레퍼런스](../cli.md)를 참조하세요.

## Token cache

KIS 액세스 토큰은 로컬 사용자 캐시 디렉터리에 저장되어 만료 직전까지 재사용됩니다. 토큰을 새로 받고 싶다면 캐시 파일을 삭제하면 됩니다. 캐시 위치는 OS별 표준 경로를 따릅니다(`XDG_CACHE_HOME`, `~/Library/Caches`, `%LOCALAPPDATA%`).

## Paper trading / Sandbox

현재 KIS 샌드박스는 연결되어 있지 않습니다. 실거래 키로만 동작합니다. `KISClient(..., sandbox=True)`를 전달하면 명시적 예외(`KXTUnsupportedError`)가 발생합니다.

## Next steps

- [Quickstart](quickstart.md) — 인증된 클라이언트로 첫 호출.
- [Errors](errors.md) — 인증 실패와 재시도 처리.
