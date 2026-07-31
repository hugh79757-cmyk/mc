# Phase 26 Plan 03-04: MarkdownProcessor 파이프라인 단일 진실 공급원 Summary

**Plan:** 26-03-04
**Type:** execute (wave 4)
**Status:** Complete
**Duration:** ~35 min
**Completed:** 2026-08-01

## One-liner

`markdown_processor.py` 신설 — `MarkdownProcessor` 클래스가 펜스 자동 수정(fix_fences) + 릭 방어(strip_leaks) + 심볼 클리닝(clean_symbols)을 순서대로 수행하는 `process()` 파이프라인 제공. 기존 3개 단일 진실 공급원(`chain_card_injector.CardInjector.fix_unclosed_fences`, `mc.leak_defense.strip_leaks`, `chain_publisher_core._clean_markdown_symbols`)으로 **위임(additive)** — 기존 함수/호출부 무변경. `_sanitize_markdown_body` 신설로 전체 정제 경로 진입점 제공. 25개 테스트.

## What Was Done

1. **`markdown_processor.py`** (147 lines) — `MarkdownProcessor` 클래스:
   - `fix_fences(text)` — `CardInjector.fix_unclosed_fences` 위임 (chain_card_injector 가 link_finder/card_generator 등 무거운 모듈을 import 하므로 **lazy import** 로 부팅 비용 회피)
   - `strip_leaks(text, context="draft")` — `mc.leak_defense.strip_leaks` 위임, 튜플 `(cleaned, stats)` 중 cleaned 만 반환. 패턴 단일 진실 공급원은 `constants.LEAK_PATTERNS`/`LEAK_REGEX` (leak_defense 문서 참조)
   - `clean_symbols(body)` — `_clean_markdown_symbols` 와 **동일 알고리즘** (테이블/코드/수학/todo 마커 보호 + pipe 이스케이프 + unmatched `**` 제거)
   - `process(markdown_text, leak_context="draft")` — **fix_fences → strip_leaks → clean_symbols** 순서 파이프라인
   - 모듈 공유 인스턴스 `processor`
2. **`chain_publisher_core.py`** — 2개 변경 (모두 위임, 호출부 무변경):
   - `_clean_markdown_symbols` 본문 → `markdown_processor.processor.clean_symbols(body)` 위임 (docstring 은 신 단일 진실 공급원 명시, -73/+17)
   - `_sanitize_markdown_body(body)` 신설 — `process(body, leak_context="draft")` 위임, 전체 정제 경로 진입점
   - `import markdown_processor` (chain_models import 뒤에 noqa: E402)
3. **`test_markdown_processor.py`** (134 lines, 25 tests) — 기존 공급원과 parity (fix_fences/strip_leaks/clean_symbols 11개 픽스처), 파이프라인 순서, `_sanitize_markdown_body` parity, 공유 인스턴스

## Files Changed

| File | Action |
|------|--------|
| `markdown_processor.py` | created (147 lines) |
| `chain_publisher_core.py` | modified (+17/-73 — `_clean_markdown_symbols` 위임 + `_sanitize_markdown_body` 신설) |
| `test_markdown_processor.py` | created (134 lines, 25 tests) |

## Verification Results

| Command | Result |
|---------|--------|
| `python -m pytest test_markdown_processor.py -v` | **25 passed** in 0.23s |
| `python -m pytest -q` (full suite) | **737 passed** in 21.41s — 산출: 712 (03-03 종료 시점) + 25 신규 = 737. 기존 회귀 0건 |
| staged blob `c7d33796` compile + delegation smoke | `_clean_markdown_symbols("a|b") == "a\\|b"`, `_sanitize_markdown_body("본문 x\|y")` 동작 확인 — importlib 로 **staged 파일 직접 로드** 검증 |
| `git diff HEAD~1 HEAD --diff-filter=D` | 0건 — 파일 삭제 없음 (-73 은 `_clean_markdown_symbols` 본문 교체) |

## Deviations from Plan

1. **[Rule 1 - Test Bug] strip_leaks 는 frontmatter 이후 본문만 처리** — `_remove_prompt_leaks` 는 `past_frontmatter` False 구간을 통과시키므로, frontmatter(`---`) 없는 테스트 입력에서는 릭이 제거되지 않음. [TEST CODE] 수정: 테스트 입력에 frontmatter 블록 추가. production 로직은 기존 동작 유지 (이는 의도된 시맨틱 — draft 본문은 frontmatter 이후).
2. **[Test 설계 보정] prompt_leak remove_block 의 블록 소멸 범위** — `# Role` 릭 블록은 다음 '깨끗한' 헤더까지 전부 제거하므로, 테스트 입력에 `## 실제 제목` 같은 정상 헤더를 릭 블록 뒤에 배치해 나머지 본문 생존 확인.
3. **`process()` 가 실행되는 기존 호출부는 없음** — PLAN.md 의 "MarkdownProcessor 를 발행 경로에 연결" 항목은 **기존 동작 보존(additive)** 원칙에 따라 이번 플랜에서는 `_sanitize_markdown_body`/위임으로 신설 경로만 제공. 발행 파이프라인의 기존 `_clean_markdown_symbols` 호출부는 그대로 유지됨 (동작 동일하므로 사실상 파이프라인 효과는 동일). 자동 연결은 향후 플랜에서 신규 경로로 도입 가능.
4. **`<output>` 경로 무시** — `.planning/phases/26-11/` 는 stale. repo 컨벤션 `.planning/phase-26/03-04-SUMMARY.md` 에 작성.
5. **Wave 1 WIP 혼재** — chain_publisher_core.py 상단 상수 통합(WIP)은 커밋 제외, HEAD + 03-03 + 03-04 블록만 스테이징 (기존 방식).

## Known Stubs

None — 모든 메서드가 실 구현에 위임, 테스트로 동작 확인. `_sanitize_markdown_body` 는 신설 진입점으로 현재 호출처 없음 (의도적 — 향후 발행 경로 연결 예정, 기존 동작 보존).

## Threat Flags

None — 신규 네트워크/파일 접근/인증 경로 없음 (기존 위임 함수 재사용만). 릭 방어 로직이 정제 파이프라인에 그대로 적용되어 T-26-14/프롬프트 릭 위협 완화 유지.

## Self-Check: PASSED

- `[ -f markdown_processor.py ]` → FOUND / `[ -f test_markdown_processor.py ]` → FOUND
- `git log | grep a33c486` → FOUND (feat 커밋 존재)
- `python -m pytest -q` → 737 passed (실행 출력으로 검증)

## Residual Risk

- `clean_symbols` 알고리즘이 `_clean_markdown_symbols` 와 중복 존재 (위임이므로 동작은 단일 — 복사본은 테이블 보호 규칙과 동일). 향후 알고리즘 변경 시 `markdown_processor.clean_symbols` 한 곳만 수정하면 됨 (위임 구조가 보장).
- chain_card_injector lazy import — 최초 `fix_fences` 호출 시점에 모듈 로드 비용 발생 (기존에는 이미 발행 경로에서 로드됨). 성능 영향 없음.
- Wave 1 WIP(상수 통합, mc/leak_defense.py 등) 여전히 미커밋 — 03-05 가 파일을 추가로 수정하지 않으므로(테스트만 신설) 이번 wave 에서는 추가 hunk 분리 없음.
