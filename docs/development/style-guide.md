# Style Guide

이 문서는 `kxt` 한국어 문서의 작성 기준입니다. 이후 세션들이 참조하는 영구 가이드라인입니다.

## 언어 정책

- **주 언어: 한국어.** 격식체(~입니다/합니다)로 작성합니다.
- **영어 유지 대상**
    - 코드 식별자 (`get_bars`, `InstrumentRef`)
    - 환경변수명 (`KIS_APP_KEY`)
    - 섹션 카테고리 고정어 (Installation, Tutorial, Guide, Reference, Advanced, Development, Unified API, Providers, Examples, Getting Started)
    - 파일명과 URL (kebab-case)
- **한국어 대상**
    - 본문 문장, 설명, 비고, 경고
    - 파일 내부 H1

## 문체

- 능동형을 기본으로. `~됩니다` 과잉 사용을 피합니다.
- 번역투(`~에 의해`, `~을/를 가진다`, `~로서`)를 피합니다.
- 한 문장 한 아이디어. 긴 쉼표 나열은 bullet로 분해합니다.
- 기술 용어는 영어 그대로 쓰는 것이 자연스러울 때 영어를 유지합니다 (예: 타임스탬프, 페이로드, 커서, 스트림).

## 페이지 구조 원칙

- **Self-contained.** 앞 페이지를 읽지 않아도 이해 가능해야 합니다. 필요한 전제는 짧게 다시 언급하고 상세는 링크합니다.
- **Lead paragraph 우선.** 첫 1~3 문장에서 "이 페이지가 무엇을 다루는지·왜 필요한지"를 밝힙니다.
- **실행 가능한 예제.** 복붙으로 바로 돌아가는 코드 조각을 최소 하나 포함합니다.
- **한 화면에 과부하 금지.** 깊은 세부는 하위 페이지로 링크합니다.

## Unified API 메서드 페이지 템플릿

모든 메서드 페이지는 아래 순서를 따릅니다 (`get_bars` 기준).

1. **H1: 메서드명 (영어 식별자 그대로)**
2. **Lead**: 1~3 문장. 개념 프라이밍.
3. **At a glance**: 테이블. 인증 필요, 데이터 타입, 스트리밍 여부, 계좌 컨텍스트, 시간대, Paper trading 지원 등.
4. **Signature**: 파이썬 시그니처 코드블록.
5. **Parameters**: bullet 리스트. 각 항목 `**name** (Type) required? — 설명`.
6. **Returns**: 반환 타입 + 공유 스키마 링크 + 핵심 필드 테이블.
7. **Example**: 완결 실행 가능 코드.
8. **Sample response**: 실제 값 예시 (DTO 재구성).
9. **Notes**: 타임존·경계·소수점·수정주가 등 실용적 주의.
10. **KIS specifics**: TR_ID, rate bucket, 범위, 공식 링크.
11. **Common pitfalls**: 자주 겪는 실수.
12. **See also**: 관련 페이지 링크.

## Public 입력 네이밍 정책

`kxt`의 public 메서드(시세, 호가, 체결, 스트리밍)는 ccxt 계열 라이브러리와 일관성을 맞춰 **종목 코드 문자열(`symbol`)을 1차 입력 형태**로 받습니다.

- **권장**: 첫 위치인자에 종목 코드 문자열을 그대로 넘깁니다.

    ```python
    await client.get_quote("005930")
    await client.get_bars("005930", timeframe="day", start=..., end=...)
    async for event in client.stream_trades("005930"):
        ...
    ```

- **Advanced**: 베뉴/마켓 세그먼트 같은 추가 컨텍스트가 필요하거나 모든 필드를 한꺼번에 묶고 싶을 때만 같은 위치인자에 `InstrumentRef` 또는 `*Request` DTO를 넘깁니다. 입력 DTO는 `kxt.requests`에 모여 있습니다.

    ```python
    from kxt import InstrumentRef
    from kxt.requests import BarsRequest

    await client.get_quote(InstrumentRef(symbol="005930"))
    await client.get_bars(BarsRequest(instrument=InstrumentRef(symbol="005930"), timeframe="day"))
    ```

- **응답 모델은 그대로 `InstrumentRef`를 유지**합니다. 입력은 primitive-friendly, 출력은 broker-neutral structured DTO라는 비대칭이 의도적인 설계입니다.

### Public 임포트 정책

