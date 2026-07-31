# Phase 26 Plan 04: Update Modules to Use Constants — Summary

**Plan:** 26-04
**Type:** execute (wave 1)
**Status:** Complete
**Duration:** ~10 min
**Completed:** 2026-07-31

## One-liner

Consumed the new `constants.py` module across `chain_drafter.py`, `chain_publisher_core.py`, and `mc/leak_defense.py`, removing all duplicate hardcoded constant definitions.

## What Was Done

1. **`chain_drafter.py`** — replaced any duplicate/standalone constant definitions with module-level imports from `constants.py` (`AUTHORITY_DOMAINS`, `SKIP_DOMAINS`, `URL_PATTERN`). Grep confirmed the module previously had no duplicate domain-list definitions; the import satisfies the plan's export contract (`hasattr(chain_drafter, 'AUTHORITY_DOMAINS')` etc. verified).

2. **`chain_publisher_core.py`** — removed local `HTML_TAG_RE` and `R2_IMAGE_DOMAINS` definitions; now imports them from `constants.py` alongside `AUTHORITY_DOMAINS`, `SKIP_DOMAINS`. All call sites (`_extract_clean_body` line ~114, `_verify_before_deploy` line ~185) reference the imported names unchanged.

3. **`mc/leak_defense.py`** — the module remains the loader/owner of leak patterns (yaml-driven, `reload_config()`). Plan 01-03 added the public `LEAK_PATTERNS`/`LEAK_REGEX` exports here; `constants.py` re-exports them. No duplicate list definitions remain.

4. **Duplicate-definition sweep** — `grep '^AUTHORITY_\|^SKIP_DOMAINS\|^SKIP_PATHS\|^URL_PATTERN\|^EMAIL_PATTERN\|^HTML_TAG_RE\|^R2_IMAGE_DOMAINS'` across `chain_card_injector.py`, `chain_drafter.py`, `chain_publisher_core.py`, `mc/leak_defense.py` → **0 matches** (all definitions live in `constants.py` now).

## Files Changed

| File | Action |
|------|--------|
| `chain_drafter.py` | modified (constants import) |
| `chain_publisher_core.py` | modified (constants import + duplicate definitions removed) |
| `mc/leak_defense.py` | modified (public derived constants, from plan 01-03) |

## Verification Results

| Command | Result |
|---------|--------|
| `python -c "import chain_drafter; ..."` (T1) | OK |
| `python -c "import chain_publisher_core; ..."` (T2) | OK |
| `python -c "from mc.leak_defense import LEAK_PATTERNS; ..."` (T3) | OK |
| Plan's `from leak_defense import LEAK_PATTERNS` | ModuleNotFoundError — see deviation 1 |
| `python -m pytest -q` (full suite) | **462 passed** — zero regressions |

## Deviations from Plan

1. **[Verify-command fix] Plan's Task 3 verify used `from leak_defense import LEAK_PATTERNS`** but the module lives at `mc/leak_defense.py` (package). The correct import `from mc.leak_defense import LEAK_PATTERNS` passes. No code change needed — the plan's import path was wrong, not the module.
2. **[Shared with 01-03] `LEAK_PATTERNS` source remains yaml-driven in `mc/leak_defense.py`** (not defined in constants.py) to preserve `reload_config()` semantics; constants.py re-exports. See 01-03-SUMMARY.md deviation 1 for full rationale.

## Known Stubs

None.

## Threat Flags

None — purely additive import changes + removal of duplicate definitions; no new behavior surface.

## Residual Risk

- `chain_publisher_core.py` still contains its own frontmatter parsing helpers (`_extract_clean_body`, `_strip_frontmatter`) that are distinct operations from frontmatter *creation* — intentionally not merged into `frontmatter_utils.py` (see 01-01-SUMMARY.md deviation 1). A future plan could consolidate them.
- `pyproject.toml` package-include gap for the three new root modules (flagged in 01-01/01-02/01-03 summaries).
