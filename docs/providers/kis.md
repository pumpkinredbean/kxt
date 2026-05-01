# KIS Provider

Korea Investment & Securities(한국투자증권) OpenAPI 어댑터입니다. 현재 `kxt`의 유일한 프로바이더이며, 국내주식 시세와 계좌·주문 기능을 담당합니다.

## Official documentation

- 포털: <https://apiportal.koreainvestment.com/>
- API 서비스: <https://apiportal.koreainvestment.com/apiservice>

## Authentication

- `app_key`, `app_secret`이 필수입니다.
- 계좌 기반 메서드(주문·잔고)는 `account_no`, `account_product_code`가 필요합니다.
- 체결 알림 스트림(`stream_order_events`)은 `hts_id`가 필요합니다.
- SDK는 모두 `KISClient(...)`의 명시적 키워드 인자로 받습니다. 환경변수에 관여하지 않습니다.
- CLI는 `KIS_APP_KEY`, `KIS_APP_SECRET`, `KIS_ACCOUNT_NO`, `KIS_ACCOUNT_PRODUCT_CODE`, `KIS_HTS_ID` 환경변수를 사용합니다 ([CLI 레퍼런스](../cli.md)).
- 토큰은 로컬 캐시에 저장되어 만료 직전까지 재사용됩니다.
- 샌드박스는 현재 연결되어 있지 않습니다. `sandbox=True` 전달 시 `KXTUnsupportedError`가 발생합니다.

자세한 설정은 [Authentication](../getting-started/authentication.md)을 참조하세요.

## Supported methods matrix

| 카테고리 | 메서드 | 지원 | 비고 |
|---|---|:---:|---|
| Market data | `get_quote` | ✅ | 최상위 호가 필드는 제외 (호가창은 `get_orderbook` 사용) |
| Market data | `get_bars` | ✅ | 일/주/월/년/분봉. 국내주식 |
| Market data | `get_orderbook` | ✅ | 호가창 스냅샷 |
| Market data | `get_recent_trades` | ✅ | 당일 국내주식 체결만 |
| Market data | `get_market_status` | ✅ | 시세 payload 상태 필드에서 파생 |
| Market data | `get_market_calendar` / `is_market_open` | ✅ | 국내시장 휴장일/거래일 캘린더 |
| Market data | `get_investor_flow` | ✅ | 정규장 집계, 장 마감 이후 공개 |
| Batch analytics | `get_rankings` | ✅ | 거래량·거래대금·등락률·시가총액·체결강도·관심종목·공매도·신용잔고·호가잔량 |
| Batch analytics | `get_program_trade` | ✅ | 종목별 체결/일별, 시장 종합 시간/일별 |
| Batch analytics | `get_condition_searches` | ✅ | HTS 서버저장 조건검색 목록, HTS ID 필요 |
| Batch analytics | `get_condition_search_results` | ✅ | 조건검색 결과, 조건당 KIS 제한 적용 |
| Batch analytics | `get_investor_trends` | ✅ | 종목별 투자자매매동향 일별·외국인/기관 추정 |
| Batch analytics | `get_foreign_institution_rankings` | ✅ | 외국인/기관 매매종목 가집계 |
| Streams | `stream_trades` | ✅ | 실시간 체결 (WSS) |
| Streams | `stream_orderbook` | ✅ | 실시간 호가 (WSS) |
| Streams | `stream_program_trades` | ✅ | KRX/NXT/통합 scope |
| Streams | `stream_member_flow` | ✅ | KRX/NXT/통합 scope |
| Streams | `stream_market_status` | ✅ | KRX/NXT/통합 scope |
| Streams | `stream_order_events` | ✅ | 주문 체결 알림 (HTS ID 필요) |
| Streams | `stream_order_updates` | ✅ | 주문 상태 |
| Streams | `stream_fill_updates` | ✅ | 체결 업데이트 |
| Account | `get_account_overview` | ✅ | |
| Account | `get_balance` | ✅ | |
| Account | `get_positions` | ✅ | |
| Account | `get_buying_power` | ✅ | |
| Account | `get_open_orders` | ✅ | |
| Account | `get_order_history` | ✅ | |
| Trading | `submit_order` | ✅ | 현금 매수/매도 |
| Trading | `cancel_order` | ✅ | |
| Trading | `modify_order` | ✅ | |
| Unsupported | 해외주식·파생 | ❌ | 이번 슬라이스 범위 외 |

