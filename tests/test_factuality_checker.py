"""Tests for quality/factuality_checker.py."""

import re

import pytest

from quality.factuality_checker import (
    Claim,
    FactualityResult,
    check_forbidden,
    extract_claims,
    validate_factuality,
)
from quality._types import ContractSpec


# ---------------------------------------------------------------------------
# extract_claims
# ---------------------------------------------------------------------------

class TestExtractClaims:
    def test_extract_percentage_claim(self):
        """Percentage pattern '73%' is detected."""
        claims = extract_claims("방문객 만족도 73%입니다.")
        assert len(claims) >= 1
        assert any("73%" in c.sentence for c in claims)
        assert any(c.claim_type == "number" for c in claims)

    def test_extract_review_claim(self):
        """Review pattern '리뷰 데이터를 분석하면' is detected."""
        claims = extract_claims("리뷰 데이터를 분석하면 높은 만족도가 나옵니다.")
        assert len(claims) >= 1
        assert any(c.claim_type == "review" for c in claims)

    def test_extract_statistics_claim(self):
        """Statistics pattern '설문 결과' is detected."""
        claims = extract_claims("설문 결과 85%가 긍정적이었습니다.")
        assert len(claims) >= 1
        assert any(c.claim_type == "statistics" for c in claims)

    def test_extract_people_count_claim(self):
        """People count pattern '1200명' is detected."""
        claims = extract_claims("월간 방문자는 1200명입니다.")
        assert len(claims) >= 1
        assert any("1200명" in c.sentence for c in claims)

    def test_extract_price_claim(self):
        """Price pattern '59만원' is detected."""
        claims = extract_claims("가격은 59만원부터 시작합니다.")
        assert len(claims) >= 1
        assert any("59만원" in c.sentence for c in claims)

    def test_extract_satisfaction_score_claim(self):
        """Satisfaction score pattern '만족도 85' is detected."""
        claims = extract_claims("소비자 만족도 85점입니다.")
        assert len(claims) >= 1
        assert any("만족도" in c.sentence for c in claims)

    def test_extract_no_claims(self):
        """Text with no claims returns empty list."""
        claims = extract_claims("안녕하세요. 오늘 날씨가 좋습니다.")
        assert claims == []


# ---------------------------------------------------------------------------
# Source tag detection
# ---------------------------------------------------------------------------

class TestSourceTag:
    def test_sourced_claim_passes(self):
        """Sentence with [출처:] tag is marked has_source_tag=True."""
        claims = extract_claims(
            "방문객 만족도 73%입니다. [출처: 공식홈페이지]"
        )
        assert len(claims) >= 1
        assert any(c.has_source_tag for c in claims)

    def test_unsourced_claim(self):
        """Sentence without [출처:] tag is marked has_source_tag=False."""
        claims = extract_claims("설문 결과 85%가 긍정적이었습니다.")
        assert len(claims) >= 1
        assert all(not c.has_source_tag for c in claims)

    def test_source_tag_in_middle_of_sentence(self):
        """[출처:] tag anywhere in sentence counts."""
        claims = extract_claims(
            "리뷰 데이터를 분석하면 [출처: 네이버블로그] 높은 점수가 나옵니다."
        )
        assert len(claims) >= 1
        assert any(c.has_source_tag for c in claims)


# ---------------------------------------------------------------------------
# check_forbidden
# ---------------------------------------------------------------------------

class TestCheckForbidden:
    def test_forbidden_pattern_hit(self):
        """Forbidden pattern '최저가' matches and returns the sentence."""
        hits = check_forbidden(
            "이곳은 최저가를 보장합니다.",
            [r"최저가", r"100%\s*보장"],
        )
        assert len(hits) == 1
        assert "최저가" in hits[0]

    def test_forbidden_multiple_patterns(self):
        """Multiple forbidden patterns can match different sentences."""
        body = "최저가 보장. 100% 보장합니다."
        hits = check_forbidden(body, [r"최저가", r"100%\s*보장"])
        assert len(hits) == 2

    def test_forbidden_no_match(self):
        """No matches returns empty list."""
        hits = check_forbidden(
            "좋은 제품입니다.",
            [r"최저가", r"100%\s*보장"],
        )
        assert hits == []


# ---------------------------------------------------------------------------
# validate_factuality
# ---------------------------------------------------------------------------

