"""Tests for chain_drafter.py — AI 초안 생성 및 체인 컨텍스트 주입."""
import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest


class TestStripPromptLeak:
    """_strip_prompt_leak 함수 테스트."""

    def test_removes_prompt_headers_after_frontmatter(self):
        """frontmatter 이후 프롬프트 헤더 제거."""
        from chain_drafter import _strip_prompt_leak

        text = """---
title: "Test"
draft: true
---

## 서론

본론 내용.

## 본론

분석 내용.

# Role (역할)

이것은 프롬프트 유출입니다.

## 결론

결론 내용."""

        result = _strip_prompt_leak(text)

        assert "## 서론" in result  # 본문 헤더는 유지
        assert "## 본론" in result
        assert "# Role (역할)" not in result  # 프롬프트 헤더 제거
        assert "이것은 프롬프트 유출입니다" not in result

    def test_removes_all_known_prompt_patterns(self):
        """알려진 모든 프롬프트 패턴 제거."""
        from chain_drafter import _strip_prompt_leak
        
        patterns = [
            "# SEO 기본 원칙",
            "## title 규칙",
            "## description 규칙",
            "# Content Structure",
            "## 절대 금지",
            "# Chain Context",
            "이전 포스트 (",
        ]
        
        for pattern in patterns:
            text = f"---\ntitle: Test\ndraft: true\n---\n\n{pattern}\n\n본문."
            result = _strip_prompt_leak(text)
            assert pattern not in result, f"Pattern not removed: {pattern}"

    def test_preserves_frontmatter(self):
        """frontmatter 보존 확인."""
        from chain_drafter import _strip_prompt_leak

        text = """---
title: "Test Title"
description: "Desc"
tags: ["태그1", "태그2"]
categories: ["카테고리"]
draft: true
---

본문 내용."""

        result = _strip_prompt_leak(text)
        assert result.startswith("---")
        assert 'title: "Test Title"' in result
        assert 'tags: ["태그1", "태그2"]' in result


class TestParseAIOutput:
    """parse_ai_output 함수 테스트 (chain_models에서 임포트)."""

    def test_extracts_body_from_markdown(self):
        """parse_ai_output이 본문을 추출."""
        from chain_models import parse_ai_output

        text = """---
title: "Test"
draft: true
---

## 서론

본문 내용."""
        result = parse_ai_output(text)
        assert "## 서론" in result.body
        assert "본문 내용" in result.body

    def test_handles_no_frontmatter(self):
        """frontmatter 없는 경우에도 본문 추출."""
        from chain_models import parse_ai_output

        text = "그냥 본문만 있는 경우."
        result = parse_ai_output(text)
        assert "그냥 본문만 있는 경우" in result.body


class TestAIOutputValidation:
    """AIOutput/AIOutputMeta 스키마 검증 — 계약 1 독립 검증."""

    def test_aioutput_rejects_extra_fields(self):
        """AIOutput에 정의되지 않은 필드 전달 시 ValidationError."""
        from pydantic import ValidationError
        from chain_models import AIOutput

        with pytest.raises(ValidationError):
            AIOutput(body="test body", unknown_field="should_not_be_allowed")

    def test_aioutput_meta_rejects_extra_fields(self):
        """AIOutputMeta에 정의되지 않은 필드 전달 시 ValidationError."""
        from pydantic import ValidationError
        from chain_models import AIOutputMeta

        with pytest.raises(ValidationError):
            AIOutputMeta(image_type="photo", image_keyword="cat", extra_bad="reject")

    def test_aioutput_requires_keyword_for_photo(self):
        """image_type='photo' + image_keyword='' → ValidationError."""
        from pydantic import ValidationError
        from chain_models import AIOutputMeta

        with pytest.raises(ValidationError, match="image_keyword"):
            AIOutputMeta(image_type="photo", image_keyword="")

    def test_aioutput_requires_chart_data_for_chart(self):
        """image_type='chart' + chart_data=None → ValidationError."""
        from pydantic import ValidationError
        from chain_models import AIOutputMeta

        with pytest.raises(ValidationError, match="chart_data"):
            AIOutputMeta(image_type="chart", chart_type="bar", chart_data=None)

    def test_parse_ai_output_removes_json_fence_from_body(self):
        """parse_ai_output 결과 body에 JSON 코드블록이 없어야 함."""
        from chain_models import parse_ai_output

        text = "본문 시작입니다.\n\n```json\n{\"image_type\": \"photo\", \"image_keyword\": \"test\"}\n```\n\n본문 끝입니다."
        result = parse_ai_output(text)

        assert "```json" not in result.body
        assert "image_type" not in result.body
        assert "image_keyword" not in result.body
        assert "본문 시작입니다" in result.body
        assert "본문 끝입니다" in result.body


