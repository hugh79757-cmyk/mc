# Phase 47 Plan 01: quality-scorer Summary

**Phase:** 47-quality-scorer  
**Plan:** 01  
**Subsystem:** quality  
**Tags:** quality-gate, scorer, integration  
**Duration:** 425s  
**Completed:** 2026-08-18  

## One-Liner

Weighted quality scorer (contract 0.40, factuality 0.25, role 0.20, visual 0.15) with integrated gate that blocks publish on score <7.0, warns on 7.0–8.9, and auto-publishes on 9.0+.

## Dependency Graph

**Requires:** 41-01 (contract_loader), 42-01 (title_body_checker), 43-01 (pre_researcher), 44-01 (factuality_checker), 45-01 (cross_blog_checker), 46-01 (html_render_checker)  
**Provides:** quality.scorer, quality.gate  
**Affects:** chain_publisher.py, cli/mc.py

## Tech Stack

**Added:** quality/scorer.py, quality/gate.py  
**Patterns:** dataclass aggregation, weighted scoring, gate verdict pattern

## Key Files

| File | Action | Purpose |
|------|--------|---------|
| quality/scorer.py | Created | QualityScore dataclass + calculate_score() |
| quality/gate.py | Created | GateVerdict + run_all_checks() orchestration |
| chain_publisher.py | Modified | Quality gate inserted before publish step |
| cli/mc.py | Modified | --force flag added |
| tests/test_scorer.py | Created | 7 scorer unit tests |
| tests/test_gate_integration.py | Created | 6 gate integration tests |

## Decisions Made

1. **Contract file name mapping:** `issue.techpawz` → `issue_techpawz.yaml` (underscore in filename, dot in blog_id)
2. **HTML check deferred at pre-publish:** HTML not rendered yet before Hugo build; gate uses empty HTML string (no HTML violations at pre-publish stage)
3. **Gate placement in chain_publisher.py:** Added between image generation and publish step in `run_chain()`, not in `cli/mc.py` (which delegates to `run_chain()`)

## Verification Results

| Task | Status | Evidence |
|------|--------|----------|
| scorer.py | [검증됨] | `python -c "from quality.scorer import QualityScore"` → fields verified |
| gate.py | [검증됨] | `python -c "from quality.gate import run_all_checks"` → importable |
| CLI integration | [검증됨] | `--force` flag visible in `mc run --help` |
| Scorer tests (7) | [검증됨] | `pytest tests/test_scorer.py -v` → 7/7 passed |
| Gate tests (6) | [검증됨] | `pytest tests/test_gate_integration.py -v` → 6/6 passed |
| Full regression | [부분검증] | 1016/1021 passed (5 pre-existing failures unrelated to Phase 47) |

## Metrics

- **Tests added:** 13 (7 scorer + 6 gate)
- **Tests passed:** 13/13
- **Files created:** 4 (scorer.py, gate.py, test_scorer.py, test_gate_integration.py)
- **Files modified:** 2 (chain_publisher.py, cli/mc.py)

## Deviations from Plan

### Plan Deviation: Gate placement

- **Plan said:** "Add to cli/mc.py publish command, right before the actual publish logic"
- **Actual:** Added to `chain_publisher.py` `run_chain()` between image generation and publish step
- **Reason:** `run_chain()` handles the full pipeline (derive→draft→image→publish). The quality gate must run after images but before publish, which is inside `run_chain()`. Adding it to `cli/mc.py` would require posts to exist before `run_chain()` is called, which they don't in the `mc <keyword>` flow.
- **Impact:** None — the gate still runs before publish. `--force` flag and `MC_SKIP_QUALITY_GATE` env var work as specified.

## Known Stubs

None — all implementations are complete and tested.

## Threat Flags

None — no new network endpoints, auth paths, or trust boundary changes.

## Residual Risks

1. **HTML check deferred:** At pre-publish stage, HTML is not rendered yet. The HTML duplicate check (title==H1, CTA count, paragraph duplication) runs only in post-build smoke tests. A future enhancement could render markdown→HTML for pre-publish checks.
2. **Contract missing for new blogs:** If a new blog is added without a corresponding contract YAML, the gate will skip that blog's checks. The gate logs a violation but doesn't fail.

## Self-Check

- [✅] quality/scorer.py exists
- [✅] quality/gate.py exists
- [✅] tests/test_scorer.py exists
- [✅] tests/test_gate_integration.py exists
- [✅] 13 tests pass (pytest verified)
- [✅] No regression in existing 1008 tests (5 pre-existing failures unchanged)
- [✅] git commits: 114306c, 93a54bf, 6204b0b, 87c1ec1
