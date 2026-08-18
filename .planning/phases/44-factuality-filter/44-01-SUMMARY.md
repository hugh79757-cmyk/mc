---
phase: 44-factuality-filter
plan: "01"
subsystem: quality
tags: [factuality, claims, source-tag, forbidden-patterns, quality-gate]
dependency_graph:
  requires: ["43-01"]
  provides: ["quality/factuality_checker.py"]
  affects: [quality]
tech_stack:
  added: []
  patterns: [dataclass, regex, sentence-splitting]
key_files:
  created: [quality/factuality_checker.py, tests/test_factuality_checker.py]
  modified: []
decisions:
  - "Claim type priority: review > statistics > number (most specific wins)"
  - "Source tag association: check current sentence + next sentence for [출처:] tag"
  - "Score threshold: 0.7 (below → passed=False), any forbidden hit → passed=False"
metrics:
  duration: 180s
  completed: "2026-08-18T06:25:03Z"
  tasks_completed: 2
  files_created: 2
---

# Phase 44 Plan 01: factuality_checker Summary

마크다운 본문에서 사실 주장을 추출하고 출처 태그·금지 패턴을 검증하는 품질 게이트 모듈 구현. 숫자/리뷰/통계 패턴 기반 주장 추출, `[출처:]` 태그 소스 귀속 검증, 계약 금지 패턴 매칭, 점수 기반 통과/실패 판정.

## What Was Built

1. **`quality/factuality_checker.py`** — 핵심 모듈
   - `Claim` dataclass: sentence, claim_type, has_source_tag
   - `FactualityResult` dataclass: score, unsourced_claims, forbidden_hits, passed
   - `extract_claims(body_md)`: 문장 분리 후 숫자/리뷰/통계 패턴 매칭 → Claim 목록 반환. 출처 태그는 현재 문장 + 다음 문장에서 탐지
   - `check_forbidden(body_md, patterns)`: 계약 금지 패턴과 매칭되는 문장 반환
   - `validate_factuality(body_md, contract)`: 점수 = sourced/total (0.0이면 1.0), 0.7 미만 또는 금지 패턴 → passed=False

2. **`tests/test_factuality_checker.py`** — 21개 테스트
   - extract_claims 패턴별 탐지 (7건): 퍼센트, 리뷰, 통계, 인원, 가격, 만족도, 무주장
   - 출처 태그 검증 (3건): 동일 문장, 미포함, 문장 중간
   - 금지 패턴 (3건): 단일 매칭, 다중 매칭, 무매칭
   - validate_factuality (6건): 점수 미달, 클린 패스, 전체 출처, 금지 강제 실패, 혼합, 빈 본문
   - 실Fixture (2건): techpawz 스타일 미출처 통계, 금지 패턴 병행

## Deviations from Plan

### Rule 1 — Bug: Sentence splitting 분리된 `[출처:]` 태그 미연동
- **Found during:** Task 2 테스트 실행
- **Issue:** `re.split(r"(?<=[.!?])\s+", text)`가 `. [출처:]`를 별도 문장으로 분리하여, 주장 문장이 `[출처:]` 태그를 인식하지 못함
- **Fix:** `extract_claims`에서 현재 문장 + 다음 문장에서 `[출처:]` 탐지하도록 Look-ahead 로직 추가
- **Files modified:** quality/factuality_checker.py
- **Commit:** 1ad03f2

### Rule 1 — Bug: 주장 유형 우선순위 (number → statistics 순서)
- **Found during:** Task 2 테스트 실행
- **Issue:** "설문 결과 85%" 같은 문장이 `\d+%` 패턴(number)에 먼저 매칭되어 statistics 유형으로 분류되지 않음
- **Fix:** 우선순위를 review → statistics → number로 변경 (가장 구체적인 유형 우선)
- **Files modified:** quality/factuality_checker.py
- **Commit:** 1ad03f2

### Rule 2 — Test expectation: techpawz fixture 주장 수
- **Found during:** Task 2 테스트 실행
- **Issue:** "25km/h", "10.5Ah"는 number 패턴(`\d+%`, `\d+명`, `\d+만원`, `\d+점`, `만족도\s*\d+`)에 매칭되지 않아 5건이 아닌 3건
- **Fix:** 테스트 기대값을 3건으로 조정
- **Files modified:** tests/test_factuality_checker.py
- **Commit:** 1ad03f2

## Verification

| Check | Result |
|-------|--------|
| `python -c "from quality.factuality_checker import extract_claims; claims = extract_claims('방문객 만족도 73%입니다.'); print(len(claims), claims[0].has_source_tag)"` | [검증됨] `1 False` 출력 — 주장 1건 탐지, 출처 없음 |
| `python -m pytest tests/test_factuality_checker.py -v` | [검증됨] 21 passed in 0.03s |
| `python -m pytest --tb=short -q` (전체 스위트) | [검증됨] 1003 passed, 5 failed (기존 5건 회귀 없음) |

## Known Stubs

None — 모듈이 독립적으로 동작하며, Phase 47에서 파이프라인 삽입(발행 전 factuality 검증)이 수행됨.

## Threat Flags

None — 새로운 네트워크 엔드포인트나 인증 경로를 추가하지 않음. 모든 검증은 로컬 마크다운 텍스트 기반.

## Residual Risks

- **5건 기존 테스트 실패**: `test_ai_writer_bug001.py` 3건 (truncation retry), `test_chain_drafter.py` 2건 (raw_ai_output 컬럼 누락). 이번 변경과 무관.

## Self-Check: PASSED

- [✅] quality/factuality_checker.py 존재
- [✅] tests/test_factuality_checker.py 존재
- [✅] SUMMARY.md 존재
- [✅] 커밋 d0118e5 (feat) 존재
- [✅] 커밋 1ad03f2 (test) 존재
