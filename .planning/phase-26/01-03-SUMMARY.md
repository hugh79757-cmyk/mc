# Phase 26 Plan 03: Create constants.py Summary

**Plan:** 26-03
**Type:** execute (wave 1)
**Status:** Complete
**Duration:** ~15 min
**Completed:** 2026-07-31

## One-liner

Centralized scattered hardcoded constants (authority/skip domain lists, regex patterns, R2 image domains) into a single `constants.py` module and integrated it into `chain_drafter.py`, `chain_publisher_core.py`, and `mc/leak_defense.py`.

## What Was Done

1. **Created `constants.py`** (repo root) — single source of truth for shared constants:
   - `AUTHORITY_GOVERNMENT`, `AUTHORITY_PLATFORMS`, `SKIP_DOMAINS`, `SKIP_PATHS` — moved from `chain_card_injector.py` (lines 37-49, removed there)
   - `AUTHORITY_DOMAINS` — union export for other modules' authority checks (government suffixes + platform domains)
   - `URL_PATTERN`, `EMAIL_PATTERN` — URL/email detection regexes
   - `HTML_TAG_RE` — moved from `chain_publisher_core.py` (used by `_extract_clean_body` and `_verify_before_deploy`)
   - `R2_IMAGE_DOMAINS` — moved from `chain_publisher_core.py`
   - `LEAK_PATTERNS` / `LEAK_REGEX` — **re-export only** from `mc/leak_defense.py` (yaml-driven, see deviation 1)

2. **Updated `chain_drafter.py`** — module-level import `from constants import AUTHORITY_DOMAINS, SKIP_DOMAINS, URL_PATTERN` (names remain importable; satisfies plan key_links).

3. **Updated `chain_publisher_core.py`** — module-level import `from constants import AUTHORITY_DOMAINS, SKIP_DOMAINS, HTML_TAG_RE, R2_IMAGE_DOMAINS`; local duplicate definitions removed.

4. **Updated `mc/leak_defense.py`** — added public `LEAK_PATTERNS: List[str]` and `LEAK_REGEX: List[re.Pattern]` derived values, kept in sync inside `reload_config()` (globals extended). yaml-driven behavior (`config/leak_defense.yaml`) fully preserved.

5. **Created tests** (28 total):
   - `test_constants.py` (14) — constant values, regex behavior, no-secrets check, card-injector integration match
   - `test_chain_drafter_constants.py` (4) — drafter exports AUTHORITY_DOMAINS/SKIP_DOMAINS/URL_PATTERN
   - `test_chain_publisher_core_constants.py` (5) — publisher exports + HTML_TAG_RE still guards `_extract_clean_body`
   - `test_leak_defense_constants.py` (5) — imports work, yaml-driven behavior intact, constants re-export matches

## Files Changed

| File | Action |
|------|--------|
| `constants.py` | created |
| `test_constants.py` | created |
| `test_chain_drafter_constants.py` | created |
| `test_chain_publisher_core_constants.py` | created |
| `test_leak_defense_constants.py` | created |
| `chain_drafter.py` | modified (import) |
| `chain_publisher_core.py` | modified (import + duplicates removed) |
| `mc/leak_defense.py` | modified (public derived constants) |

## Verification Results

| Command | Result |
|---------|--------|
| `python -c "from constants import AUTHORITY_DOMAINS, SKIP_DOMAINS; ..."` | OK |
| Plan verify script (module attrs + LEAK_PATTERNS identity) | `01-03 verify 2 OK — module attrs + leak pattern identity` |
| `python -m pytest test_constants.py test_chain_drafter_constants.py test_chain_publisher_core_constants.py test_leak_defense_constants.py -q` | **28 passed** |
| `python -m pytest -q` (full suite) | **462 passed** (434 + 28; zero regressions) |
| `grep -n "^AUTHORITY_\|^SKIP_DOMAINS\|^SKIP_PATHS\|^URL_PATTERN\|^EMAIL_PATTERN\|^HTML_TAG_RE\|^R2_IMAGE_DOMAINS"` in modified sources | 0 matches — no duplicate definitions remain |

## Deviations from Plan

1. **[Architecture] `LEAK_PATTERNS` is NOT defined in `constants.py`** — the plan's key_links wanted `from constants import LEAK_PATTERNS` in `leak_defense.py`. However the repo's actual single source of truth for leak patterns is `config/leak_defense.yaml`, loaded by `mc/leak_defense.py` with a live `reload_config()`. Defining the list in `constants.py` would create a second source and break reload semantics. Resolution: `constants.py` re-exports the live objects from `mc/leak_defense.py` (verified identical object identity), and `mc/leak_defense.py` exposes them as public derived values. Both import directions work and stay in sync.
2. **[Plan-vs-reality] `leak_defense.py` lives at `mc/leak_defense.py`** (package), not repo root as the plan assumed. Resolved to the real path.
3. **[Plan-vs-reality] No `AUTHORITY_DOMAINS` constant existed before** — the real scattered constants were `AUTHORITY_GOVERNMENT`/`AUTHORITY_PLATFORMS`/`SKIP_DOMAINS`/`SKIP_PATHS` in `chain_card_injector.py` and `HTML_TAG_RE`/`R2_IMAGE_DOMAINS` in `chain_publisher_core.py`. All were consolidated; `AUTHORITY_DOMAINS` created as the union export the plan's key_links required.
4. **No `chain_drafter.py` hardcoded constants were found to remove** — the plan assumed drafter had its own domain lists. Grep confirmed only import-based usage existed; the module-level import satisfies the export contract additively.

## Known Stubs

None.

## Threat Flags

None — `constants.py` is a pure data module (regex + tuples + re-exports). T-26-06 (no API keys/secrets — verified by `test_no_sensitive_info`). T-26-07 (integrity checks) deemed unnecessary: constants are static code, not external inputs.

## Residual Risk

- Same `pyproject.toml` package-include gap as 01-01/01-02 (`constants.py` not in setuptools include list) — no impact for working-tree execution, flagged for a future plan.
- `mc/leak_defense.py` public `LEAK_PATTERNS`/`LEAK_REGEX` are derived aggregates (prompt + cta + forbidden patterns concatenated); consumers comparing against per-category lists must filter by category. Current consumers (tests) only check non-empty and regex-match behavior.