- `from kxt import ...` — `KISClient`, 응답·이벤트 DTO, enum, 에러, value object(`InstrumentRef`, `OrderCorrelationKey` 등). 사용자가 *읽는* 타입만 노출합니다.
- `from kxt.requests import ...` — `*Request`, `*Cursor`, `*Subscription`, `OrderInstruction`, `OrderAmendment`, `ProviderRef` 등 power-user 입력 DTO. 일반 호출은 symbol 문자열과 kwargs만으로 충분하므로 top-level에서 의도적으로 제외했습니다.
- `from kxt.models import ...` — 전체 DTO를 한 번에 가져오는 introspection용 별칭.

문서 코드 예제도 같은 규약을 따릅니다. 입력 DTO를 보여줄 때는 `kxt.requests`에서 가져오세요.

문서 작성 시:

- **Primary 예제는 항상 `symbol` 문자열 형태**로 작성합니다.
- `InstrumentRef`/`*Request` 형태는 "Advanced"로 명확히 표시한 보조 예제(`!!! note`)에서만 보여줍니다.
- Parameters 섹션의 첫 항목은 `**symbol** (str) *required*`로 시작합니다. 옵션 필드는 `*Request` DTO로 호출할 때만 의미가 있다고 명시합니다.

## 코드 예제

- 최상위 `import` → `async def main()` → `asyncio.run(main())` 패턴을 권장합니다.
- 예제 종목은 실제 KRX 코드를 씁니다: `005930` 삼성전자, `000660` SK하이닉스.
- Decimal 비교를 보여줄 때 `float` 혼용을 피합니다.

### SDK 예제는 env-free, 명시적 인자만

SDK 코드 자체는 환경변수에 관여하지 않습니다. `KISClient`는 `app_key`, `app_secret`, `account_no`, `account_product_code`, `hts_id`를 모두 명시적 키워드 인자로만 받습니다. 따라서 문서의 SDK 예제도 같은 규약을 따릅니다.

- **금지**: `os.environ`, `os.getenv`, `import os`를 SDK 예제에 사용하지 마세요. `KIS_APP_KEY` 같은 환경변수명도 SDK 예제 본문에 등장시키지 않습니다.
- **권장**: 자격증명은 placeholder 리터럴로 표기하거나, 호출자가 임의 경로(설정 파일·시크릿 매니저·CLI 환경 등)로 주입한다는 가정을 둡니다.

```python
async with KISClient(
    app_key="<APP_KEY>",
    app_secret="<APP_SECRET>",
) as client:
    ...
```

계좌·HTS ID가 필요한 메서드도 같은 방식입니다.

```python
async with KISClient(
    app_key="<APP_KEY>",
    app_secret="<APP_SECRET>",
    account_no="<CANO>",
    account_product_code="<ACNT_PRDT_CD>",
    hts_id="<HTS_ID>",
) as client:
    ...
```

환경변수 기반 흐름은 CLI 전용 관심사이며, [CLI 레퍼런스](../cli.md)와 [Authentication](../getting-started/authentication.md)의 CLI 섹션에서만 다룹니다.

## 표 작성

- 3열 이상은 첫 행을 인간 친화적으로 정렬 (항목 | 타입 | 설명).
- 긴 설명은 표 대신 bullet로 풀어씁니다.

## Admonition 사용

- `!!! note` — 보충 정보.
- `!!! tip` — 권장 패턴.
- `!!! warning` — 잠재적 문제.
- `!!! danger` — 시크릿·보안·재무 위험.
- `!!! info` — 메타 정보(세션 로드맵 등).

## 링크

- 내부 링크는 상대 경로 마크다운. MkDocs `strict` 빌드가 깨진 링크를 잡습니다.
- 외부 링크는 공식 문서 위주. KIS 관련 링크는 포털 루트 또는 `apiservice` 경로.

## 금지

- "쉽게", "간단히" 같은 주관적 수식어 남용.
- 구현되지 않은 기능을 현재 시제로 단정.
- 영어/한국어 어절을 공백 없이 붙여쓰기 (`API를`는 허용, `API와같이` 같은 경우 공백 사용).
- 이모지 (사용자가 명시적으로 요청하지 않은 한).

## Session 2 이후 적용

신규 Unified API 페이지는 `get_bars`를 그대로 복제해 채우세요. 템플릿에서 벗어나고 싶다면 이 Style Guide를 먼저 개정합니다.
