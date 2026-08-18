"""Tests for quality.contract_loader."""

import pytest

from quality.contract_loader import load, validate_post, _extract_h2_headings, is_category_supported
from quality._types import ContractSpec


# --- Task 1: load ---

def test_load_valid_contract():
    """All 3 blog contracts load successfully with a supported category."""
    for blog_id in ("rotcha", "issue_techpawz", "techpawz"):
        spec = load(blog_id, category="product")
        assert spec.blog_id == blog_id
        assert len(spec.required_sections) >= 3
        assert len(spec.forbidden_patterns) >= 1


def test_load_missing_contract():
    """Non-existent blog ID raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load("nonexistent_blog", category="product")


# --- Task 2: validate_post ---

def _make_post(*sections: str) -> str:
    """Build a minimal markdown post with the given H2 section names."""
    parts = ["# Title\n"]
    for s in sections:
        parts.append(f"\n## {s}\n\nSome content about {s}.\n")
    return "\n".join(parts)


def test_validate_passing_post():
    """Post with all required sections passes."""
    spec = load("rotcha", category="product")
    post = _make_post("제품 개요", "핵심 특징/스펙", "사용법/활용법", "구매 참고사항")
    result = validate_post(post, spec)
    assert result.passed is True
    assert result.violations == []
    assert result.score == 1.0


def test_validate_missing_section():
    """Post missing a required section fails with violation."""
    spec = load("rotcha", category="product")
    post = _make_post("제품 개요", "핵심 특징/스펙")  # missing 사용법/활용법, 구매 참고사항
    result = validate_post(post, spec)
    assert result.passed is False
    assert any("사용법/활용법" in v for v in result.violations)
    assert any("구매 참고사항" in v for v in result.violations)


def test_validate_forbidden_pattern():
    """Post containing a forbidden pattern fails."""
    spec = load("rotcha", category="product")
    post = _make_post("제품 개요", "핵심 특징/스펙", "사용법/활용법", "구매 참고사항")
    post += "\n\n이곳은 최저가 보장입니다.\n"
    result = validate_post(post, spec)
    assert result.passed is False
    assert any("최저가" in v for v in result.violations)
    assert result.score < 1.0


def test_validate_score_decreases_with_violations():
    """Score drops proportionally to violation count."""
    spec = load("rotcha", category="product")
    post = _make_post("제품 개요")
    result = validate_post(post, spec)
    # Missing 3 sections + no forbidden pattern = 3 violations, score = 0.7
    assert len(result.violations) == 3
    assert result.score == pytest.approx(0.7)


def test_extract_h2_headings():
    """H2 heading extraction works correctly."""
    md = "# H1\n## First\n### H3\n## Second\n## Third\n"
    headings = _extract_h2_headings(md)
    assert headings == ["First", "Second", "Third"]


# --- Task 3: category branching ---

def test_load_contract_with_category():
    """load('rotcha', 'product') returns product-specific sections."""
    spec = load("rotcha", category="product")
    assert "제품 개요" in spec.required_sections
    assert "골프장 개요" not in spec.required_sections


def test_load_contract_default_reject():
    """load('rotcha') with no category returns empty required_sections."""
    spec = load("rotcha")
    assert spec.required_sections == []


def test_load_contract_unknown_category():
    """load('rotcha', 'xyz') with unknown category returns empty required_sections."""
    spec = load("rotcha", category="xyz")
    assert spec.required_sections == []


def test_is_category_supported():
    """Supported categories return True, unsupported return False."""
    assert is_category_supported("product") is True
    assert is_category_supported("travel") is True
    assert is_category_supported("entertainment") is True
    assert is_category_supported("knowledge") is True
    assert is_category_supported("food") is False
    assert is_category_supported(None) is False


def test_validate_unsupported_category_empty_sections():
    """Post with unsupported category has empty required_sections → no section violations."""
    spec = load("rotcha", category="food")  # food not in YAML → empty sections
    post = _make_post("개요")
    result = validate_post(post, spec)
    # No required sections to check, so only forbidden patterns matter
    assert result.passed is True
    assert result.score == 1.0


def test_all_blog_contracts_have_9_categories():
    """Each blog contract YAML has exactly the 9 supported categories."""
    expected = {"product", "customer_service", "gov_finance",
                "shopping_brand", "golf_course", "medicine",
                "travel", "entertainment", "knowledge"}
    for blog_id in ("rotcha", "issue_techpawz", "techpawz"):
        spec = load(blog_id, category="product")  # load any category to get the YAML
        # Re-load raw YAML to check dict keys
        import yaml
        from pathlib import Path
        path = Path(__file__).resolve().parent.parent / "contracts" / f"{blog_id}.yaml"
        data = yaml.safe_load(path.read_text())
        assert set(data["required_sections"].keys()) == expected, \
            f"{blog_id} contract categories mismatch"
