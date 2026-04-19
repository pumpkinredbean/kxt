# Architecture

`kxt`는 **라이브러리 우선** SDK입니다. 허브/러너/대시보드 같은 런타임 플랫폼 책임을 의도적으로 배제하고, 재사용 가능한 시장 접근 모델과 프로바이더 클라이언트 경계만 담습니다.

## Layers

```text
┌──────────────────────────────┐
│ User code / CLI              │
├──────────────────────────────┤
│ Unified API (get_* / stream_*)│  ← 브로커 중립 메서드 이름
├──────────────────────────────┤
│ Broker-neutral DTO (models/) │  ← frozen dataclasses, Decimal
├──────────────────────────────┤
│ Base Client contract         │  ← MarketDataClient 등 추상 경계
├──────────────────────────────┤
│ Provider adapter (kis/)      │  ← HTTP/WS transport, parsing, 인증
├──────────────────────────────┤
│ Provider HTTP/WS             │
└──────────────────────────────┘
```

## Principles

### Import-safe, no side effects

- `import kxt`는 네트워크 호출·파일 기록·스레드 기동 없이 완료되어야 합니다.
- 자격증명은 생성자 인자나 환경변수로 **명시적으로** 주입받습니다. import 시점의 암묵 로딩은 금지합니다.

### Async by default

- 모든 I/O 메서드는 코루틴입니다. 동기 래퍼는 제공하지 않습니다.
- 블로킹 라이브러리 의존을 추가하지 않습니다.

### Request scope vs venue identity

- `InstrumentRef`는 **벤뉴 신원**(symbol, venue, ISIN)을 담습니다. 요청별 파라미터(기간, 세션, limit)와 분리합니다.
- 같은 인스트루먼트 여러 번 조회에도 DTO 불변성이 유지되도록 합니다.

### Provider boundary

- 프로바이더 특이사항은 **어댑터 에지**에서 처리합니다. KIS TR_ID, 필드명 규칙, 페이로드 구조는 `src/kxt/clients/kis/` 내부에만 존재해야 합니다.
- 공개 모델에는 프로바이더 필드가 누출되지 않습니다.

### Honest implementation status

- 구현되지 않은 메서드는 `KXTUnsupportedError`로 명시합니다.
- 플레이스홀더 네임스페이스를 "프로덕션 준비됨"으로 표기하지 않습니다.

## Scope

### In scope

- 프로바이더 클라이언트와 브로커 중립 시장 데이터 계약.
- 현재 구현된 평평한 클라이언트 메서드.
- 타입드 capability 메타데이터.
- `native`를 통한 프로바이더 특이 기능 노출(탈출구).
- 구현 범위와 공백의 정직한 문서화.
- 기존 호환 계층 (`fetch_*`, `client.market`, `client.streams`) — 신규 권장은 아님.

### Out of scope

- Kafka·메시지 큐 파이프라인.
- 웹 서버·대시보드.
- 데이터베이스 영속화 계층.
- 오케스트레이션 스택.
- COM 프로바이더 지원.
- 미구현 프로바이더·패밀리를 "프로덕션 준비됨"으로 주장.
- 레포 대상 문서를 기획 문서로 전환.

## Current implementation status

- 유일하게 구현된 프로바이더는 `kis`.
- 작동 범위는 국내주식 시장 데이터 중심의 좁은 슬라이스.
- 그룹 네임스페이스(`client.market.*`)는 레거시 호환. 선호 형태는 평평한 `get_*`/`stream_*`.
- 미지원 메서드는 구현 전까지 명시적 미지원 상태를 유지합니다.

## See also

- [Style guide](style-guide.md) — 문서 톤앤매너.
- [Contributing](contributing.md) — 기여 절차.
