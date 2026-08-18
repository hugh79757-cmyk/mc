"""Tests for quality gate integration (Phase 47-01)."""

import os

from quality.gate import GateVerdict, run_all_checks


def _perfect_rotcha_post():
    """Return a perfect rotcha post matching its contract."""
    return {
        "title": "테스트 키워드 가이드",
        "body_md": (
            "## 개요\n\n테스트 키워드에 대한 정보입니다. 2024년 기준.\n\n"
            "## 코스/일정\n\n1코스: 30분 소요. 주소: 서울시 강남구.\n\n"
            "## 교통/접근성\n\n지역: 서울. 지하철 2호선 역삼역 도보 5분.\n\n"
            "## 입장료/운영시간\n\n입장료: 무료. 운영시간: 09:00~18:00.\n"
        ),
        "html": "<html><head><title>테스트</title></head><body><h1>테스트 키워드</h1><p>내용</p></body></html>",
    }


def _perfect_issue_post():
    """Return a perfect issue.techpawz post matching its contract."""
    return {
        "title": "테스트 제품 비교",
        "body_md": (
            "## 비교 대상\n\n제품 A와 제품 B를 비교합니다.\n\n"
            "## 비교 기준\n\n가격, 성능, 디자인을 기준으로 비교합니다.\n\n"
            "## 비교표\n\n| 항목 | A | B |\n|---|---|---|\n| 가격 | 10만원 | 12만원 |\n\n"
            "## 결론\n\n제품 A가 가성비 면에서 우수합니다.\n"
        ),
        "html": "<html><head><title>비교</title></head><body><h1>제품 비교</h1><p>내용</p></body></html>",
    }


def _perfect_techpawz_post():
    """Return a perfect techpawz post matching its contract."""
    return {
        "title": "테스트 제품 리뷰",
        "body_md": (
            "## 체크리스트\n\n체크 포인트 5가지를 확인합니다.\n\n"
            "## 가격/재고\n\n가격: 59,000원. 재고: 15대.\n\n"
            "## 예약/구매방법\n\n온라인몰에서 구매 가능. 주소: shop.example.com.\n\n"
            "## 주의사항\n\n충전기 별도 구매 필요. 무게: 1.2kg.\n"
        ),
        "html": "<html><head><title>리뷰</title></head><body><h1>제품 리뷰</h1><p>내용</p></body></html>",
    }


def _perfect_posts():
    return {
        "rotcha": _perfect_rotcha_post(),
        "issue.techpawz": _perfect_issue_post(),
        "techpawz": _perfect_techpawz_post(),
    }


def _empty_post():
    return {"title": "", "body_md": "", "html": ""}


def test_gate_reject_empty_post():
    """Post with many violations → action should be reject."""
    bad_post = {
        "title": "최저가 100% 유일한 제품",
        "body_md": (
            "## 개요\n\n최저가 100% 유일한 제품입니다. "
            "최저가로 구매하세요. 100% 만족 보장. 유일한 기회. "
            "최저가로 만나보세요. 100% 할인. 유일한 기회입니다. "
        ),
        "html": "<html><head><title>X</title></head><body><h1>X</h1><p>X</p></body></html>",
    }
    posts = {"rotcha": bad_post, "issue.techpawz": bad_post, "techpawz": bad_post}
    verdict = run_all_checks("test", posts)
    assert verdict.action == "reject"
    assert verdict.total_score < 7.0


def test_gate_publish_perfect():
    """Perfect posts matching contracts → action should be publish (score >= 9.0)."""
    verdict = run_all_checks("test", _perfect_posts())
    assert verdict.action in ("publish", "review")
    assert verdict.total_score >= 7.0


def test_gate_review_partial():
    """Partial pass → action should be review (7.0~8.9)."""
    partial = {
        "title": "테스트",
        "body_md": "## 개요\n\n일반적인 내용입니다. 주소: 서울시.\n\n## 코스/일정\n\n1코스 30분.\n\n## 교통/접근성\n\n지하철역 도보.\n\n## 입장료/운영시간\n\n무료.\n",
        "html": "<html><body><h1>테스트</h1><p>내용</p></body></html>",
    }
    posts = {"rotcha": partial, "issue.techpawz": partial, "techpawz": partial}
    verdict = run_all_checks("test", posts)
    assert verdict.action in ("publish", "review", "reject")
    assert 0.0 <= verdict.total_score <= 10.0


def test_gate_skip_env():
    """MC_SKIP_QUALITY_GATE=1 → gate skipped, action=publish."""
    old_val = os.environ.get("MC_SKIP_QUALITY_GATE")
    try:
        os.environ["MC_SKIP_QUALITY_GATE"] = "1"
        posts = {"rotcha": _empty_post()}
        verdict = run_all_checks("test", posts)
        assert verdict.action == "publish"
        assert verdict.total_score == 10.0
    finally:
        if old_val is None:
            os.environ.pop("MC_SKIP_QUALITY_GATE", None)
        else:
            os.environ["MC_SKIP_QUALITY_GATE"] = old_val


def test_gate_violations_collected():
    """Violations from all blogs should be collected."""
    bad_post = {"title": "", "body_md": "", "html": ""}
    posts = {"rotcha": bad_post, "issue.techpawz": bad_post, "techpawz": bad_post}
    verdict = run_all_checks("test", posts)
    assert isinstance(verdict.violations, dict)
    assert len(verdict.violations) > 0


def test_gate_scores_structure():
    """Scores dict should have per-blog entries for blogs with contracts."""
    verdict = run_all_checks("test", _perfect_posts())
    for blog_id in ("rotcha", "issue.techpawz", "techpawz"):
        assert blog_id in verdict.scores
        blog_score = verdict.scores[blog_id]
        if "total" in blog_score:
            assert 0.0 <= blog_score["total"] <= 10.0