class TestDraftChain:
    """draft_chain 통합 테스트."""

    @patch("chain_drafter.generate")
    @patch("chain_drafter._load_chain_cfg")
    @patch("chain_drafter._load_prompts")
    @patch("chain_drafter.get_chain_posts")
    @patch("chain_drafter.update_post_draft")
    @patch("chain_db.update_image_meta")
    def test_draft_chain_creates_three_posts(
        self,
        mock_update_image_meta,
        mock_update_draft,
        mock_get_posts,
        mock_load_prompts,
        mock_load_config,
        mock_generate,
        sample_chain_config,
        sample_prompts,
    ):
        """체인당 3개 포스트 초안 생성."""
        mock_load_config.return_value = sample_chain_config
        mock_load_prompts.return_value = sample_prompts

        mock_get_posts.return_value = [
            {"id": 1, "step": 1, "title": "1단계", "target_keyword": "키워드1", "category_guess": "기술", "depth": 0},
            {"id": 2, "step": 2, "title": "2단계", "target_keyword": "키워드2", "category_guess": "기술", "depth": 1},
            {"id": 3, "step": 3, "title": "3단계", "target_keyword": "키워드3", "category_guess": "기술", "depth": 2},
        ]

        mock_generate.return_value = {
            "content": """---
title: "Test Post"
description: "Test description"
tags: ["테스트", "기술"]
categories: ["기술"]
draft: true
---

## 서론

서론입니다.

## 본론

본론입니다.

## 결론

결론입니다.

```json
{"image_type": "photo", "image_keyword": "test-keyword", "image_reason": "test"}
```""",
            "model": "test-model",
        }

        from chain_drafter import draft_chain
        result = draft_chain(1, "테스트")

        assert len(result) == 3
        assert mock_update_draft.call_count == 3

        for call in mock_update_draft.call_args_list:
            post_id, draft_md, slug = call[0]
            assert draft_md.startswith("---")
            assert "draft: true" in draft_md
            assert "<!--todo:image-->" in draft_md

    @patch("chain_drafter.generate")
    @patch("chain_drafter._load_chain_cfg")
    @patch("chain_drafter._load_prompts")
    @patch("chain_drafter.get_chain_posts")
    @patch("chain_drafter.update_post_draft")
    @patch("chain_db.update_image_meta")
    def test_draft_chain_includes_chain_context(
        self,
        mock_update_image_meta,
        mock_update_draft,
        mock_get_posts,
        mock_load_prompts,
        mock_load_config,
        mock_generate,
        sample_chain_config,
        sample_prompts,
    ):
        """체인 컨텍스트(이전/다음 포스트 정보)가 프롬프트에 주입."""
        mock_load_config.return_value = sample_chain_config
        mock_load_prompts.return_value = sample_prompts

        mock_get_posts.return_value = [
            {"id": 1, "step": 1, "title": "1단계", "target_keyword": "키워드1", "category_guess": "기술", "depth": 0},
            {"id": 2, "step": 2, "title": "2단계", "target_keyword": "키워드2", "category_guess": "기술", "depth": 1},
            {"id": 3, "step": 3, "title": "3단계", "target_keyword": "키워드3", "category_guess": "기술", "depth": 2},
        ]

        mock_generate.return_value = {
            "content": """---
title: "Test"
description: "Desc"
tags: ["태그"]
categories: ["카테고리"]
draft: true
---

Content
<!--todo:image-->""",
            "model": "test-model",
        }

        from chain_drafter import draft_chain
        draft_chain(1, "테스트")

        # Verify chain context was passed in prompt to generate()
        call_args_list = mock_generate.call_args_list
        assert len(call_args_list) == 3
        for call in call_args_list:
            args, kwargs = call
            # generate(system_prompt, user_prompt, tier=..., temperature=...)
            user_prompt = args[1] if len(args) > 1 else kwargs.get("user_prompt", "")
            assert "이전 포스트" in user_prompt or "chain" in user_prompt.lower()
            assert "1단계" in user_prompt or "다음 포스트" in user_prompt

    def test_frontmatter_validation_valid(self):
        """유효한 frontmatter는 검증 통과."""
        from chain_drafter import _validate_draft_frontmatter

        valid_draft = """---
title: "Valid Title"
description: "Description"
tags: ["태그1", "태그2"]
categories: ["카테고리"]
draft: true
---

Content here."""

        _validate_draft_frontmatter(valid_draft)

    def test_frontmatter_rejects_title_with_colon(self):
        """제목에 콜론 있으면 예외 발생."""
        from chain_drafter import _validate_draft_frontmatter

        invalid_draft = """---
title: "Title: With Colon"
description: "Desc"
tags: ["태그"]
categories: ["카테고리"]
draft: true
---

Content."""

        with pytest.raises(ValueError, match="콜론"):
            _validate_draft_frontmatter(invalid_draft)

    def test_frontmatter_rejects_multiline_tags(self):
        """tags/categories가 여러 줄이면 예외 발생."""
        from chain_drafter import _validate_draft_frontmatter

        invalid_draft = """---
title: "Title"
description: "Desc"
tags:
  - "태그1"
  - "태그2"
categories: ["카테고리"]
draft: true
---

Content."""

        with pytest.raises(ValueError, match="한 줄"):
            _validate_draft_frontmatter(invalid_draft)