## Key KIS TR_IDs

| 용도 | TR_ID |
|---|---|
| 시세(현재가) | `FHKST01010100` |
| 호가창 | `FHKST01010200` |
| 일/주/월/년봉 | `FHKST03010100` |
| 당일 분봉 | `FHKST03010200` |
| 과거 분봉 | `FHKST03010230` |
| 당일 체결 | `FHPST01060000` |
| 휴장일 조회 | `CTCA0903R` |
| 투자자 플로 | `FHKST01010900` |
| 거래량 순위 | `FHPST01710000` |
| 등락률 순위 | `FHPST01700000` |
| 시가총액 순위 | `FHPST01740000` |
| 체결강도 순위 | `FHPST01680000` |
| 공매도 순위 | `FHPST04820000` |
| 신용잔고 순위 | `FHKST17010000` |
| 프로그램매매 종목 | `FHPPG04650101` |
| 프로그램매매 종목 일별 | `FHPPG04650201` |
| 프로그램매매 종합 시간 | `FHPPG04600101` |
| 프로그램매매 종합 일별 | `FHPPG04600001` |
| 조건검색 목록 | `HHKST03900300` |
| 조건검색 결과 | `HHKST03900400` |
| 잔고 | `TTTC8434R` |
| 매수 가능 금액 | `TTTC8908R` |
| 미체결 주문 | `TTTC8036R` |
| 주문 이력 | `TTTC8001R` |
| 현금 매수 | `TTTC0802U` |
| 현금 매도 | `TTTC0801U` |
| 정정/취소 | `TTTC0803U` |
| 실시간 체결 (WS) | `H0STCNT0` |
| 실시간 호가 (WS) | `H0STASP0` |
| 실시간 프로그램매매 (WS) | `H0STPGM0` / `H0NXPGM0` / `H0UNPGM0` |
| 실시간 회원사 (WS) | `H0STMBC0` / `H0NXMBC0` / `H0UNMBC0` |
| 실시간 장운영정보 (WS) | `H0STMKO0` / `H0NXMKO0` / `H0UNMKO0` |
| 체결 통보 (WS) | `H0STCNI0` |

## Rate limits

KIS OpenAPI의 공식 한도를 따릅니다. [Rate limits](../getting-started/rate-limits.md)를 참고하세요.

## Constraints

- 국내주식(장내·코스닥) 중심. 해외·파생은 후속 슬라이스.
- `get_investor_flow`는 장 마감 이후 공개되는 정규장 집계입니다. 실시간이 아닙니다.
- `get_market_status`는 시세 payload의 상태 필드에서 파생합니다.
- `get_market_calendar`는 KIS `chk-holiday`를 사용하며, `get_market_status`나 빈 `get_bars` 응답과 의미가 다릅니다.
- 다운스트림 애플리케이션은 필요한 날짜 범위의 캘린더를 자체 캐시에 저장해 휴장일과 데이터 공백을 구분하는 것이 좋습니다.
- `stream_market_status`는 KIS 장운영정보 WebSocket 채널을 구독합니다.
- KIS HTS 화면 코드와 `FID_*` 필터를 직접 제어해야 하는 분석 API는 `client.native.get_domestic_analysis(...)`로 raw output을 조회할 수 있습니다.

## See also

- [get_bars](../unified-api/market-data/get-bars.md) — KIS 봉 엔드포인트가 어떻게 매핑되는지.
- [Schemas](../reference/schemas.md) — 응답 DTO 구조.
