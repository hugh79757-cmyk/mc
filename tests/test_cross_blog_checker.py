"""Tests for cross_blog_checker module."""

import pytest

from quality._types import ContractSpec
from quality.contract_loader import load
from quality.cross_blog_checker import (
    calc_similarity,
    check_cross_blog_dedup,
    check_role_elements,
    split_sentences,
)


class TestSplitSentences:
    """Tests for split_sentences function."""

    def test_simple_sentences(self):
        text = "첫번째 문장입니다. 두번째 문장입니다."
        result = split_sentences(text)
        assert len(result) >= 2

    def test_markdown_headers_stripped(self):
        text = "## 개요\n이것은 소개입니다."
        result = split_sentences(text)
        assert any("개요" in s for s in result)

    def test_korean_sentence_endings(self):
        text = "문장한다. 문장했다. 문장합니다."
        result = split_sentences(text)
        assert len(result) >= 2


class TestCalcSimilarity:
    """Tests for calc_similarity function."""

    def test_identical_sentences(self):
        sents = ["동일 문장입니다"] * 3
        assert calc_similarity(sents, sents) == 1.0

    def test_completely_different(self):
        a = ["완전히 다른 문장입니다"]
        b = ["아예 다른 내용이에요"]
        assert calc_similarity(a, b) < 0.1

    def test_empty_input(self):
        assert calc_similarity([], ["문장"]) == 0.0
        assert calc_similarity(["문장"], []) == 0.0
        assert calc_similarity([], []) == 0.0

    def test_partial_overlap(self):
        # Partial overlap with enough tokens for 3-grams
        a = ["가나다 라마바 사아자 바나나"]
        b = ["가나다 라마바 사아자 포도"]
        score = calc_similarity(a, b)
        assert 0.0 < score < 1.0


class TestCheckCrossBlogDedup:
    """Tests for check_cross_blog_dedup function."""

    def test_identical_posts_fail(self):
        """Identical text across 3 blogs should fail."""
        text = "## 개요\n남양주 물의 정원입니다. 방문객이 많습니다."
        posts = {
            "rotcha": text,
            "issue_techpawz": text,
            "techpawz": text,
        }
        result = check_cross_blog_dedup(posts)
        assert result.passed is False
        assert len(result.violations) > 0
        assert all("High similarity" in v for v in result.violations)

    def test_unique_posts_pass(self):
        """Completely different posts should pass."""
        posts = {
            "rotcha": "## 개요\n남양주 물의 정원은 아름다운 공간입니다.",
            "issue_techpawz": "## 비교 대상\nA제품 vs B제품 비교 분석입니다.",
            "techpawz": "## 체크리스트\n방문 전 확인사항을 정리했습니다.",
        }
        result = check_cross_blog_dedup(posts)
        assert result.passed is True
        assert len(result.violations) == 0

    def test_partial_overlap(self):
        """Posts with some shared content but below threshold should pass."""
        posts = {
            "rotcha": "## 개요\n남양주 물의 정원입니다. 경기도 남양주시에 위치합니다.",
            "issue_techpawz": "## 비교 대상\n남양주 물의 정원과 다른 정원을 비교합니다.",
            "techpawz": "## 체크리스트\n물의 정원 방문 전 체크리스트입니다.",
        }
        result = check_cross_blog_dedup(posts)
        # Some similarity but should be below 0.30 threshold
        assert all(s < 0.30 for s in result.pair_scores.values())

    def test_pair_scores_recorded(self):
        """All 3 pairs should have scores recorded."""
        posts = {
            "rotcha": "문장 A",
            "issue_techpawz": "문장 B",
            "techpawz": "문장 C",
        }
        result = check_cross_blog_dedup(posts)
        assert len(result.pair_scores) == 3


class TestCheckRoleElements:
    """Tests for check_role_elements function."""

    def test_role_check_rotcha_pass(self):
        """Rotcha with all required sections should pass."""
        contract = load("rotcha", category="product")
        body = """## 제품 개요
남양주 물의 정원 소개

## 핵심 특징/스펙
방문 코스 안내

## 사용법/활용법
교통편 안내

## 구매 참고사항
운영시간 안내
"""
        result = check_role_elements("rotcha", body, contract)
        assert result.passed is True
        assert len(result.missing_sections) == 0

    def test_role_check_rotcha_missing(self):
        """Rotcha missing sections should fail."""
        contract = load("rotcha", category="product")
        body = """## 제품 개요
남양주 물의 정원 소개
"""
        result = check_role_elements("rotcha", body, contract)
        assert result.passed is False
        assert "핵심 특징/스펙" in result.missing_sections
        assert "사용법/활용법" in result.missing_sections
        assert "구매 참고사항" in result.missing_sections

    def test_role_check_issue_missing_comparison(self):
        """Issue without comparison table should have it in missing."""
        contract = load("issue_techpawz", category="product")
        body = """## 비교 대상 제품
제품 A와 B

## 스펙 비교
성능과 가격

## 추천 결론
최고의 제품은 A입니다.
"""
        result = check_role_elements("issue_techpawz", body, contract)
        assert result.passed is False
        assert "가격대 비교" in result.missing_sections

    def test_role_check_techpawz_pass(self):
        """Techpawz with all required sections should pass."""
        contract = load("techpawz", category="product")
        body = """## 구매 체크리스트
방문 전 확인사항

## 가격/구매처
가격 정보

## 사용법/관리법
구매 방법

## 주의사항
주의할 점
"""
        result = check_role_elements("techpawz", body, contract)
        assert result.passed is True
        assert len(result.missing_sections) == 0

    def test_role_check_issue_pass(self):
        """Issue with all required sections should pass."""
        contract = load("issue_techpawz", category="product")
        body = """## 비교 대상 제품
제품 A와 B

## 스펙 비교
성능과 가격

## 가격대 비교
| 항목 | A | B |
|------|---|---|
| 가격 | 1만원 | 2만원 |

## 추천 결론
최고의 제품은 A입니다.
"""
        result = check_role_elements("issue_techpawz", body, contract)
        assert result.passed is True
        assert len(result.missing_sections) == 0
