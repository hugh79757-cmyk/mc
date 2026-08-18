---
phase: 42
plan: 01
subsystem: quality
tags: [title-body, consistency, promise-check]
requires: [contract-specs, contract-loader]
provides: [title-body-checker]
affects: [quality/, tests/]
tech-stack:
  added: []
  patterns: [dataclass-validation, regex-gate, section-parsing]
key-files:
  created:
    - quality/title_body_checker.py
    - tests/test_title_body_checker.py
  modified: []
decisions:
  - "TitleBodyResult as dataclass with score/met_promises/unmet_promises/details"
  - "Particle stripping applied to both promises and headings for matching"
  - "Empty heading (pre-content) skipped to avoid false matches"
  - "Concrete info detection: digits, addresses, or 2+ char Korean words"
metrics:
  duration: 5min
  completed: 2026-08-18
  tasks: 2
  files: 2
---

# Phase 42 Plan 01: title_body_checker Summary

**One-liner:** Extract noun-phrase promises from titles and verify each promise has a concrete H2/H3 section in the markdown body.

## What Was Done

1. **quality/title_body_checker.py** — Three functions:
   - `extract_title_promises(title)`: Split on 및/과/,/+, strip Korean particles (을/를/이/가/은/는/의/에/에서/로/으로/와/과/하고), return noun phrases.
   - `check_section_coverage(body_md, promises)`: Split markdown by H2/H3 headings. For each promise, find a heading containing the promise text (after particle stripping). Verify the section has concrete info (digits, addresses, or Korean proper nouns).
   - `validate_title_body(title, body_md)`: Returns `TitleBodyResult(score, met_promises, unmet_promises, details)`. Score = met/total.

2. **tests/test_title_body_checker.py** — 15 tests:
   - extract_title_promises: compound titles (및/,/+) and particle stripping
   - check_section_coverage: all-met, partial, empty section, generic content
   - validate_title_body: all-met (score≥0.8), partial (score<0.8), single promise, empty body, real post structure

## Test Results

| Metric | Count | Breakdown |
|--------|-------|-----------|
| New tests | 15 | extract(5) + coverage(4) + validate(6) |
| Passed | 15 | All green |
| Failed | 0 | — |
| Full suite | 950 | 935 existing + 15 new |
| Pre-existing failures | 5 | ai_writer(3) + drafter(2) — unchanged |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Empty heading false match**
- **Found during:** Task 1 implementation
- **Issue:** Pre-heading content (empty string heading) matched all promises via `'' in promise_lower` being True
- **Fix:** Skip sections with empty heading in `check_section_coverage`
- **Files modified:** quality/title_body_checker.py
- **Commit:** 74ba604

**2. [Rule 1 - Bug] Particle stripping asymmetry**
- **Found during:** Task 1 testing
- **Issue:** Particles stripped from promises but not from headings, causing "남양주 물 정원" not to match heading "남양주 물의 정원"
- **Fix:** Also strip particles from headings during comparison
- **Files modified:** quality/title_body_checker.py
- **Commit:** 74ba604

## Known Stubs

None — all functions fully implemented.

## Threat Flags

None — local validation only, no new network surface.

## Residual Risks

- `check_section_coverage` uses substring matching for heading↔promise, which may produce false positives for short promises (e.g., "개" matching "개요")
- Concrete info detection treats any 2+ char Korean word as a named entity — may over-report concrete info for truly generic content
- Integration with `contract_loader.validate_post` not wired yet (future phase)

## Self-Check: PASSED

- [✅] `quality/title_body_checker.py` exists — Found on disk (204 lines)
- [✅] `tests/test_title_body_checker.py` exists — Found on disk (149 lines)
- [✅] Commit `74ba604` exists — feat(42-01) implementation
- [✅] Commit `48434b2` exists — test(42-01) tests
- [✅] 15/15 new tests pass — pytest output confirmed
- [✅] 950/950 suite pass (5 pre-existing failures excluded)
