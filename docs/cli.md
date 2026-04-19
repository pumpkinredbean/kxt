# CLI

`kxt` CLI는 라이브러리와 동일한 공개 메서드를 얇게 감싼 커맨드라인 래퍼입니다. 실제 네트워크 호출 경로는 라이브러리와 같고, 결과는 JSON으로 stdout에 출력됩니다.

## Verify installation

```bash
kxt --help
kxt doctor
```

`kxt doctor`는 자격증명 환경변수 상태를 점검합니다.

## Authentication

CLI는 시크릿을 플래그로 받지 않습니다. 반드시 환경변수를 사용하세요 ([Authentication](getting-started/authentication.md) 참조).

## General commands

```bash
kxt capabilities                               # 지원 메서드 매트릭스
kxt doctor                                     # 자격증명/환경 점검
```

## Market data

```bash
kxt quote 005930 --provider kis
kxt bars 005930 --provider kis --timeframe day --start 2025-04-01 --end 2025-04-14
kxt bars 005930 --provider kis --timeframe 5m
kxt recent-trades 005930 --provider kis --limit 5
kxt orderbook 005930 --provider kis
kxt orderbook 005930 --provider kis --stream --count 5
kxt market-status --provider kis --symbol 005930
kxt investor-flow 005930 --provider kis
kxt trades 005930 --provider kis --count 5
```

`--stream` 없이 사용한 `--count` 옵션은 무시됩니다. `recent-trades`는 당일 국내주식 체결만 지원합니다. `investor-flow`는 장 마감 이후 공개되는 정규장 집계입니다.

## Account & orders

계좌번호(CANO)와 상품코드가 필요합니다. `KIS_ACCOUNT_NO`, `KIS_ACCOUNT_PRODUCT_CODE` 환경변수로도 넣을 수 있고, 플래그가 우선합니다.

```bash
kxt balance         --account-no 12345678 --account-product-code 01
kxt positions       --account-no 12345678 --account-product-code 01
kxt buying-power 005930 --price 70000 \
                    --account-no 12345678 --account-product-code 01
kxt open-orders     --account-no 12345678 --account-product-code 01
kxt order-history   --start 2025-01-01 --end 2025-01-31 \
                    --account-no 12345678 --account-product-code 01
```

## Orders

```bash
kxt place-order 005930 --side BUY --order-type LIMIT \
  --quantity 1 --limit-price 70000 \
  --account-no 12345678 --account-product-code 01

kxt cancel-order --order-id 0000000123 --origin-org-no 01234 \
  --account-no 12345678 --account-product-code 01

kxt modify-order --order-id 0000000123 --origin-org-no 01234 \
  --quantity 1 --limit-price 70500 \
  --account-no 12345678 --account-product-code 01
```

## Fill notification stream

HTS ID가 필요합니다 (`KIS_HTS_ID`).

```bash
kxt order-events --hts-id myhtsid --count 5 \
  --account-no 12345678 --account-product-code 01
```

## Output format

`kxt quote`의 예:

```json
{
  "occurred_at": "2025-04-14T00:00:00+00:00",
  "last": "71000",
  "open": "70900",
  "high": "71400",
  "low": "70500",
  "previous_close": "70900",
  "change": "100",
  "change_rate": "0.14",
  "volume": "10203040"
}
```

## See also

- [Unified API overview](unified-api/overview.md) — 동일 메서드의 라이브러리 호출 형태.
- [KIS provider](providers/kis.md)
