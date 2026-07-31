# Phase 26 Plan 03-05: 최종 검증 — 전체 스위트 + 핵심 기능 smoke 테스트 Summary

**Plan:** 26-03-05
**Type:** execute (wave 4)
**Status:** Complete
**Duration:** ~20 min
**Completed:** 2026-08-01

## One-liner

전체 테스트 스위트 실행(754 passed) + `test_verification.py`(17 tests) 신설 — 리팩터링(단일 진실 공급원 통합) 이후 frontmatter/링크 감지/카드 생성/이미지 파이프라인이 그대로 동작함을 스모크 테스트로 고정. 회귀 0건.

## What Was Done

1. **Task 1 — 전체 테스트 스위트 실행** (`python -m pytest -q`): **754 passed** in 21.69s. 산출: 737 (03-04 종료 시점) + 17 (test_verification.py) = 754. 기존 테스트 회귀 0건.
2. **Task 2 — `test_verification.py`** (146 lines, 17 tests, 네트워크 호출 없음):
   - **frontmatter handling** (4): `ensure_frontmatter` 추가/기존 보존, `ensure_frontmatter_closer`, `extract_description` 길이 제한
   - **link detection** (5): `extract_domain`, `normalize_url`(트래킹/fragment 제거 + scheme/host 소문자화), `strip_tracking_params`, `LinkFinder` 마크다운 링크 추출 + **코드 펜스 내 링크 제외** (T-26-10 입력 가드)
   - **card generation** (2): `CardGenerator.generate_next_card_spec` 스펙 dict (type/title/url/cta), `CardInjector.fix_unclosed_fences` 정적 메서드 유지 (MarkdownProcessor 위임 대상)
   - **image fetching** (4, 구조 smoke): Unsplash/Pexels 프로바이더 `BaseImageProvider` 인스턴스 + `fetch`/`validate` 존재 + `validate(None) is False`(로컬 검증 로직), `search_body_image` 레거시 유지, `build_contextual_prompt`/`build_full_prompt`
   - **markdown pipeline 연동** (2): `_sanitize_markdown_body` 존재, `_clean_markdown_symbols` → `MarkdownProcessor.clean_symbols` 위임 일치

## Files Changed

| File | Action |
|------|--------|
| `test_verification.py` | created (146 lines, 17 tests) |

(plan 파일 목록은 빈 값 — `files_created`/`files_modified` 에 항목 없음, 실제 생성 파일은 위 1건)

## Verification Results

| Command | Result |
|---------|--------|
| `python -m pytest test_verification.py -v` | **17 passed** in 0.15s (Plan Task 2 verify) |
| `python -m pytest -q` (full suite) | **754 passed** in 21.69s — 산출: 737 + 17 = 754 (Plan Task 1 verify). 기존 회귀 0건 |
| import sanity (staged chain_publisher_core module load) | 03-04 에서 확인, 03-05 에서는 chain_publisher_core/markdown_processor/프로바이더 import 가 test 수집 시점에 검증됨 |

## Deviations from Plan

1. **[Test 코드 수정] API 시그니처 오가정 3건** — 초기 smoke 테스트가 실제 시그니처와 불일치:
   - `normalize_url("example.com")` 가 scheme 을 붙이지 않음 (scheme 추가는 `ensure_scheme` 의 역할) → [TEST CODE] 테스트를 실제 동작(트래킹/fragment 제거 + 소문자화)에 맞게 수정
   - `generate_next_card_spec` 반환 키는 `type` (아님 `card_type`) → [TEST CODE] 수정
   - `build_contextual_prompt` 시그니처는 `title`/`post_angle`/`step`/`chain_type` 키워드 (아님 `topic_type`) → [TEST CODE] 수정
   - 생산 코드 변경 없음 — production 로직은 정확히 그대로
2. **plan 의 "251 tests" 수치는 stale** — 실측 기준선 665 (orchestrator 사전 확인) → 본 플랜 종료 시점 **754** (665 + 03-02:28 + 03-03:19 + 03-04:25 + 03-05:17 = 754 합산 일치).
3. **`<output>` 경로 무시** — `.planning/phases/26-12/` 는 stale. repo 컨벤션 `.planning/phase-26/03-05-SUMMARY.md` 에 작성.

## Known Stubs

None — 스모크 테스트가 실제 구현에 연결됨. `validate(None) is False` 는 로컬 검증 로직만 확인(네트워크 제외) — 의도된 구조 테스트.

## Threat Flags

None — T-26-28 (테스트 커버리지) 완화: 신규 17개 스모크 테스트가 핵심 기능 5개 영역을 고정. 신규 네트워크/파일 접근/인증 경로 없음 (네트워크 테스트 아예 없음).

## Self-Check: PASSED

- `[ -f test_verification.py ]` → FOUND
- `git log | grep af8ccad` → FOUND (test 커밋 존재)
- `python -m pytest -q` → 754 passed (실행 출력으로 검증)

## Residual Risk

- 스모크 테스트는 "동작한다"의 경량 증명 — 깊은 회귀 커버리지는 개별 모듈 테스트(03-02~03-04 산출물 72 tests)가 담당. 
- 이미지 파이프라인은 구조만 검증(네트워크 미호출) — 실제 API 호출 경로는 수동/라이브 검증 필요. [부분검증]
- Wave 1 WIP (constants 통합 등 chain_publisher_core 상단, mc/leak_defense.py, test_chain_publisher_core_constants.py 미추적) 여전히 미커밋 — 오케스트레이터 Wave 1 통합 커밋에서 처리 예정.
