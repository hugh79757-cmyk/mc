"""Tests for audit/audit_format.py — 포스트 형식/시각 구조 검증 단위테스트.

모든 테스트는 DB/파일 I/O 없이 self-contained.
"""

import pytest


# ── 프론트매터 파싱 ──────────────────────────────────────────────


class TestSplitFrontmatter:
    """_split_frontmatter 단위테스트."""

    def test_split_with_frontmatter(self):
        from audit.audit_format import _split_frontmatter
        text = "---\ntitle: test\ndraft: false\n---\n\n본문입니다."
        fm, body = _split_frontmatter(text)
        assert "title: test" in fm
        assert "본문입니다." in body

    def test_split_without_frontmatter(self):
        from audit.audit_format import _split_frontmatter
        text = "본문만 있습니다."
        fm, body = _split_frontmatter(text)
        assert fm == ""
        assert body == "본문만 있습니다."

    def test_split_empty(self):
        from audit.audit_format import _split_frontmatter
        fm, body = _split_frontmatter("")
        assert fm == ""
        assert body == ""

    def test_split_leading_whitespace(self):
        from audit.audit_format import _split_frontmatter
        text = "  \n---\ntitle: x\n---\nbody"
        fm, body = _split_frontmatter(text)
        assert "title: x" in fm
        assert "body" in body


class TestParseFrontmatter:
    """_parse_frontmatter 단위테스트."""

    def test_parse_valid(self):
        from audit.audit_format import _parse_frontmatter
        fm = _parse_frontmatter('title: "테스트"\ndraft: false')
        assert fm["title"] == "테스트"
        assert fm["draft"] is False

    def test_parse_empty(self):
        from audit.audit_format import _parse_frontmatter
        assert _parse_frontmatter("") == {}

    def test_parse_invalid_yaml(self):
        from audit.audit_format import _parse_frontmatter
        # YAML parser is lenient — most strings parse as scalars, not errors
        result = _parse_frontmatter(":::invalid:::")
        # Should return something (scalar string) or empty dict, not crash
        assert isinstance(result, (dict, str))


# ── 카드 주입 수 ────────────────────────────────────────────────


class TestCardCount:
    """check_card_count 단위테스트."""

    def test_d0_ok(self):
        """D0에 chain-card 2개 → 통과."""
        from audit.audit_format import check_card_count
        body = " 본문\n\n{{< chain-card title=\"a\" url=\"#\" >}}\n\n## H2\n\n{{< chain-card title=\"b\" url=\"#\" >}}"
        assert check_card_count(body, depth=0) == []

    def test_d0_exceeds(self):
        """D0에 chain-card 3개 → 실패."""
        from audit.audit_format import check_card_count
        body = "{{< chain-card title=\"a\" url=\"#\" >}}\n{{< chain-card title=\"b\" url=\"#\" >}}\n{{< chain-card title=\"c\" url=\"#\" >}}"
        findings = check_card_count(body, depth=0)
        assert len(findings) == 1
        assert "초과" in findings[0]["detail"]

    def test_d2_ok(self):
        """D2에 외부링크 카드 1개 → 통과."""
        from audit.audit_format import check_card_count
        body = '<div style="margin:1.5em 0;padding:1em;border:1px solid #e5e7eb;border-radius:8px;background:#f0fdf4;text-align:center">관련 공식 사이트<br>바로가기 →</div>'
        assert check_card_count(body, depth=2) == []

    def test_d2_no_shortcode(self):
        """D2에 chain-card 있으면 실패."""
        from audit.audit_format import check_card_count
        body = '{{< chain-card title="a" url="#" >}}'
        findings = check_card_count(body, depth=2)
        assert len(findings) == 1
        assert "chain-card" in findings[0]["detail"]


# ── 카드 위치 ────────────────────────────────────────────────────


