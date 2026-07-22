# Phase 13 — 콘텐츠 고도화 (Content Refinement)

## Objective
Phase 1–12에서 파이프라인 안정화가 완료됨. 이제 콘텐츠 품질을 고도화한다.

## Requirements (from user)

### R1: 이미지 관련성 개선
- 현재 이미지 선택이 무작위(pollinations random)에 가까움
- 주제어(seed keyword)와 결이 같은 이미지를 검색/선택하도록 개선
- 검색 기반 이미지 소싱: Unsplash/Pexels (landscape, no text overlay)
- 검색 실패/빈결과/레이트리밋 시 폴백: 기존 image_keyword Pollinations 경로 (W6 fallback 포함)
- 검색 결과 캐시 (24h TTL, key=keyword hash)
- API 키: `.env.common`에서 `UNSPLASH_ACCESS_KEY`, `PEXELS_API_KEY` → 하드코딩 금지
- 재시도 금지 (다음 발행에서 재시도)

### R2: 마크다운 잔류 기호 제거
- 발행 후에도 HTML에 마크다운 기호(`**`, `*`, `|`, `- ` 등)가 보이는 현상 수정
- Hugo 빌드 전 `_clean_markdown_symbols()` post-processing 추가
- 보호 대상: `<!--todo:image-->`, `<!--todo:chart-->`, 코드블록, 인라인 코드, math
- `_extract_clean_body()` 수정 금지

### R3: 표(table) 렌더링 깨짐 수정
- AI가 생성한 표가 Hugo Blowfish/PaperMod 테마에서 깨짐
- Hugo Goldmark GFM 표 기본 활성화 확인됨 (config.toml에 table=true 불필요)
- HTML `<table>` 변환 불필요 — GFM 표를 마크다운 그대로 유지
- `_clean_markdown_symbols()`에서 표 라인(`|` 시작) 보호

### Phase 13.1 (이월, 명시만)
- 이미지 캐시 히트율 대시보드
- 사이트별 이미지 전략 분기 (techpawz는 stock photo 부적합 가능성)

## Existing Pipeline Context
- `chain_drafter.py`: AI 초안 생성, `_strip_prompt_leak()`, `_sanitize_markdown_body()`
- `chain_publisher_core.py`: Hugo 발행 전 index.md 작성, `_verify_before_deploy()`
- `image/`: pollinations_client.py 등 이미지 생성 파이프라인
- `pillow_chart.py`: 차트 이미지 렌더링
- `config/prompts.yaml`: AI 프롬프트 템플릿

## Constraints
- 19/27 guard (`_NON_INTENDED_CHAINS`) 미건드림
- FM preservation (`_ensure_featureimage`) 미건드림
- W1~W6 코드 미건드림
- `_extract_clean_body()` 수정 금지 (예외: R3 (c) 케이스만)
- rerank=false 회귀 100% 유지
- pytest baseline: 112 → **120/120** 목표 (+8 신규)

## Test Baseline
- pytest 112/112 (현재)
- 목표: 120/120 (+8: Task 1.1:1 + Task 1.2:4 + Task 2.1:2 + Task 2.2:1)
- 라이브 3/3 (리린샵 체인 #64)
