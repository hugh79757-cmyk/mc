# Phase 26 Plan 02: Create url_utils.py Summary

**Plan:** 26-02
**Type:** execute (wave 1)
**Status:** Complete
**Duration:** ~20 min
**Completed:** 2026-07-31

## One-liner

Centralized URL handling (domain extraction, punycode decode, tracking-param stripping, normalization) into a new `url_utils.py`, integrated into chain_card_injector (wrapper delegation) and export-imports in chain_drafter / chain_publisher_core / image.search_providers / image.prompt_builder.

## What Was Done

1. **Created `url_utils.py`** (repo root) with:
   - `extract_domain(url)` — host extraction (port/path/query stripped, lowercase, exception-safe). Scheme-less inputs get `https://` prefixed + domain-shape validation (rejects garbage with whitespace or missing dot); schemed inputs preserve legacy netloc-equivalent behavior.
   - `decode_idn(domain)` — punycode→unicode decode (moved from `chain_card_injector._decode_idn`; `None` now returns `""` instead of crashing).
   - `strip_tracking_params(url)` — removes `utm_*` + well-known tracker keys (`fbclid`, `gclid`, `mc_cid`, `igshid`, `si`, `spm`, etc.) without re-encoding kept params (byte-for-byte preservation).
   - `normalize_url(url)` — tracking strip + fragment removal + scheme/host lowercasing (path/query case preserved).
   - `ensure_scheme(url)` — `https://` prefix helper.
   - Threat mitigations: `MAX_URL_LENGTH` guard (T-26-05 ReDoS/memory), exception-safe returns with no error-message leakage (T-26-04).

2. **Updated `chain_card_injector.py`** — `_extract_domain` / `_decode_idn` converted to backward-compat wrappers delegating to `url_utils`; module-level import `from url_utils import extract_domain, normalize_url, strip_tracking_params, decode_idn`.

3. **Updated export contracts** (module-level imports so names remain importable):
   - `chain_drafter.py` → `from url_utils import extract_domain`
   - `chain_publisher_core.py` → `from url_utils import extract_domain`
   - `image/search_providers.py` → `from url_utils import normalize_url`
   - `image/prompt_builder.py` → `from url_utils import normalize_url`

4. **Created `test_url_utils.py`** (36 tests): URL formats/edge cases/error conditions + wrapper-delegation and module-export integration tests.

## Files Changed

| File | Action |
|------|--------|
| `url_utils.py` | created |
| `test_url_utils.py` | created |
| `chain_card_injector.py` | modified (wrappers + import) |
| `chain_drafter.py` | modified (import) |
| `chain_publisher_core.py` | modified (import) |
| `image/search_providers.py` | modified (import) |
| `image/prompt_builder.py` | modified (import) |

## Verification Results

| Command | Result |
|---------|--------|
| `python -c "from url_utils import extract_domain, normalize_url, strip_tracking_params; ..."` | `Import successful` |
| `python -m pytest test_url_utils.py -v` | 36 passed |
| Plan verify script (modules import + 3 function assertions) | `All modules imported successfully` / `URL utility functions work correctly` |
| `python -m pytest -q` (full suite) | **434 passed** (398 + 36 new; zero regressions) |

## Deviations from Plan

1. **[Plan-vs-reality] No duplicate URL handling existed in chain_drafter, chain_publisher_core, image/search_providers, image/prompt_builder.** Grep confirmed zero `urlparse`/`netloc`/`utm_`/normalization code in those files. The only real URL handling was `_extract_domain` + `_decode_idn` in chain_card_injector. Resolution: centralized the real code (chain_card_injector), and satisfied the plan's export contracts (key_links) via module-level imports in the other 4 modules — additive, zero behavior change.
2. **[Verify-command fix] Plan's verify imported `UnsplashProvider, PexelsProvider` from `image.search_providers` and `PromptBuilder` from `image.prompt_builder` — these names don't exist** (providers live in `image.thumbnail`; prompt_builder exposes functions). Verify ran with correct names: `from image.thumbnail import UnsplashProvider, PexelsProvider`, `from image.prompt_builder import build_full_prompt, build_contextual_prompt`.
3. **[Behavior refinement] `extract_domain` port-stripping**: legacy `_extract_domain` returned netloc verbatim (e.g. `example.com:8080`). New version strips the port via `urlsplit().hostname`. Divergence only on port-bearing or scheme-less inputs, which never occur in production paths (card injector filters `link.startswith("http")` before extraction; search results are always schemed). Strictly more correct for the skip-domain matching use case. Documented here.
4. **`decode_idn(None)`** previously raised `AttributeError`; now returns `""` (improvement, not a regression).
5. **[Test-data fix] My initial test asserted `decode_idn("xn--vsoa.kr") == "테스트.kr"` — factually wrong** (that punycode decodes to `䘉䘉`). Corrected test to `xn--9t4b11yi5a.kr` → `테스트.kr` (verified via Python `idna` codec). Implementation was correct.

## Known Stubs

None.

## Threat Flags

None — `url_utils.py` is a pure function module; no new network/file surface.

## Residual Risk

- Same `pyproject.toml` package-include gap as 01-01 (`url_utils.py` not in setuptools include list) — no impact for working-tree execution, flagged for future plan.
