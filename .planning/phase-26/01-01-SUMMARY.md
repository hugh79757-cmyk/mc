# Phase 26 Plan 01: Create frontmatter_utils.py Summary

**Plan:** 26-01
**Type:** execute (wave 1)
**Status:** Complete
**Duration:** ~15 min
**Completed:** 2026-07-31

## One-liner

Centralized duplicate frontmatter handling (`_ensure_frontmatter`, `_ensure_frontmatter_closer`, `_build_frontmatter`, `_extract_description`) into a single `frontmatter_utils.py` module with input validation, keeping `chain_drafter.py` wrappers for backward compatibility.

## What Was Done

1. **Created `frontmatter_utils.py`** (repo root) — single source of truth for frontmatter handling:
   - `ensure_frontmatter(draft_md, post)` — unified frontmatter ensure logic (from `chain_drafter._ensure_frontmatter`)
   - `ensure_frontmatter_closer(draft_md)` — closer repair (from `chain_drafter._ensure_frontmatter_closer`)
   - `build_frontmatter(post, body)` — Hugo FM assembly (from `chain_drafter._build_frontmatter`)
   - `extract_description(body, max_len=150)` — description extraction (from `chain_drafter._extract_description`)
   - Threat-model mitigations: `MAX_FRONTMATTER_INPUT_CHARS` (T-26-02 DoS size cap, 1MB → ValueError) and post-must-be-dict validation (T-26-01 injection guard → ValueError).

2. **Updated `chain_drafter.py`**:
   - `_extract_description`, `_build_frontmatter`, `_ensure_frontmatter_closer`, `_ensure_frontmatter` converted to thin backward-compat wrappers delegating to `frontmatter_utils` (comment-marked).
   - Internal call sites (`draft_chain` FM assembly, `_ensure_featureimage`) now call `frontmatter_utils` directly.

3. **Updated `chain_publisher_core.py`**:
   - Added `from frontmatter_utils import ensure_frontmatter` (module-level export contract). No duplicate frontmatter functions existed in this file — nothing to remove.

4. **Created `test_frontmatter_utils.py`** (20 tests): behavior parity suite mirroring existing `test_chain_drafter.py` cases for all 4 functions, plus T-26-01/T-26-02 validation tests, plus wrapper-delegation tests proving `chain_drafter._ensure_frontmatter` etc. return identical results to `frontmatter_utils`.

## Files Changed

| File | Action |
|------|--------|
| `frontmatter_utils.py` | created |
| `test_frontmatter_utils.py` | created |
| `chain_drafter.py` | modified (wrappers + call-site switch) |
| `chain_publisher_core.py` | modified (import added) |

## Verification Results

| Command | Result |
|---------|--------|
| `python -c "from frontmatter_utils import ensure_frontmatter; print('Import successful')"` | `Import successful` |
| `python -c "import chain_drafter; ..."` | OK |
| `python -c "import chain_publisher_core; ..."` | OK |
| `python -m pytest test_frontmatter_utils.py -q` | 20 passed |
| `python -m pytest -q` (full suite) | **398 passed** (baseline 378 + 20 new; zero regressions) |

## Deviations from Plan

1. **[Accuracy fix] `chain_publisher_core.py` had no `_ensure_frontmatter`/`_ensure_frontmatter_closer` functions** to replace. The plan assumed duplicate definitions existed there. Resolution: added the required `from frontmatter_utils import ensure_frontmatter` import to satisfy the plan's key_links/exports contract. Existing publisher frontmatter parsing (`_extract_clean_body`, `_strip_frontmatter`) left untouched — different operations, not duplicates.
2. **[Compatibility] `_ensure_frontmatter`/`_ensure_frontmatter_closer`/`_build_frontmatter`/`_extract_description` retained as thin wrappers** instead of being deleted, because `test_chain_drafter.py` (lines ~419-447, 606-724, 735-872, 886-920) imports them directly from `chain_drafter`. Repo rule "never break passing tests" takes precedence over the plan's "remove duplicate function definitions". Each wrapper carries a `backward-compat wrapper` comment.
3. **Added validation not in the plan's task list** (T-26-01/T-26-02 threat mitigations): dict-type check and 1MB input cap. Both raise `ValueError` only on inputs that previously crashed with `AttributeError` or are pathologically large — no behavior change for valid inputs.

## Known Stubs

None — all functions are fully wired to existing behavior.

## Threat Flags

None — `frontmatter_utils.py` is a pure function module (no network, no file access). Validations added per threat register.

## Residual Risk

- `pyproject.toml` package `include` list (`chain_*, image*, cli*, shared*`) does not cover `frontmatter_utils.py` — a future `pip install .` would miss it. Repo runs scripts from working tree, so no current impact. Flagged for a future plan.
