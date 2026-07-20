"""pytest configuration and shared fixtures for mc project."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ─── Environment Setup ───

def pytest_configure(config):
    """Configure test environment before test collection."""
    # Set test environment variables
    os.environ.setdefault("OPENAI_API_KEY", "test-key")
    os.environ.setdefault("UNSPLASH_ACCESS_KEY", "test-unsplash")
    os.environ.setdefault("PEXELS_API_KEY", "test-pexels")
    os.environ.setdefault("KREA_API_KEY", "test-krea")
    os.environ.setdefault("R2_ENDPOINT_URL", "https://test.r2.cloudflarestorage.com")
    os.environ.setdefault("R2_ACCESS_KEY_ID", "test-access")
    os.environ.setdefault("R2_SECRET_ACCESS_KEY", "test-secret")
    os.environ.setdefault("R2_BUCKET_NAME", "test-bucket")
    os.environ.setdefault("R2_PUBLIC_URL", "https://img.test.com")


# ─── Fixtures ───

@pytest.fixture
def temp_dir():
    """Provide a temporary directory that cleans up after test."""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def mock_openai():
    """Mock OpenAI API responses."""
    with patch("openai.OpenAI") as mock:
        client = MagicMock()
        mock.return_value = client
        # Default chat completion response
        client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps({
                "topics": [{"title": "Test Topic", "angle": "Test Angle", "category_guess": "tech", "bridge_logic": "Test bridge"}]
            })))]
        )
        yield client


@pytest.fixture
def mock_requests():
    """Mock requests.get/post for HTTP calls."""
    with patch("requests.get") as mock_get, patch("requests.post") as mock_post:
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"results": [], "photos": []},
            raise_for_status=lambda: None,
            content=b"fake-image-data",
        )
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"id": "test-job"},
            raise_for_status=lambda: None,
        )
        yield {"get": mock_get, "post": mock_post}


@pytest.fixture
def mock_boto3():
    """Mock boto3 R2 client."""
    with patch("boto3.client") as mock:
        client = MagicMock()
        mock.return_value = client
        client.upload_file.return_value = None
        client.head_object.return_value = {"ContentLength": 100}
        client.head_bucket.return_value = {}
        yield client


@pytest.fixture
def sample_chain_config():
    """Sample chain_config.yaml content for testing."""
    return {
        "sites": {
            "rotcha": {
                "site_path": "/fake/rotcha-blog",
                "blog_id": "manual_rotcha",
                "base_url": "https://rotcha.kr",
                "publisher_type": "hugo",
                "hugo_root": "/fake/rotcha-blog",
                "theme": "Blowfish",
                "cf_pages_project": "rotcha-blog",
                "permalink_pattern": "/posts/:slug/",
                "content_dir": "content/posts",
            },
            "infohot": {
                "site_path": "/fake/informationhot-hugo",
                "blog_id": "manual_informationhot",
                "base_url": "https://informationhot.kr",
                "publisher_type": "hugo",
                "hugo_root": "/fake/informationhot-hugo",
                "theme": "PaperMod",
                "cf_pages_project": "informationhot-hugo",
                "permalink_pattern": "/posts/:slug/",
                "content_dir": "content/posts",
            },
            "techpawz": {
                "site_path": "/fake/techpawz-hugo",
                "blog_id": "manual_techpawz",
                "base_url": "https://techpawz.com",
                "publisher_type": "hugo",
                "hugo_root": "/fake/techpawz-hugo",
                "theme": "Blowfish",
                "cf_pages_project": "techpawz-hugo",
                "permalink_pattern": "/:slug/",
                "content_dir": "content/posts",
            },
        },
        "chain_directions": {
            "depth": {"label": "깊이", "step_roles": {1: "기초", 2: "분석", 3: "전문"}},
            "swallow": {"label": "역방향", "step_roles": {1: "구매", 2: "절약", 3: "금융"}},
            "lateral": {"label": "횡방향", "step_roles": {1: "주제", 2: "비교", 3: "비즈니스"}},
        },
        "keyword_mapping": {"tech": "depth", "shopping": "swallow", "travel": "lateral"},
        "chain_blogs": {0: "rotcha", 1: "infohot", 2: "techpawz"},
        "ai_writer": {"tier": "default", "temperature": 0.85},
        "thumbnail": {
            "provider": "auto",
            "fallback_chain": ["pexels", "pollinations", "krea"],
            "target_size": [1024, 1024],
            "text_overlay": {"enabled": True, "font": "assets/fonts/NotoSansKR-Regular.otf", "bg_alpha": 0.55},
        },
        "pollinations": {
            "enabled": True,
            "base_url": "https://image.pollinations.ai/prompt/",
            "width": 1024,
            "height": 1024,
            "model": "flux",
            "rate_limit_seconds": 15,
        },
    }


@pytest.fixture
def sample_prompts():
    """Sample prompts.yaml content for testing - matches actual prompt keys."""
    return {
        "derive_system": "You are a blog chain planner.",
        "derive_user_depth": "Seed: {seed}\nChain type: depth\nReturn JSON with 3 topics.",
        "derive_user_swallow": "Seed: {seed}\nChain type: swallow\nReturn JSON with 3 topics.",
        "derive_user_lateral": "Seed: {seed}\nChain type: lateral\nReturn JSON with 3 topics.",
        "draft_system": "You are a blog writer.",
        "draft_user": "Blog: {blog_name} ({blog_url})\nKeyword: {target_keyword}\nTitle: {title}\nAngle: {angle}\nCategory: {category}\n\nChain Context: {step} / {depth_role}\n\n{prev_context}\n\n{next_context}",
        "image_system": "Create image prompt.",
        "image_user": "Keyword: {keyword}, Blog: {blog}, Step: {step}",
    }


@pytest.fixture
def sample_draft_md():
    """Sample draft markdown with frontmatter."""
    return """---