class TestCardPlacement:
    """check_card_placement 단위테스트."""

    def test_d0_correct_placement(self):
        """D0: 카드가 3번째 H2 앞, 마지막 H2 뒤 → 통과."""
        from audit.audit_format import check_card_placement
        body = (
            "## 첫 번째\n본문\n\n"
            "## 두 번째\n본문\n\n"
            "{{< chain-card title=\"mid\" url=\"#\" >}}\n\n"
            "## 세 번째\n본문\n\n"
            "## 네 번째\n본문\n\n"
            "{{< chain-card title=\"bot\" url=\"#\" >}}"
        )
        assert check_card_placement(body, depth=0) == []

    def test_d0_wrong_mid_placement(self):
        """D0: 중간 카드가 3번째 H2 뒤 → 실패."""
        from audit.audit_format import check_card_placement
        body = (
            "## 첫 번째\n본문\n\n"
            "## 두 번째\n본문\n\n"
            "## 세 번째\n본문\n\n"
            "{{< chain-card title=\"mid\" url=\"#\" >}}\n\n"
            "## 네 번째\n본문\n\n"
            "{{< chain-card title=\"bot\" url=\"#\" >}}"
        )
        findings = check_card_placement(body, depth=0)
        assert len(findings) == 1
        assert "중간 카드" in findings[0]["detail"]

    def test_d0_single_card_before_last_h2(self):
        """D0: 카드 1개가 마지막 H2 앞 → 실패."""
        from audit.audit_format import check_card_placement
        body = (
            "## 첫 번째\n본문\n\n"
            "{{< chain-card title=\"a\" url=\"#\" >}}\n\n"
            "## 두 번째\n본문"
        )
        findings = check_card_placement(body, depth=0)
        assert len(findings) == 1
        assert "마지막 H2" in findings[0]["detail"]


# ── H2 추출 ──────────────────────────────────────────────────────


class TestH2Extraction:
    """RE_H2 패턴 테스트."""

    def test_extract_h2(self):
        from audit.audit_format import RE_H2
        body = "## 첫 번째\n본문\n\n## 두 번째\n본문\n\n## 세 번째"
        matches = RE_H2.findall(body)
        assert matches == ["첫 번째", "두 번째", "세 번째"]

    def test_no_h2(self):
        from audit.audit_format import RE_H2
        assert RE_H2.findall("본문만 있습니다.") == []

    def test_h3_not_matched(self):
        from audit.audit_format import RE_H2
        assert RE_H2.findall("### H3 제목") == []


# ── 크로스링크 URL ───────────────────────────────────────────────


class TestCrossLinkUrl:
    """check_cross_link_url 단위테스트."""

    def test_d0_links_to_issue_techpawz(self):
        """D0 카드가 issue.techpawz.com을 가리킴 → 통과."""
        from audit.audit_format import check_cross_link_url
        body = '{{< chain-card title="다음" url="https://issue.techpawz.com/slug" >}}'
        assert check_cross_link_url(body, depth=0) == []

    def test_d0_wrong_domain(self):
        """D0 카드가 wrong 도메인 → 실패."""
        from audit.audit_format import check_cross_link_url
        body = '{{< chain-card title="다음" url="https://techpawz.com/slug" >}}'
        findings = check_cross_link_url(body, depth=0)
        assert len(findings) == 1
        assert "issue.techpawz.com" in findings[0]["detail"]

    def test_d1_links_to_techpawz(self):
        """D1 카드가 techpawz.com을 가리킴 → 통과."""
        from audit.audit_format import check_cross_link_url
        body = '{{< chain-card title="다음" url="https://techpawz.com/slug" >}}'
        assert check_cross_link_url(body, depth=1) == []

    def test_d2_no_check(self):
        """D2는 크로스링크 없음 → 검증 불필요."""
        from audit.audit_format import check_cross_link_url
        assert check_cross_link_url("본문", depth=2) == []


# ── 프론트매터 완성도 ────────────────────────────────────────────