class TestDraftSinglePost:
    """draft_single_post 단위 테스트."""

    @patch("chain_drafter.generate")
    @patch("chain_drafter._load_chain_cfg")
    @patch("chain_drafter._load_prompts")
    def test_draft_single_post_returns_valid_markdown(
        self,
        mock_load_prompts,
        mock_load_config,
        mock_generate,
        sample_chain_config,
        sample_prompts,
    ):
        """단일 포스트 초안 생성 반환."""
        mock_load_prompts.return_value = sample_prompts
        mock_load_config.return_value = sample_chain_config

        mock_generate.return_value = {
            "content": """---
title: "Single Post"
description: "Desc"
tags: ["태그"]
categories: ["카테고리"]
draft: true
---

Content

```json
{"image_type": "photo", "image_keyword": "test", "image_reason": "test"}
```""",
            "model": "test-model",
        }

        from chain_drafter import draft_single_post

        post = {"id": 1, "step": 1, "title": "Test", "target_keyword": "키워드", "category_guess": "기술", "depth": 0}

        draft_md, meta = draft_single_post(post, [post], "시드")

        assert draft_md.startswith("---")
        assert "draft: true" in draft_md
        assert meta["image_type"] is not None
        assert meta["image_type"] == "photo"


class TestIndentationFix:
    """Phase 9 들여쓰기 수정 검증."""

    def test_strip_prompt_leak_indentation_in_module(self):
        """_strip_prompt_leak 호출부가 올바르게 들여쓰기됨."""
        import chain_drafter
        import inspect

        source = inspect.getsource(chain_drafter.draft_single_post)
        lines = source.splitlines()
        strip_call_line = None
        for i, line in enumerate(lines):
            if "_strip_prompt_leak" in line:
                strip_call_line = i
                break

        assert strip_call_line is not None, "_strip_prompt_leak 호출 없음"

        for i in range(strip_call_line + 1, min(strip_call_line + 5, len(lines))):
            if lines[i].strip() and not lines[i].startswith(" "):
                pytest.fail(f"들여쓰기 누락 at line {i}: {lines[i]}")


class TestEnsureFrontmatterCloser:
    """_ensure_frontmatter_closer() 테스트."""

    def test_ensure_frontmatter_closer_adds_missing_closer(self):
        """closer 없는 frontmatter → closer 추가."""
        from chain_drafter import _ensure_frontmatter_closer
        draft = '---\ntitle: "Test"\ndraft: true\n\nBody text here.'
        result = _ensure_frontmatter_closer(draft)
        assert result.startswith("---\n")
        assert result.count("---") >= 2
        end = result.find("---", 3)
        assert end != -1
        body = result[end + 3:].strip()
        assert "Body text here" in body

    def test_ensure_frontmatter_closer_preserves_existing_closer(self):
        """closer가 이미 있으면 그대로 반환."""
        from chain_drafter import _ensure_frontmatter_closer
        draft = '---\ntitle: "Test"\n---\n\nBody text.'
        result = _ensure_frontmatter_closer(draft)
        assert result == draft

    def test_ensure_frontmatter_closer_no_frontmatter(self):
        """frontmatter 없으면 그대로 반환."""
        from chain_drafter import _ensure_frontmatter_closer
        draft = "No frontmatter here.\n\nBody text."
        result = _ensure_frontmatter_closer(draft)
        assert result == draft

    def test_ensure_frontmatter_closer_no_empty_line(self):
        """빈 줄이 없으면 전체를 frontmatter로 간주."""
        from chain_drafter import _ensure_frontmatter_closer
        draft = '---\ntitle: "Test"\ndraft: true'
        result = _ensure_frontmatter_closer(draft)
        assert result.endswith("\n---\n")
        assert result.count("---") >= 2


