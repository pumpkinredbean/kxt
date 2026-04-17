# Contributing

`kxt`에 기여를 환영합니다. 알파 단계이므로 공개 API 변경은 담당자와 먼저 논의해주세요.

## 개발 환경

```bash
git clone https://github.com/pumpkinredbean/kxt.git
cd kxt
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,docs]"
```

## 테스트

```bash
pytest
```

현재 15개 테스트가 있으며, 모두 통과해야 합니다. 새 기능에는 해당 영역의 테스트를 추가하세요.

## 문서 빌드

```bash
mkdocs serve              # 로컬 프리뷰 http://127.0.0.1:8000
mkdocs build --strict     # 빌드 검증 (깨진 링크를 에러로 처리)
```

문서 수정 PR은 `mkdocs build --strict`가 통과해야 합니다.

## 빌드 검증

릴리스 준비 전에:

```bash
python -m build
python -m twine check dist/*
```

## 커밋 규칙

- 한 커밋 = 한 논리 단위.
- 커밋 메시지는 현재형 영어 또는 한국어 어느 쪽이든 가능하지만, 프로젝트 내 스타일을 따라주세요.
- 시크릿, `.env`, 토큰 캐시는 절대 커밋 금지.

## PR 체크리스트

- [ ] `pytest` 통과
- [ ] `mkdocs build --strict` 통과 (문서 변경 시)
- [ ] 공개 API 변경이 있다면 `CHANGELOG` 또는 릴리스 노트에 반영
- [ ] 한국어 문서는 [Style Guide](style-guide.md)를 따름
- [ ] 프로바이더 특이사항이 공개 모델로 누출되지 않았는지 확인

## 보고

- 버그: <https://github.com/pumpkinredbean/kxt/issues>
- 보안 이슈는 공개 이슈가 아닌 비공개 채널로 보고해주세요.
