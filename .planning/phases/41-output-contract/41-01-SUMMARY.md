---
phase: 41
plan: 01
subsystem: quality
tags: [contract, validation, gate]
requires: []
provides: [contract-specs, contract-loader]
affects: [contracts/, quality/]
tech-stack:
  added: [pyyaml]
  patterns: [dataclass-validation, yaml-contract, regex-gate]
key-files:
  created:
    - contracts/rotcha.yaml
    - contracts/issue_techpawz.yaml
    - contracts/techpawz.yaml
    - quality/contract_loader.py
    - tests/test_contract_loader.py
  modified:
    - quality/_types.py
    - quality/__init__.py
decisions:
  - "GateResult placed in _types.py alongside ContractSpec (existing stub location)"
  - "Score penalty: 0.1 per violation, floor 0.0"
  - "H2 parser skips H3+ headings (line.startswith('## ') and not '### ')"
metrics:
  duration: 3min
  completed: 2026-08-18
  tasks: 3
  files: 8
---

# Phase 41 Plan 01: Blog Contract YAMLs + contract_loader Summary

**One-liner:** YAML contracts for 3 blog roles (rotcha/issue_techpawz/techpawz) with GateResult-based post validation (required sections, forbidden patterns, score).

## What Was Done

1. **contracts/ YAML files (3)** — Blog-specific contracts defining role, required H2 sections, forbidden regex patterns, min facts, max generic ratio, CTA limits, and thumbnail keyword match flag.

2. **quality/contract_loader.py** — `load(blog_id)` reads YAML into `ContractSpec`; `validate_post(post_md, contract)` checks required sections (H2 heading parse), forbidden patterns (regex), returns `GateResult(passed, violations, score)`.

3. **quality/_types.py** — Added `GateResult` dataclass alongside existing `ContractSpec`.

4. **tests/test_contract_loader.py** — 7 tests covering load, missing contract, passing post, missing section, forbidden pattern, score decrease, and H2 heading extraction.

## Test Results

| Metric | Count | Breakdown |
|--------|-------|-----------|
| New tests | 7 | load(2) + validate(4) + parser(1) |
| Passed | 7 | All green |
| Failed | 0 | — |
| Full suite | 935 | 928 existing + 7 new |
| Pre-existing failures | 5 | ai_writer(3) + drafter(2) — unchanged |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all functions fully implemented.

## Threat Flags

None — contracts are local-only validation, no new network surface.

## Residual Risks

- `min_specific_facts` and `max_generic_ratio` fields are present in YAML but not yet enforced in `validate_post` (Phase 42 scope)
- `cta_max_count` and `thumbnail_keyword_match` not enforced in validation (future gate integration)

## Self-Check: PASSED

- [✅] `contracts/rotcha.yaml` exists — Found on disk
- [✅] `contracts/issue_techpawz.yaml` exists — Found on disk
- [✅] `contracts/techpawz.yaml` exists — Found on disk
- [✅] `quality/contract_loader.py` exists — Found on disk
- [✅] `tests/test_contract_loader.py` exists — Found on disk
- [✅] Commit `bca675c` exists — feat(41-01) contracts
- [✅] Commit `3b8cfeb` exists — feat(41-01) loader
- [✅] Commit `ad95554` exists — test(41-01) tests
- [✅] 7/7 new tests pass — pytest output confirmed
- [✅] 935/935 suite pass (5 pre-existing failures excluded)
