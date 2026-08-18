"""Tests for quality scorer module (Phase 47-01)."""

from quality._types import DedupResult, GateResult, RoleResult
from quality.factuality_checker import FactualityResult
from quality.html_render_checker import HtmlCheckResult
from quality.scorer import QualityScore, calculate_score
from quality.title_body_checker import TitleBodyResult


def _perfect_results():
    """Return all-perfect check results."""
    return (
        GateResult(passed=True, violations=[], score=1.0),
        TitleBodyResult(score=1.0, met_promises=["A"], unmet_promises=[]),
        FactualityResult(score=1.0, unsourced_claims=[], forbidden_hits=[], passed=True),
        DedupResult(passed=True, pair_scores={}, violations=[]),
        RoleResult(passed=True, missing_sections=[], extra_sections=[]),
        HtmlCheckResult(passed=True, violations=[]),
    )


def test_perfect_score():
    """All perfect results → total should be 10.0."""
    score = calculate_score(*_perfect_results())
    assert score.total == 10.0
    assert score.contract_score == 10.0
    assert score.factuality_score == 10.0
    assert score.role_score == 10.0
    assert score.visual_score == 10.0


def test_zero_factuality():
    """Factuality 0 → total should be <= 7.5."""
    contract, title_body, _, dedup, role, html = _perfect_results()
    bad_factuality = FactualityResult(score=0.0, unsourced_claims=["x"], passed=False)
    score = calculate_score(contract, title_body, bad_factuality, dedup, role, html)
    assert score.total <= 7.5
    assert score.factuality_score == 0.0


def test_weight_sum():
    """Weight sum should equal 1.0."""
    score = calculate_score(*_perfect_results())
    weights = score.breakdown["weights"]
    total_weight = sum(weights.values())
    assert abs(total_weight - 1.0) < 1e-9


def test_all_zero_score():
    """All worst results → total should be 0.0 or very low."""
    worst = (
        GateResult(passed=False, violations=["v1"], score=0.0),
        TitleBodyResult(score=0.0, met_promises=[], unmet_promises=["p1"]),
        FactualityResult(score=0.0, unsourced_claims=["c1"], passed=False),
        DedupResult(passed=False, violations=["dup"]),
        RoleResult(passed=False, missing_sections=["s1"]),
        HtmlCheckResult(passed=False, violations=["h1"]),
    )
    score = calculate_score(*worst)
    assert score.total < 5.0
    assert len(score.violations) > 0


def test_dedup_penalty():
    """Failed dedup reduces role score."""
    contract, title_body, factuality, _, role, html = _perfect_results()
    bad_dedup = DedupResult(passed=False, violations=["high similarity"])
    score_good = calculate_score(contract, title_body, factuality, DedupResult(passed=True), role, html)
    score_bad = calculate_score(contract, title_body, factuality, bad_dedup, role, html)
    assert score_bad.role_score < score_good.role_score


def test_html_violation_penalty():
    """HTML violations reduce visual score."""
    contract, title_body, factuality, dedup, role, _ = _perfect_results()
    good_html = HtmlCheckResult(passed=True, violations=[])
    bad_html = HtmlCheckResult(passed=False, violations=["dup_title", "dup_cta"])
    score_good = calculate_score(contract, title_body, factuality, dedup, role, good_html)
    score_bad = calculate_score(contract, title_body, factuality, dedup, role, bad_html)
    assert score_bad.visual_score < score_good.visual_score


def test_breakdown_structure():
    """Breakdown dict has expected keys."""
    score = calculate_score(*_perfect_results())
    assert "contract" in score.breakdown
    assert "factuality" in score.breakdown
    assert "role" in score.breakdown
    assert "visual" in score.breakdown
    assert "weights" in score.breakdown
