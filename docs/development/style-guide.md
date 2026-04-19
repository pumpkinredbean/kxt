# Style Guide

이 문서는 `kxt` 한국어 문서의 작성 기준입니다. 이후 세션들이 참조하는 영구 가이드라인입니다.

## Language policy

kxt 문서는 영어 헤딩과 한국어 본문을 사용합니다.

- **영어 사용**
    - 모든 헤딩(H1–H6)
    - 코드 식별자, 메서드명, 파라미터명, 타입, 예외 클래스
    - 고유명사(KIS, PyPI 등)
- **한국어 사용**
    - 본문 문장, 리스트, 표 셀, admonition 내부 설명, 비고, 경고

새 페이지를 작성할 때는 기존 페이지에서 쓰이는 영어 헤딩 어휘(Overview, Key features, Parameters, Returns, Example, Sample response, Sample event, Notes, KIS specifics, Common pitfalls, See also, Next steps, Prerequisites 등)를 재사용하세요. 새 라벨을 도입하려면 style guide를 먼저 업데이트합니다.

## Voice and style

- 능동형을 기본으로. `~됩니다` 과잉 사용을 피합니다.
- 번역투(`~에 의해`, `~을/를 가진다`, `~로서`)를 피합니다.
- 한 문장 한 아이디어. 긴 쉼표 나열은 bullet로 분해합니다.
- 기술 용어는 영어 그대로 쓰는 것이 자연스러울 때 영어를 유지합니다 (예: 타임스탬프, 페이로드, 커서, 스트림).

## Page structure principles

- **Self-contained.** 앞 페이지를 읽지 않아도 이해 가능해야 합니다. 필요한 전제는 짧게 다시 언급하고 상세는 링크합니다.
- **Lead paragraph 우선.** 첫 1~3 문장에서 "이 페이지가 무엇을 다루는지·왜 필요한지"를 밝힙니다.
- **실행 가능한 예제.** 복붙으로 바로 돌아가는 코드 조각을 최소 하나 포함합니다.
- **한 화면에 과부하 금지.** 깊은 세부는 하위 페이지로 링크합니다.

## Unified API method page template

모든 메서드 페이지는 아래 구조를 따릅니다.

- **H1**: 메서드명(코드 식별자 그대로). 예: `get_bars`.
- **H2 순서 (REST 메서드 페이지)**:
    1. `## At a glance`
    2. `## Signature`
    3. `## Parameters`
    4. `## Returns`
    5. `## Example`
    6. `## Sample response`
    7. `## Notes`
    8. `## KIS specifics`
    9. `## Common pitfalls`
    10. `## See also`
- **Streaming 메서드 페이지**: 위와 동일하되 `## Sample response` 대신 `## Sample event`를 사용합니다.
- 각 섹션 내부 본문은 한국어로 서술하며, 필드명·타입·예외는 영어 코드 식별자를 유지합니다.

## Public input naming policy

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

### Public import policy

- `from kxt import ...` — `KISClient`, 응답·이벤트 DTO, enum, 에러, value object(`InstrumentRef`, `OrderCorrelationKey` 등). 사용자가 *읽는* 타입만 노출합니다.
- `from kxt.requests import ...` — `*Request`, `*Cursor`, `*Subscription`, `OrderInstruction`, `OrderAmendment`, `ProviderRef` 등 power-user 입력 DTO. 일반 호출은 symbol 문자열과 kwargs만으로 충분하므로 top-level에서 의도적으로 제외했습니다.
- `from kxt.models import ...` — 전체 DTO를 한 번에 가져오는 introspection용 별칭.

문서 코드 예제도 같은 규약을 따릅니다. 입력 DTO를 보여줄 때는 `kxt.requests`에서 가져오세요.

문서 작성 시:

- **Primary 예제는 항상 `symbol` 문자열 형태**로 작성합니다.
- `InstrumentRef`/`*Request` 형태는 "Advanced"로 명확히 표시한 보조 예제(`!!! note`)에서만 보여줍니다.
- Parameters 섹션의 첫 항목은 `**symbol** (str) *required*`로 시작합니다. 옵션 필드는 `*Request` DTO로 호출할 때만 의미가 있다고 명시합니다.

## Code examples

- 최상위 `import` → `async def main()` → `asyncio.run(main())` 패턴을 권장합니다.
- 예제 종목은 실제 KRX 코드를 씁니다: `005930` 삼성전자, `000660` SK하이닉스.
- Decimal 비교를 보여줄 때 `float` 혼용을 피합니다.

### SDK examples: env-free, explicit args only

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

## Tables

- 3열 이상은 첫 행을 인간 친화적으로 정렬 (항목 | 타입 | 설명).
- 긴 설명은 표 대신 bullet로 풀어씁니다.

## Admonitions

- `!!! note` — 보충 정보.
- `!!! tip` — 권장 패턴.
- `!!! warning` — 잠재적 문제.
- `!!! danger` — 시크릿·보안·재무 위험.
- `!!! info` — 메타 정보(세션 로드맵 등).

## Links

- 내부 링크는 상대 경로 마크다운. MkDocs `strict` 빌드가 깨진 링크를 잡습니다.
- 외부 링크는 공식 문서 위주. KIS 관련 링크는 포털 루트 또는 `apiservice` 경로.

## Forbidden patterns

- "쉽게", "간단히" 같은 주관적 수식어 남용.
- 구현되지 않은 기능을 현재 시제로 단정.
- 영어/한국어 어절을 공백 없이 붙여쓰기 (`API를`는 허용, `API와같이` 같은 경우 공백 사용).
- 이모지 (사용자가 명시적으로 요청하지 않은 한).

## Adoption

이 가이드는 새 문서 작성과 기존 문서 정비 모두에 적용됩니다.
