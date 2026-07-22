# Phase 13 — 콘텐츠 고도화

## Objective
Phase 1–12에서 파이프라인 안정화가 완료됨. 이제 콘텐츠 품질을 고도화한다.

## Requirements (from user)

### R1: 이미지 관련성 개선
- 현재 이미지 선택이 무작위(pollinations random)에 가까움
- 주제어(seed keyword)와 결이 같은 이미지를 검색/선택하도록 개선
- 검색 기반 이미지 소싱 또는 프롬프트 엔지니어링으로 관련성 확보

### R2: 마크다운 잔류 기호 제거
- 발행 후에도 HTML에 마크다운 기호(`**`, `*`, `- ` 등)가 보이는 현상 수정
- Hugo 빌드 전/후로 sanitization 강화 또는 markdown 렌더링 검증 추가

### R3: 표(table) 렌더링 깨짐 수정
- AI가 생성한 표가 Hugo Blowfish 테마에서 깨져 보임
- 표 포맷팅 검증 및 sanification 추가
- 가능하면 HTML `<table>` 변환 또는 Hugo shortcode 활용

### R4 (Noted): CSS
- 현재 CSS는 문제 없음. 별도 작업 불필요.

## Existing Pipeline Context
- `chain_drafter.py`: AI 초안 생성, `_strip_prompt_leak()`, `_sanitize_markdown_body()`
- `chain_publisher_core.py`: Hugo 발행 전 index.md 작성, `_verify_before_deploy()`
- `image/`: pollinations_client.py 등 이미지 생성 파이프라인
- `pillow_chart.py`: 차트 이미지 렌더링

## Test Baseline
- pytest 112/112
- 라이브 3/3 (리린샵 체인 #64)