class TestFrontmatter:
    """check_frontmatter 단위테스트."""

    def test_complete_frontmatter(self):
        """모든 필수 필드 존재 → 통과."""
        from audit.audit_format import check_frontmatter
        body = (
            '---\ntitle: "테스트"\ndescription: "설명"\n'
            'draft: false\nslug: test\n'
            'date: 2026-01-01\n'
            'featureimage: "https://r2.dev/img.jpg"\n---\n\n본문'
        )
        assert check_frontmatter(body) == []

    def test_missing_title(self):
        """title 누락 → 실패."""
        from audit.audit_format import check_frontmatter
        body = (
            '---\ndescription: "설명"\n'
            'draft: false\nslug: test\n'
            'date: 2026-01-01\n'
            'featureimage: "https://r2.dev/img.jpg"\n---\n\n본문'
        )
        findings = check_frontmatter(body)
        assert any("title" in f["detail"] for f in findings)

    def test_missing_featureimage(self):
        """featureimage 누락 → 실패."""
        from audit.audit_format import check_frontmatter
        body = (
            '---\ntitle: "테스트"\ndescription: "설명"\n'
            'draft: false\nslug: test\n'
            'date: 2026-01-01\n---\n\n본문'
        )
        findings = check_frontmatter(body)
        assert any("featureimage" in f["detail"] for f in findings)

    def test_draft_not_false(self):
        """draft가 true → 실패."""
        from audit.audit_format import check_frontmatter
        body = (
            '---\ntitle: "테스트"\ndescription: "설명"\n'
            'draft: true\nslug: test\n'
            'date: 2026-01-01\n'
            'featureimage: "https://r2.dev/img.jpg"\n---\n\n본문'
        )
        findings = check_frontmatter(body)
        assert any("draft" in f["detail"] for f in findings)

    def test_no_frontmatter(self):
        """프론트매터 자체 없음 → 실패."""
        from audit.audit_format import check_frontmatter
        findings = check_frontmatter("본문만 있습니다.")
        assert len(findings) == 1
        assert "프론트매터 없음" in findings[0]["detail"]

    def test_featureimage_not_url(self):
        """featureimage가 상대경로 → 실패."""
        from audit.audit_format import check_frontmatter
        body = (
            '---\ntitle: "테스트"\ndescription: "설명"\n'
            'draft: false\nslug: test\n'
            'date: 2026-01-01\n'
            'featureimage: "images/thumb.jpg"\n---\n\n본문'
        )
        findings = check_frontmatter(body)
        assert any("URL 형식" in f["detail"] for f in findings)


# ── 카드 타입 ────────────────────────────────────────────────────


class TestCardType:
    """check_card_type 단위테스트."""

    def test_d0_with_official_card(self):
        """D0에 chain-official-card → 실패."""
        from audit.audit_format import check_card_type
        body = '{{< chain-official-card title="a" url="#" >}}'
        findings = check_card_type(body, depth=0)
        assert len(findings) == 1
        assert "chain-official-card" in findings[0]["detail"]

    def test_d2_with_shortcode(self):
        """D2에 chain-card → card_count + card_type 둘 다 실패."""
        from audit.audit_format import check_card_type
        body = '{{< chain-card title="a" url="#" >}}'
        findings = check_card_type(body, depth=2)
        # chain-card 발견 + 외부링크 카드 없음 = 2건
        assert len(findings) == 2
        assert any("chain-card" in f["detail"] for f in findings)

    def test_d2_with_ext_card(self):
        """D2에 외부링크 카드만 → 통과."""
        from audit.audit_format import check_card_type
        body = '<div style="margin:1.5em 0;padding:1em;border:1px solid #e5e7eb;border-radius:8px;background:#f0fdf4;text-align:center">관련 공식 사이트<br>바로가기 →</div>'
        assert check_card_type(body, depth=2) == []


# ── DB 일관성 ────────────────────────────────────────────────────


