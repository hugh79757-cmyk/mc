"""
test_frontmatter_utils.py — frontmatter_utils 모듈 단위 테스트 (Phase 26, Plan 01-01)

chain_drafter.py 의 기존 테스트 (test_chain_drafter.py) 와 동일한 동작을
frontmatter_utils 모듈에 대해 재검증하고, chain_drafter 의 wrapper 가
동일 결과를 위임하는지 확인한다.
"""

import pytest


# ── ensure_frontmatter ──────────────────────────────────────────────

class TestEnsureFrontmatter:
    def test_adds_when_missing(self):
        from frontmatter_utils import ensure_frontmatter

        draft_md = """## 서론

본문 내용입니다.

## 결론

결론 내용."""

        post = {
            "title": "테스트 포스트",
            "tags": ["테스트", "기술"],
            "category_guess": "기술",
        }

        result = ensure_frontmatter(draft_md, post)

        assert result.startswith("---\n")
        assert 'title: "테스트 포스트"' in result
        assert "draft: true" in result
        assert 'categories: ["기술"]' in result
        assert "## 서론" in result
        assert "본문 내용입니다" in result

    def test_preserves_existing(self):
        from frontmatter_utils import ensure_frontmatter

        existing_fm = """---
title: "기존 타이틀"
description: "기존 설명"
tags: ["기존태그"]
categories: ["기존카테고리"]
featureimage: ""
---

## 기존 본문

기존 본문 내용입니다."""

        post = {
            "title": "새 타이틀",
            "tags": ["새태그"],
            "category_guess": "새카테고리",
        }

        result = ensure_frontmatter(existing_fm, post)

        assert result.startswith("---\n")
        assert result.count("---") == 2
        assert 'title: "기존 타이틀"' in result
        assert 'categories: ["기존카테고리"]' in result
        assert "## 기존 본문" in result
        assert result.count("title:") == 1
        assert result.count("categories:") == 1

    def test_partial_opening_only(self):
        from frontmatter_utils import ensure_frontmatter

        partial_fm = '---\ntitle: "Partial"\n\n## 본문\n\n본문 내용.'

        post = {
            "title": "새 포스트",
            "tags": ["태그"],
            "category_guess": "일반",
        }

        result = ensure_frontmatter(partial_fm, post)

        assert result.startswith("---\n")
        assert "## 본문" in result
        assert "본문 내용" in result

    def test_empty_draft(self):
        from frontmatter_utils import ensure_frontmatter

        post = {"title": "Test", "tags": [], "category_guess": "일반"}
        assert ensure_frontmatter("", post) == ""
        assert ensure_frontmatter("   ", post) == "   "

    def test_tags_string_not_list(self):
        from frontmatter_utils import ensure_frontmatter

        draft_md = "## Content\n\nBody."
        post = {
            "title": "Test",
            "tags": "태그1, 태그2, 태그3",
            "category_guess": "기술",
        }

        result = ensure_frontmatter(draft_md, post)

        assert 'tags: ["태그1", "태그2", "태그3"]' in result

    def test_tags_empty(self):
        from frontmatter_utils import ensure_frontmatter

        draft_md = "## Content\n\nBody."
        post = {
            "title": "Test",
            "tags": [],
            "category_guess": "일반",
        }

        result = ensure_frontmatter(draft_md, post)

        assert "tags: []" in result
        assert 'categories: ["일반"]' in result

    def test_rejects_non_dict_post(self):
        """T-26-01: post 가 dict 가 아니면 ValueError."""
        from frontmatter_utils import ensure_frontmatter

        with pytest.raises(ValueError):
            ensure_frontmatter("## Content\n\nBody.", None)
        with pytest.raises(ValueError):
            ensure_frontmatter("## Content\n\nBody.", "not-a-dict")

    def test_rejects_oversized_input(self):
        """T-26-02: 입력 크기 상한 초과 시 ValueError."""
        from frontmatter_utils import (
            ensure_frontmatter, MAX_FRONTMATTER_INPUT_CHARS,
        )

        post = {"title": "Test", "tags": [], "category_guess": "일반"}
        huge = "## Content\n" + ("x" * (MAX_FRONTMATTER_INPUT_CHARS + 10))
        with pytest.raises(ValueError):
            ensure_frontmatter(huge, post)


# ── ensure_frontmatter_closer ───────────────────────────────────────

