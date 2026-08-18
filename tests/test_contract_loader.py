"""Tests for quality.contract_loader."""

import pytest

from quality.contract_loader import load, validate_post, _extract_h2_headings
from quality._types import ContractSpec


# --- Task 1: load ---

def test_load_valid_contract():
    """All 3 blog contracts load successfully."""
    for blog_id in ("rotcha", "issue_techpawz", "techpawz"):
        spec = load(blog_id)
        assert spec.blog_id == blog_id
        assert len(spec.required_sections) >= 3
        assert len(spec.forbidden_patterns) >= 1


def test_load_missing_contract():
    """Non-existent blog ID raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load("nonexistent_blog")


# --- Task 2: validate_post ---

def _make_post(*sections: str) -> str:
    """Build a minimal markdown post with the given H2 section names."""
    parts = ["# Title\n"]
    for s in sections:
        parts.append(f"\n## {s}\n\nSome content about {s}.\n")
    return "\n".join(parts)


def test_validate_passing_post():
    """Post with all required sections passes."""
    spec = load("rotcha")
    post = _make_post("개요", "코스/일정", "교통/접근성", "입장료/운영시간")
    result = validate_post(post, spec)
    assert result.passed is True
    assert result.violations == []
    assert result.score == 1.0


def test_validate_missing_section():
    """Post missing a required section fails with violation."""
    spec = load("rotcha")
    post = _make_post("개요", "코스/일정")  # missing 교통/접근성, 입장료/운영시간
    result = validate_post(post, spec)
    assert result.passed is False
    assert any("교통/접근성" in v for v in result.violations)
    assert any("입장료/운영시간" in v for v in result.violations)


def test_validate_forbidden_pattern():
    """Post containing a forbidden pattern fails."""
    spec = load("rotcha")
    post = _make_post("개요", "코스/일정", "교통/접근성", "입장료/운영시간")
    post += "\n\n이곳은 최저가 보장입니다.\n"
    result = validate_post(post, spec)
    assert result.passed is False
    assert any("최저가" in v for v in result.violations)
    assert result.score < 1.0


def test_validate_score_decreases_with_violations():
    """Score drops proportionally to violation count."""
    spec = load("rotcha")
    post = _make_post("개요")
    result = validate_post(post, spec)
    # Missing 3 sections + no forbidden pattern = 3 violations, score = 0.7
    assert len(result.violations) == 3
    assert result.score == pytest.approx(0.7)


def test_extract_h2_headings():
    """H2 heading extraction works correctly."""
    md = "# H1\n## First\n### H3\n## Second\n## Third\n"
    headings = _extract_h2_headings(md)
    assert headings == ["First", "Second", "Third"]