class TestValidateFactuality:
    def test_score_below_threshold(self):
        """High unsourced ratio → passed=False (score < 0.7)."""
        # 4 unsourced, 0 sourced → score = 0.0
        body = (
            "73%의 방문객이 만족합니다. "
            "리뷰 데이터를 분석하면 높은 점수입니다. "
            "설문 결과 85%가 긍정적. "
            "1200명의 사용자가 이용했습니다."
        )
        contract = ContractSpec(
            blog_id="test",
            forbidden_patterns=[],
        )
        result = validate_factuality(body, contract)
        assert result.score == 0.0
        assert result.passed is False
        assert len(result.unsourced_claims) == 4

    def test_clean_post_passes(self):
        """No claims at all → score=1.0, passed=True."""
        body = "오늘 날씨가 좋습니다. 산책하기 좋은 날이에요."
        contract = ContractSpec(blog_id="test", forbidden_patterns=[])
        result = validate_factuality(body, contract)
        assert result.score == 1.0
        assert result.passed is True
        assert result.unsourced_claims == []

    def test_all_sourced_passes(self):
        """All claims have [출처:] → score=1.0, passed=True."""
        body = (
            "방문객 만족도 73%입니다. [출처: 공식사이트] "
            "리뷰 데이터를 분석하면 높은 점수입니다. [출처: 네이버]"
        )
        contract = ContractSpec(blog_id="test", forbidden_patterns=[])
        result = validate_factuality(body, contract)
        assert result.score == 1.0
        assert result.passed is True

    def test_forbidden_forces_fail(self):
        """Even with good score, forbidden pattern → passed=False."""
        body = (
            "방문객 만족도 73%입니다. [출처: 공식사이트] "
            "이곳은 최저가를 보장합니다."
        )
        contract = ContractSpec(
            blog_id="test",
            forbidden_patterns=[r"최저가"],
        )
        result = validate_factuality(body, contract)
        assert result.passed is False
        assert len(result.forbidden_hits) == 1

    def test_mixed_sourced_unsourced(self):
        """Mix of sourced/unsourced → partial score."""
        # Claim 1 has [출처:] on next sentence → sourced.
        # Claim 2 has no [출처:] and no following sentence → unsourced.
        body = (
            "방문객 만족도 73%입니다. [출처: 공식사이트] 다른 내용입니다. "
            "설문 결과 85%가 긍정적."
        )
        contract = ContractSpec(blog_id="test", forbidden_patterns=[])
        result = validate_factuality(body, contract)
        # 1 sourced, 1 unsourced → score = 0.5 → below 0.7
        assert result.score == pytest.approx(0.5)
        assert result.passed is False

    def test_no_claims_passes(self):
        """Empty body → no claims → score=1.0, passed=True."""
        contract = ContractSpec(blog_id="test", forbidden_patterns=[])
        result = validate_factuality("", contract)
        assert result.score == 1.0
        assert result.passed is True


# ---------------------------------------------------------------------------
# Real-world fixture: techpawz-style unsourced stats
# ---------------------------------------------------------------------------

class TestRealFixture:
    def test_real_techpawz_fixture(self):
        """Simulated techpawz post with unsourced statistics → flagging."""
        body = (
            "이 전동킥보드의 최고 속도는 25km/h입니다. "
            "배터리 용량은 10.5Ah이며, 완충 시 40km까지 주행 가능합니다. "
            "리뷰 데이터를 분석하면 사용자 만족도 78%입니다. "
            "가격은 89만원으로, 동급 대비 경쟁력이 있습니다. "
            "설문 결과 90%의 사용자가 재구매 의사를 밝혔습니다."
        )
        contract = ContractSpec(
            blog_id="techpawz",
            forbidden_patterns=[r"최저가\s*보장"],
        )
        result = validate_factuality(body, contract)
        # 3 pattern-matched claims (리뷰, 만원, 설문) are all unsourced → score=0.0
        # "25km/h" and "10.5Ah" don't match number patterns (no %, 명, 만원, 점, 만족도 N)
        assert result.score == 0.0
        assert result.passed is False
        assert len(result.unsourced_claims) == 3
        assert result.forbidden_hits == []

    def test_real_techpawz_with_forbidden(self):
        """Techpawz-style post with forbidden pattern → double fail."""
        body = (
            "73%의 사용자가 만족합니다. "
            "이곳은 최저가를 보장합니다."
        )
        contract = ContractSpec(
            blog_id="techpawz",
            forbidden_patterns=[r"최저가"],
        )
        result = validate_factuality(body, contract)
        assert result.passed is False
        assert result.score == pytest.approx(0.0)
        assert len(result.forbidden_hits) == 1