class TestEnsureFrontmatterCloser:
    def test_adds_missing_closer(self):
        from frontmatter_utils import ensure_frontmatter_closer

        draft = '---\ntitle: "Test"\n\n## 본문\n\n내용'
        result = ensure_frontmatter_closer(draft)
        assert result.startswith("---\n")
        assert result.count("---") == 2
        assert "## 본문" in result

    def test_preserves_existing_closer(self):
        from frontmatter_utils import ensure_frontmatter_closer

        draft = '---\ntitle: "Test"\n---\n\n## 본문'
        result = ensure_frontmatter_closer(draft)
        assert result == draft

    def test_no_frontmatter(self):
        from frontmatter_utils import ensure_frontmatter_closer

        draft = "## 본문\n\n내용"
        assert ensure_frontmatter_closer(draft) == draft

    def test_no_empty_line(self):
        from frontmatter_utils import ensure_frontmatter_closer

        draft = '---\ntitle: "Test"\ndraft: true'
        result = ensure_frontmatter_closer(draft)
        assert result.count("---") == 2
        assert 'title: "Test"' in result


# ── build_frontmatter ───────────────────────────────────────────────

class TestBuildFrontmatter:
    def test_creates_valid_yaml(self):
        from frontmatter_utils import build_frontmatter
        import yaml

        post = {
            "title": "테스트 포스트",
            "tags": ["테스트", "기술"],
            "category_guess": "기술",
        }
        body = "## 서론\n\n본문 내용입니다.\n\n## 결론\n\n결론 내용입니다."

        result = build_frontmatter(post, body)

        assert result.startswith("---\n")
        end = result.find("---", 3)
        assert end != -1
        fm_text = result[4:end].strip()
        parsed = yaml.safe_load(fm_text)
        assert parsed["title"] == "테스트 포스트"
        assert parsed["draft"] is True
        assert "테스트" in parsed["tags"]
        assert parsed["categories"] == ["기술"]
        assert body in result

    def test_includes_featureimage(self):
        from frontmatter_utils import build_frontmatter

        post = {"title": "Test", "tags": ["tag"], "category_guess": "일반"}
        body = "## Content\n\nBody."
        result = build_frontmatter(post, body)
        assert 'featureimage: ""' in result

    def test_extracts_description(self):
        from frontmatter_utils import build_frontmatter

        post = {"title": "Test", "tags": [], "category_guess": "일반"}
        body = "이것은 첫 번째 문장입니다. 이것은 두 번째 문장입니다.\n\n## 본론\n\n본문."
        result = build_frontmatter(post, body)

        assert 'description: "이것은 첫 번째 문장입니다' in result
        assert len(result.split('description: "')[1].split('"')[0]) <= 150

    def test_handles_special_chars(self):
        from frontmatter_utils import build_frontmatter

        post = {
            "title": 'Test "Special" Title',
            "tags": ["tag"],
            "category_guess": '일반"카테고리',
        }
        body = "## Content\n\nBody."
        result = build_frontmatter(post, body)
        assert 'title: "Test \\"Special\\" Title"' in result
        assert 'categories: ["일반\\"카테고리"]' in result


# ── wrapper 위임 검증 (chain_drafter 와 동일 동작) ──────────────────

class TestChainDrafterWrappers:
    def test_ensure_frontmatter_wrapper_delegates(self):
        from chain_drafter import _ensure_frontmatter
        from frontmatter_utils import ensure_frontmatter

        post = {
            "title": "테스트 포스트",
            "tags": ["테스트"],
            "category_guess": "기술",
        }
        draft = "## 서론\n\n본문 내용입니다."
        assert _ensure_frontmatter(draft, post) == ensure_frontmatter(draft, post)

    def test_ensure_frontmatter_closer_wrapper_delegates(self):
        from chain_drafter import _ensure_frontmatter_closer
        from frontmatter_utils import ensure_frontmatter_closer

        draft = '---\ntitle: "Test"\n\n## 본문'
        assert _ensure_frontmatter_closer(draft) == ensure_frontmatter_closer(draft)

    def test_build_frontmatter_wrapper_delegates(self):
        from chain_drafter import _build_frontmatter
        from frontmatter_utils import build_frontmatter

        post = {"title": "Test", "tags": [], "category_guess": "일반"}
        body = "## Content\n\nBody."
        assert _build_frontmatter(post, body) == build_frontmatter(post, body)

    def test_publisher_core_exports_ensure_frontmatter(self):
        import chain_publisher_core
        import frontmatter_utils

        assert chain_publisher_core.ensure_frontmatter is frontmatter_utils.ensure_frontmatter