class TestValidateDraftSchema:
    """_validate_draft_schema() 테스트."""

    def test_validate_draft_schema_with_valid_draft(self):
        """유효한 초안 검증 통과."""
        from chain_drafter import _validate_draft_schema
        
        valid_draft = """---
title: "테스트 포스트"
description: "테스트 설명"
tags: [테스트]
categories: [카테고리]
---

## 첫 번째 섹션

이것은 본문 내용입니다.

## 두 번째 섹션

여기에는 이미지 마커가 있습니다: <!--todo:image-->

더 많은 내용..."""
        
        result, message = _validate_draft_schema(valid_draft)
        assert result is True
        assert message == "스키마 검증 통과"

    def test_validate_draft_schema_without_h2(self):
        """H2 헤딩 없는 초안 검증 실패."""
        from chain_drafter import _validate_draft_schema
        
        invalid_draft = """---
title: "테스트 포스트"
description: "테스트 설명"
tags: [테스트]
categories: [카테고리]
---

# H1 헤딩만 있음

이것은 본문 내용입니다. 이미지 마커: <!--todo:image-->"""
        
        result, message = _validate_draft_schema(invalid_draft)
        assert result is False
        assert "H2 헤딩이 필요합니다" in message

    def test_validate_draft_schema_without_image_marker(self):
        """이미지 마커 없는 초안 검증 실패."""
        from chain_drafter import _validate_draft_schema
        
        invalid_draft = """---
title: "테스트 포스트"
description: "테스트 설명"
tags: [테스트]
categories: [카테고리]
---

## 첫 번째 섹션

이것은 본문 내용입니다. 이미지 마커가 없습니다.

## 두 번째 섹션

더 많은 내용..."""
        
        result, message = _validate_draft_schema(invalid_draft)
        assert result is False
        assert "이미지 마커" in message

    def test_validate_draft_schema_missing_frontmatter(self):
        """Frontmatter 없는 초안 검증 실패."""
        from chain_drafter import _validate_draft_schema
        
        invalid_draft = """## 서론

이것은 본문 내용입니다.

## 본론

이미지 마커: <!--todo:image-->"""
        
        result, message = _validate_draft_schema(invalid_draft)
        assert result is False
        assert "Frontmatter" in message

    def test_validate_draft_schema_missing_required_field(self):
        """필수 필드 없는 초안 검증 실패."""
        from chain_drafter import _validate_draft_schema
        
        invalid_draft = """---
title: "테스트 포스트"
description: "테스트 설명"
tags: [테스트]
---

## 섹션

이것은 본문 내용입니다. 이미지 마커: <!--todo:image-->"""
        
        result, message = _validate_draft_schema(invalid_draft)
        assert result is False
        # Categories 필드 누락 시 발생할 수 있는 메시지 확인
        assert ("필수 필드" in message and "categories" in message) or "필수 필드" in message


    def test_validate_draft_schema_missing_image_keyword(self):
        """이미지 마커 있지만 image_keyword 없는 경우 실패 (차트 아님)."""
        from chain_drafter import _validate_draft_schema
        
        invalid_draft = """---
title: "테스트 포스트"
description: "테스트 설명"
tags: [테스트]
categories: [카테고리]
---

## 섹션

이것은 본문 내용입니다. 이미지 마커: <!--todo:image-->

더 많은 내용..."""
         
        # 메타에 image_keyword가 None 또는 빈 문자열인 경우를 시뮬레이트
        result, message = _validate_draft_schema(invalid_draft, meta={"image_keyword": None})
        assert result is False
        assert "image_keyword가 비어 있습니다" in message

    def test_validate_draft_schema_chart_marker_no_keyword(self):
        """차트 마커지만 image_keyword 없는 경우 통과."""
        from chain_drafter import _validate_draft_schema
        
        valid_draft = """---
title: "테스트 차트 포스트"
description: "테스트 설명"
tags: [테스트]
categories: [카테고리]
---

## 섹션

이것은 차트입니다. <!--todo:chart-->

더 많은 내용..."""
         
        # 차트 마커인 경우 image_keyword가 없어도 통과
        result, message = _validate_draft_schema(valid_draft, meta={"image_keyword": None})
        assert result is True
        assert message == "스키마 검증 통과"


