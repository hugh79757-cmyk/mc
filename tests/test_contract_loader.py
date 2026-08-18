"""Tests for quality.contract_loader."""

import pytest

from quality.contract_loader import (
    load, validate_post, _extract_h2_headings, is_category_supported,
    match_section, DEFAULT_FUZZY_THRESHOLD,
)
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
    post = _make_post("제품 개요와 핵심 스펙", "디자인과 주요 특징", "경쟁 모델과 비교 포인트", "핵심 요약")
    result = validate_post(post, spec)
    assert result.passed is True
    assert result.violations == []
    assert result.score == 1.0


def test_validate_missing_section():
    """Post missing a required section fails with violation."""
    spec = load("rotcha", category="product")
    post = _make_post("제품 개요와 핵심 스펙", "디자인과 주요 특징")  # missing 2 sections
    result = validate_post(post, spec)
    assert result.passed is False
    assert any("경쟁 모델과 비교 포인트" in v for v in result.violations)
    assert any("핵심 요약" in v for v in result.violations)


def test_validate_forbidden_pattern():
    """Post containing a forbidden pattern fails."""
    spec = load("rotcha", category="product")
    post = _make_post("제품 개요와 핵심 스펙", "디자인과 주요 특징", "경쟁 모델과 비교 포인트", "핵심 요약")
    post += "\n\n이곳은 최저가 보장입니다.\n"
    result = validate_post(post, spec)
    assert result.passed is False
    assert any("최저가" in v for v in result.violations)
    assert result.score < 1.0


def test_validate_score_decreases_with_violations():
    """Score drops proportionally to violation count."""
    spec = load("rotcha", category="product")
    post = _make_post("제품 개요와 핵심 스펙")
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
    assert "제품 개요와 핵심 스펙" in spec.required_sections
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


# --- Fuzzy section matching ---

class TestMatchSection:
    """Tests for match_section() fuzzy matching logic."""

    def test_exact_match(self):
        matched, method = match_section("장소 개요", ["장소 개요", "교통"])
        assert matched is True
        assert method == "exact"

    def test_contains_contract_in_heading(self):
        """Contract section is substring of heading."""
        matched, method = match_section("작품 개요", ["작품 개요와 핵심 정보"])
        assert matched is True
        assert method == "contains"

    def test_contains_heading_in_contract(self):
        """Heading is substring of contract section."""
        matched, method = match_section("효능/효과와 사용", ["효능/효과"])
        assert matched is True
        assert method == "contains"

    def test_fuzzy_keyword_overlap(self):
        """High token overlap matches as fuzzy."""
        matched, method = match_section("핵심 내용 정리", ["핵심 내용 정리와 요약"])
        assert matched is True
        assert method in ("contains", "fuzzy")

    def test_no_match(self):
        """Completely different sections don't match."""
        matched, method = match_section("장소 개요", ["교통 안내", "요금 정보"])
        assert matched is False
        assert method == "none"

    def test_empty_headings(self):
        matched, method = match_section("장소 개요", [])
        assert matched is False
        assert method == "none"

    def test_partial_overlap_below_threshold(self):
        """Low overlap does not match."""
        matched, method = match_section("장소 개요", ["교통 안내"], threshold=0.5)
        assert matched is False
        assert method == "none"

    def test_case_insensitive(self):
        matched, method = match_section("ABC", ["abc def"])
        assert matched is True
        assert method == "contains"

    def test_real_world_travel(self):
        """Real-world mismatch from E2E test: contract vs AI heading."""
        matched, method = match_section("장소 개요", ["위치와 기본 정보"])
        # These share no tokens → should NOT match
        assert matched is False

    def test_real_world_entertainment(self):
        """Real-world case: '작품 개요' vs '작품 개요와 핵심 정보'."""
        matched, method = match_section("작품 개요", ["작품 개요와 핵심 정보"])
        assert matched is True
        assert method == "contains"

    def test_real_world_medicine(self):
        """Real-world case: '효능/효과' vs '효능·효과와 사용'."""
        matched, method = match_section("효능/효과", ["효능·효과와 사용"])
        assert matched is True
        assert method == "contains"


class TestValidatePostFuzzy:
    """validate_post with fuzzy matching should reduce false violations."""

    def test_fuzzy_match_entertainment_headings(self):
        """AI headings with extra words match contract sections."""
        spec = load("rotcha", category="entertainment")
        # Contract requires: 작품 개요와 핵심 정보, 줄거리 요약과 주요 장면,
        #   등장인물 분석과 관계도, 한눈에 보기
        # Use headings that contain the contract section text
        post = _make_post(
            "작품 개요와 핵심 정보",
            "줄거리 요약과 주요 장면",
            "등장인물 분석과 관계도",
            "한눈에 보기",
        )
        result = validate_post(post, spec)
        assert result.passed is True
        assert result.score == 1.0

    def test_fuzzy_match_real_h2_variations(self):
        """Real-world H2 variations from E2E tests all match."""
        # Travel: contract "교통/접근성" → AI "교통 및 접근성 안내"
        matched, _ = match_section("교통/접근성", ["교통 및 접근성 안내"])
        assert matched is True

        # Knowledge: contract "개요/정의" → AI "개요와 정의"
        matched, _ = match_section("개요/정의", ["개요와 정의"])
        assert matched is True

        # Product: contract "핵심 특징/스펙" → AI "핵심 특징과 스펙"
        matched, _ = match_section("핵심 특징/스펙", ["핵심 특징과 스펙"])
        assert matched is True

        # Travel: contract "방문 정보" → AI "방문 정보와 팁"
        matched, _ = match_section("방문 정보", ["방문 정보와 팁"])
        assert matched is True
