# Installation

## Requirements

- Python 3.11 이상 (3.11, 3.12 테스트됨)
- macOS, Linux, Windows
- KIS OpenAPI 앱키·앱시크릿 (실거래 호출 시)

## Install from PyPI

`kxt`는 현재 알파 릴리스입니다. 설치 시 `--pre` 플래그를 반드시 포함해야 합니다.

```bash
pip install --pre kxt
```

1.0 정식 릴리스 이후에는 `--pre` 없이 설치 가능합니다.

## Virtual environment (recommended)

프로젝트별 의존성 격리를 위해 가상환경 사용을 권장합니다.

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install --pre kxt
```

## Verify installation

```bash
python -c "import kxt; print(kxt.__all__[:5])"
```

CLI 엔트리포인트도 함께 설치됩니다.

```bash
kxt --help
kxt doctor
```

## Development install (from source)

저장소를 클론해서 직접 편집하며 작업할 때 사용합니다.

```bash
git clone https://github.com/pumpkinredbean/kxt.git
cd kxt
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

문서 빌드까지 하려면 `docs` extras를 추가로 설치합니다.

```bash
pip install -e ".[dev,docs]"
mkdocs serve  # http://127.0.0.1:8000
```

## Dependencies

런타임 의존성은 두 개뿐입니다.

| 패키지 | 용도 |
|---|---|
| `httpx` | HTTP 트랜스포트 |
| `websockets` | 실시간 스트림 트랜스포트 |

## Next steps

- [Authentication](authentication.md) — KIS 앱키 발급과 환경변수 설정.
- [Quickstart](quickstart.md) — 5분 안에 첫 시세 호출.