title: "Test Post Title"
description: "Test description for SEO"
tags: ["테스트", "기술", "블로그"]
categories: ["기술"]
draft: true
---

## 서론

이것은 테스트 서론입니다.

## 본론

본론 내용입니다.

## 결론

결론입니다.

<!--todo:image-->
"""


@pytest.fixture
def sample_chain_post():
    """Sample chain post dict for testing."""
    return {
        "id": 1,
        "chain_id": 1,
        "step": 1,
        "slug": "test-post-1",
        "title": "Test Post Title",
        "target_keyword": "test keyword",
        "category_guess": "기술",
        "image_keyword": "test image",
        "image_prompt": "test prompt",
        "draft_md": """---
title: "Test Post Title"
description: "Test description"
tags: ["테스트", "기술"]
categories: ["기술"]
draft: true
---

## 서론

서론 내용.

## 본론

본론 내용.

## 결론

결론 내용.

<!--todo:image-->
""",
        "status": "drafted",
        "thumbnail_path": None,
        "thumbnail_source": None,
        "published_url": None,
    }


# ─── Test Helpers ───

def assert_valid_frontmatter(fm_text: str):
    """Assert frontmatter has required fields and valid format."""
    assert fm_text.startswith("---")
    assert "title:" in fm_text
    assert "description:" in fm_text
    assert "tags:" in fm_text
    assert "categories:" in fm_text
    assert "draft:" in fm_text
    # Check no colon in title (common bug)
    for line in fm_text.splitlines():
        if line.strip().startswith("title:"):
            assert ":" not in line.split("title:", 1)[1].strip().strip('"'), "Title contains colon"
    # Check one-line arrays
    for line in fm_text.splitlines():
        if "tags:" in line or "categories:" in line:
            assert line.count("[") == 1 and line.count("]") == 1, f"Array not one-line: {line}"


def assert_no_prompt_leak(text: str):
    """Assert no prompt leak patterns in text."""
    forbidden = [
        "# Role (역할)",
        "# SEO 기본 원칙",
        "## 서론",
        "## 본론",
        "## 결론",
        "# Chain Context",
        "절대 금지",
        "이미지 플레이스홀더",
        "다음은 요청하신",
    ]
    for pattern in forbidden:
        assert pattern not in text, f"Prompt leak detected: {pattern}"


def assert_no_unresolved_markers(text: str):
    """Assert no unresolved image/chart markers."""
    forbidden = [
        "<!-- thumbnail:",
        "<!-- image:",
        "<!--todo:image-->",
        "<!--todo:chart-->",
        "<!-- todo:image -->",
        "<!-- todo:chart -->",
    ]
    for pattern in forbidden:
        assert pattern not in text, f"Unresolved marker: {pattern}"


def assert_no_cta_leak(text: str):
    """Assert no AI-generated CTA blocks."""
    forbidden = ["더 깊이 알아보기", "더 자세히 보기", "이어서 실전 적용법", "관련 주제 보기"]
    for pattern in forbidden:
        assert pattern not in text, f"CTA leak detected: {pattern}"