class TestDbConsistency:
    """check_db_consistency 단위테스트."""

    def test_consistent_post(self):
        """정상 레코드 → 통과."""
        from audit.audit_format import check_db_consistency
        posts = [{
            "id": 1, "step": 1, "title": "테스트",
            "published_url": "https://example.com",
            "status": "published",
            "hugo_file_path": None,
            "card_injected": True,
            "card_injected_at": "2026-01-01",
        }]
        assert check_db_consistency(posts) == []

    def test_url_but_not_published(self):
        """published_url 존재 but status ≠ published/draft → 실패."""
        from audit.audit_format import check_db_consistency
        posts = [{
            "id": 1, "step": 1, "title": "테스트",
            "published_url": "https://example.com",
            "status": "pending",
            "hugo_file_path": None,
            "card_injected": False,
            "card_injected_at": None,
        }]
        findings = check_db_consistency(posts)
        assert len(findings) == 1
        assert "status=" in findings[0]["detail"]

    def test_injected_at_without_flag(self):
        """card_injected_at 존재 but card_injected=False → 실패."""
        from audit.audit_format import check_db_consistency
        posts = [{
            "id": 1, "step": 1, "title": "테스트",
            "published_url": "https://example.com",
            "status": "published",
            "hugo_file_path": None,
            "card_injected": False,
            "card_injected_at": "2026-01-01",
        }]
        findings = check_db_consistency(posts)
        assert len(findings) == 1
        assert "card_injected" in findings[0]["detail"]


# ── H2 구조 검증 ────────────────────────────────────────────────


class TestH2Structure:
    """check_h2_structure 단위테스트."""

    def test_exact_match(self):
        """H2 개수가 템플릿과 일치 → 통과 (개수 기준)."""
        from audit.audit_format import check_h2_structure
        # travel/step1: 4개 섹션
        body = (
            "## 위치와 기본 정보\n본문\n\n"
            "## 시설과 특징 살펴보기\n본문\n\n"
            "## 이용 안내와 방문 팁\n본문\n\n"
            "## 마무리 — 핵심 요약\n본문"
        )
        findings = check_h2_structure(body, category="travel", step=1)
        # 개수 일치 → h2_structure 항목 없음
        assert not any(f["check"] == "h2_structure" for f in findings)

    def test_count_mismatch(self):
        """H2 개수가 템플릿과 불일치 → 실패."""
        from audit.audit_format import check_h2_structure
        # travel/step1: 4개 예상, 실제 2개
        body = "## 위치와 기본 정보\n본문\n\n## 시설과 특징\n본문"
        findings = check_h2_structure(body, category="travel", step=1)
        assert any(f["check"] == "h2_structure" for f in findings)

    def test_medicine_3_sections(self):
        """medicine는 3개 섹션 → 3개 H2면 통과."""
        from audit.audit_format import check_h2_structure
        body = (
            "## 어떤 약·증상인가\n본문\n\n"
            "## 주요 정보 개요\n본문\n\n"
            "## 마무리 — 요약\n본문"
        )
        findings = check_h2_structure(body, category="medicine", step=1)
        assert not any(f["check"] == "h2_structure" for f in findings)


# ── H2 추출 패턴 ────────────────────────────────────────────────


class TestExtractKeywordFromTemplate:
    """_extract_keyword_from_template 단위테스트."""

    def test_normal(self):
        from audit.audit_format import _extract_keyword_from_template
        assert _extract_keyword_from_template("## {keyword} — 위치와 기본 정보") == "위치와 기본 정보"

    def test_with_mammiri(self):
        from audit.audit_format import _extract_keyword_from_template
        result = _extract_keyword_from_template("## 마무리 — {keyword} 핵심 요약")
        assert "마무리" in result
        assert "핵심 요약" in result

    def test_no_keyword(self):
        from audit.audit_format import _extract_keyword_from_template
        result = _extract_keyword_from_template("## 일반 제목")
        assert "일반 제목" in result
