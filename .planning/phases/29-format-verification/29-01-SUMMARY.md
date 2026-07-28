---
phase: 29
plan: 01
subsystem: audit
tags: [format-verification, audit, testing]
dependency_graph:
  requires: []
  provides: [audit-format-checks]
  affects: [audit/]
tech_stack:
  added: []
  patterns: [audit-cli, regex-patterns]
key_files:
  created:
    - audit/__init__.py
    - audit/audit_format.py
    - test_audit_format.py
    - .planning/phase-29/VERIFICATION.md
  modified: []
decisions:
  - "Follow audit_chain.py CLI style (argparse, print_results with ✓/✗)"
  - "10 checks covering card injection, cross-links, H2 structure, frontmatter, Hugo HTML, DB consistency"
  - "Tests are self-contained (no DB or file I/O)"
metrics:
  duration: "2026-07-28T04:50:17Z to 2026-07-28T05:05:00Z"
  completed: "2026-07-28"
---

# Phase 29 Plan 01: Format Verification Summary

Automated format/visual structure verification script (`audit/audit_format.py`) with 10 checks, 39 unit tests, and baseline report.

## What Was Built

### audit/audit_format.py — 10 Verification Checks

| # | Check | Description |
|---|-------|-------------|
| 1 | card_count | 카드 주입 수 검증 (max 2 per post) |
| 2 | card_placement | 카드 위치 검증 (중간=2번째H2 직후, 하단=마지막H2 이후) |
| 3 | cross_link_url | 크로스링크 URL 정확성 (D0→issue.techpawz, D1→techpawz) |
| 4 | h2_structure | H2 구조가 prompts.yaml stepSections 템플릿과 일치 |
| 5 | frontmatter | 프론트매터 필수 필드 (draft, slug, date, featureimage, description) |
| 6 | hugo_html | Hugo HTML 렌더링 (원시 마크다운, CTA 블록 직접 삽입 없음) |
| 7 | db_consistency | DB 레코드 일관성 (published_url vs status, hugo_file_path 존재) |
| 8 | card_type | 카드 타입 정확성 (D0/D1=chain-card, D2=external link) |
| 9 | external_link_pattern | 외부링크 카드 HTML 패턴 검증 |
| 10 | chain_card_shortcode | chain-card shortcode 필수 속성 검증 |

### test_audit_format.py — 39 Unit Tests

- 9 test classes covering all 10 checks
- Self-contained: no DB, no file I/O, no network
- All 39 tests pass in 0.09s

### Baseline Verification

```
8/10 checks pass on production data
2 failures from test post #488 (no frontmatter, no H2s — expected)
Hugo HTML rendering confirmed clean across all 3 sites
```

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all checks fully implemented.

## Residual Risks

- Post #488 is a test/placeholder in the DB causing 2 expected failures. If this post is cleaned up, all 10 checks will pass.
- Hugo HTML rendering checks depend on recent Hugo builds. If Hugo hasn't been run recently, HTML files may be stale.
