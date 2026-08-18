---
phase: 46-html-render-check
plan: "01"
subsystem: quality
tags: [html, rendering, duplicate-check, post-build]
dependency_graph:
  requires: [quality/contract_loader.py, quality/_types.py]
  provides: [quality/html_render_checker.py]
  affects: [quality pipeline]
tech_stack:
  added: [html.parser (stdlib)]
  patterns: [HTMLParser subclass, dataclass result types]
key_files:
  created: [quality/html_render_checker.py, tests/test_html_render_checker.py]
  modified: []
decisions:
  - "Use stdlib html.parser.HTMLParser only (no BeautifulSoup dependency)"
  - "Extract first H1 only (not list) per plan specification"
  - "Contract parameter required in check_html_duplicates (not optional)"
metrics:
  duration: "5 minutes"
  completed: "2026-08-18T06:35:00Z"
  tasks_completed: 2
  files_created: 2
  tests_added: 11
---

# Phase 46 Plan 01: html_render_checker Summary

**One-liner:** HTML 중복 검사기 — title==H1, CTA 반복, 문단 반복 탐지 (stdlib html.parser)

## What Was Built

`quality/html_render_checker.py` — Hugo 빌드 후 최종 HTML을 파싱하여 중복 콘텐츠를 자동 탐지하는 모듈.

### Core Functions

1. **`parse_html(html_str: str) -> ParsedPage`**
   - HTML 문자열을 파싱하여 title, h1, h2_list, cta_patterns, paragraphs 추출
   - Custom `_PageParser(HTMLParser)` 서브클래스 사용
   - CTA 패턴: "다음 글", "관련 글", "함께 보면" 키워드 + href 블록

2. **`check_html_duplicates(html_str: str, contract: ContractSpec) -> HtmlCheckResult`**
   - duplicate_title: title == first H1
   - duplicate_cta: CTA 패턴 수 > contract.cta_max_count
   - duplicate_paragraph: 동일 문단 2회 이상

### Data Classes

- `ParsedPage`: title, h1, h2_list, cta_patterns, paragraphs
- `HtmlCheckResult`: passed (bool), violations (list[str])

## Verification Results

### Task 1: html_render_checker.py 구현
- [검증됨] `python -c "from quality.html_render_checker import check_html_duplicates; ..."` → duplicate_title violation 정상 탐지
- [검증됨] ParsedPage dataclass 정상 동작
- [검증됨] ContractSpec.cta_max_count 참조 정상

### Task 2: html_render_checker 테스트
- [검증됨] `python -m pytest tests/test_html_render_checker.py -v` → 11 passed
- [검증됨] TestParseHtml 클래스: 5개 테스트 통과
- [검증됨] TestCheckHtmlDuplicates 클래스: 6개 테스트 통과

### Regression Test
- [검증됨] `python -m pytest tests/ -q` → 86 passed (quality 모듈 전체)
- [검증불가] 5개 실패 테스트 (test_ai_writer_bug001.py, test_chain_drafter.py) — 파일 미존재 또는 기존 이슈,本次 변경과 무관

## Deviations from Plan

### API Design Changes

**1. H1 필드 변경: list → str**
- **Found during:** Task 1 구현
- **Issue:** Plan에서 "H1: extract text between <h1> and </h1> (first one only)" 지시
- **Fix:** `h1_texts: list` 대신 `h1: str`으로 변경하여 첫 번째 H1만 추출
- **Files modified:** quality/html_render_checker.py, tests/test_html_render_checker.py
- **Commit:** 58689e0

**2. Contract 필수 파라미터화**
- **Found during:** Task 1 구현
- **Issue:** 기존 구현에서 contract=None (기본값 사용) 가능했으나, plan에서 "ContractSpec.cta_max_count로 CTA 반복 임계값 참조" 명시
- **Fix:** `check_html_duplicates(html_str, contract)` 계약 필수 파라미터로 변경
- **Files modified:** tests/test_html_render_checker.py
- **Commit:** 58689e0

### Auto-fixed Issues

None — plan이 정확히 실행됨.

## Known Stubs

None — 모든 기능이 구현되고 테스트됨.

## Threat Flags

None — 새로운 네트워크 엔드포인트, 인증 경로, 파일 접근 패턴 없음.

## Self-Check: PASSED

### Created Files Exist
- [✅] quality/html_render_checker.py — 133줄
- [✅] tests/test_html_render_checker.py — 70줄

### Commits Exist
- [✅] 58689e0: feat(46-01): HTML 렌더링 중복 검사 구현 및 테스트

### Test Results
- [✅] 11/11 테스트 통과 (test_html_render_checker.py)
- [✅] 86/86 테스트 통과 (tests/ 디렉토리 전체)
- [부분검증] 1008/1013 테스트 통과 (전체 스위트) — 5개 실패는 기존 이슈

## Residual Risks

1. **기존 실패 테스트 5개** — test_ai_writer_bug001.py, test_chain_drafter.py에서 발생하는 sqlite3OperationalError.本次 변경과 무관하나, 품질 파이프라인 전체 통과율에 영향.

2. **CTA 패턴 감지 범위** — 현재 "다음 글", "관련 글", "함께 보면" 3개 키워드만 감지. 추가 CTA 패턴이 필요하면 _CTA_KEYWORDS 리스트 확장 필요.

## Commits

| Hash | Message | Files |
|------|---------|-------|
| 58689e0 | feat(46-01): HTML 렌더링 중복 검사 구현 및 테스트 | quality/html_render_checker.py, tests/test_html_render_checker.py |