class TestEnsureFrontmatter:
    """_ensure_frontmatter() 테스트 — Phase 14 P1 frontmatter patch 정식화."""

    def test_ensure_frontmatter_adds_when_missing(self):
        """frontmatter 없는 draft_md → title/tags/categories로 frontmatter 생성."""
        from chain_drafter import _ensure_frontmatter

        draft_md = """## 서론

본문 내용입니다.

## 결론

결론 내용."""

        post = {
            "title": "테스트 포스트",
            "tags": ["테스트", "기술"],
            "category_guess": "기술",
        }

        result = _ensure_frontmatter(draft_md, post)

        # frontmatter가 앞에 추가되어야 함
        assert result.startswith("---\n")
        assert 'title: "테스트 포스트"' in result
        assert "draft: true" in result
        assert 'categories: ["기술"]' in result
        # 원본 본문이 그대로 이어져야 함
        assert "## 서론" in result
        assert "본문 내용입니다" in result

    def test_ensure_frontmatter_preserves_existing(self):
        """이미 유효한 frontmatter가 있는 draft_md → 보존 (중복 추가 안 함)."""
        from chain_drafter import _ensure_frontmatter

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

        result = _ensure_frontmatter(existing_fm, post)

        # 기존 frontmatter 보존 (새로 추가되지 않음)
        assert result.startswith("---\n")
        assert result.count("---") == 2
        assert 'title: "기존 타이틀"' in result  # 기존 타이틀 유지
        assert 'categories: ["기존카테고리"]' in result  # 기존 카테고리 유지
        assert "## 기존 본문" in result
        # 새로운 title/categories가 중복 추가되지 않음
        assert result.count("title:") == 1
        assert result.count("categories:") == 1

    def test_ensure_frontmatter_partial_opening_only(self):
        """열기 ---는 있지만 닫기 ---가 없으면 → frontmatter 생성 (보존 안 함)."""
        from chain_drafter import _ensure_frontmatter

        # frontmatter가 열리지만 닫히지 않은 경우
        partial_fm = '---\ntitle: "Partial"\n\n## 본문\n\n본문 내용.'

        post = {
            "title": "새 포스트",
            "tags": ["태그"],
            "category_guess": "일반",
        }

        result = _ensure_frontmatter(partial_fm, post)

        # 닫는 ---가 없으면 새로운 frontmatter를 앞에 추가
        assert result.startswith("---\n")
        # 기존 content가 그대로 이어져야 함
        assert "## 본문" in result
        assert "본문 내용" in result

    def test_ensure_frontmatter_empty_draft(self):
        """빈 draft_md → 그대로 반환."""
        from chain_drafter import _ensure_frontmatter

        post = {"title": "Test", "tags": [], "category_guess": "일반"}
        assert _ensure_frontmatter("", post) == ""
        assert _ensure_frontmatter("   ", post) == "   "

    def test_ensure_frontmatter_tags_string_not_list(self):
        """tags가 list 대신 콤마 구분 문자열인 경우 → list로 파싱."""
        from chain_drafter import _ensure_frontmatter

        draft_md = "## Content\n\nBody."
        post = {
            "title": "Test",
            "tags": "태그1, 태그2, 태그3",
            "category_guess": "기술",
        }

        result = _ensure_frontmatter(draft_md, post)

        assert 'tags: ["태그1", "태그2", "태그3"]' in result

    def test_ensure_frontmatter_tags_empty(self):
        """tags가 빈 리스트인 경우 → 빈 tags로 frontmatter 생성."""
        from chain_drafter import _ensure_frontmatter

        draft_md = "## Content\n\nBody."
        post = {
            "title": "Test",
            "tags": [],
            "category_guess": "일반",
        }

        result = _ensure_frontmatter(draft_md, post)

        assert "tags: []" in result
        assert 'categories: ["일반"]' in result
