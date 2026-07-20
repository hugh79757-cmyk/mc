"""Tests for image pipeline — thumbnail, pollinations, injector."""
import os
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestThumbnailGeneration:
    """image/thumbnail.py 테스트."""

    def test_add_text_overlay_creates_webp(self, temp_dir):
        """텍스트 오버레이 적용 후 WEBP 저장."""
        from image.thumbnail import add_text_overlay

        # Create dummy image
        from PIL import Image
        img = Image.new("RGB", (1024, 1024), color="blue")
        img_path = temp_dir / "source.jpg"
        img.save(img_path)

        result = add_text_overlay(img_path, "테스트 제목", "부제목")

        assert result.exists()
        assert result.suffix == ".webp"
        assert "thumb_" in result.name

    def test_add_text_overlay_handles_long_title(self, temp_dir):
        """긴 제목 폰트 크기 자동 조절."""
        from image.thumbnail import add_text_overlay

        from PIL import Image
        img = Image.new("RGB", (1024, 1024), color="red")
        img_path = temp_dir / "source.jpg"
        img.save(img_path)

        long_title = "이것은 매우 긴 제목으로 50자가 넘어가는 경우 폰트 크기가 자동으로 조절되어야 합니다"
        result = add_text_overlay(img_path, long_title)

        assert result.exists()

    def test_add_text_overlay_strips_thumb_prefix(self, temp_dir):
        """이미 thumb_ 프리픽스 있는 파일명 중복 방지."""
        from image.thumbnail import add_text_overlay

        from PIL import Image
        img = Image.new("RGB", (1024, 1024), color="green")
        img_path = temp_dir / "thumb_already_prefixed.jpg"
        img.save(img_path)

        result = add_text_overlay(img_path, "Title")
        assert result.name.count("thumb_") == 1  # 중복 없음

    @patch("image.thumbnail.UnsplashProvider.search")
    @patch("image.thumbnail.UnsplashProvider.download")
    def test_generate_thumbnail_unsplash_success(
        self, mock_download, mock_search, temp_dir, monkeypatch
    ):
        """Unsplash 성공 시 썸네일 생성."""
        from image.thumbnail import generate_thumbnail

        monkeypatch.setenv("UNSPLASH_ACCESS_KEY", "test-key")

        mock_search.return_value = [
            {"id": "abc123", "url_raw": "https://unsplash.com/photo.jpg", "author": "Test"}
        ]
        mock_download.return_value = temp_dir / "thumb_unsplash_abc123.jpg"
        (temp_dir / "thumb_unsplash_abc123.jpg").write_bytes(b"fake")

        with patch("image.thumbnail.add_text_overlay") as mock_overlay:
            mock_overlay.return_value = temp_dir / "thumb_final.webp"
            (temp_dir / "thumb_final.webp").write_bytes(b"fake")

            result = generate_thumbnail("Test Title", "test keyword", "test-slug")
            assert result is not None
            path, source = result
            assert source == "unsplash"

    @patch("image.thumbnail.UnsplashProvider.search", return_value=[])
    @patch("image.thumbnail.PexelsProvider.search")
    @patch("image.thumbnail.PexelsProvider.download")
    def test_generate_thumbnail_fallback_to_pexels(
        self, mock_download, mock_search, mock_unsplash, temp_dir, monkeypatch
    ):
        """Unsplash 실패 시 Pexels 폴백."""
        from image.thumbnail import generate_thumbnail

        monkeypatch.setenv("UNSPLASH_ACCESS_KEY", "test")
        monkeypatch.setenv("PEXELS_API_KEY", "test")

        mock_search.return_value = [
            {"id": "xyz789", "url": "https://pexels.com/photo.jpg", "author": "Test"}
        ]
        mock_download.return_value = temp_dir / "thumb_pexels_xyz789.jpg"
        (temp_dir / "thumb_pexels_xyz789.jpg").write_bytes(b"fake")

        with patch("image.thumbnail.add_text_overlay") as mock_overlay:
            mock_overlay.return_value = temp_dir / "thumb_final.webp"
            (temp_dir / "thumb_final.webp").write_bytes(b"fake")

            result = generate_thumbnail("Title", "keyword", "slug")
            assert result is not None
            _, source = result
            assert source == "pexels"

    @patch("image.thumbnail.UnsplashProvider.search", return_value=[])
    @patch("image.thumbnail.PexelsProvider.search", return_value=[])
    @patch("image.thumbnail._pollinations_fallback")
    def test_generate_thumbnail_fallback_to_pollinations(
        self, mock_pollinations, mock_pexels, mock_unsplash, temp_dir, monkeypatch
    ):
        """Pexels 실패 시 Pollinations 폴백."""
        from image.thumbnail import generate_thumbnail

        monkeypatch.setenv("UNSPLASH_ACCESS_KEY", "test")
        monkeypatch.setenv("PEXELS_API_KEY", "test")

        mock_pollinations.return_value = temp_dir / "thumb_pollinations.webp"
        (temp_dir / "thumb_pollinations.webp").write_bytes(b"fake")

        with patch("image.thumbnail.add_text_overlay") as mock_overlay:
            mock_overlay.return_value = temp_dir / "thumb_final.webp"
            (temp_dir / "thumb_final.webp").write_bytes(b"fake")

            result = generate_thumbnail("Title", "keyword", "slug")
            assert result is not None
            _, source = result
            assert source == "pollinations"

    def test_generate_thumbnail_idempotent(self, temp_dir, monkeypatch):
        """이미 파일 존재 시 재생성 안 함 (멱등성)."""
        from image.thumbnail import generate_thumbnail

        expected = temp_dir / "output" / "images" / "thumb_existing-slug.webp"
        expected.parent.mkdir(parents=True, exist_ok=True)
        expected.write_bytes(b"existing")

        monkeypatch.chdir(temp_dir)
        monkeypatch.setenv("UNSPLASH_ACCESS_KEY", "test")

        with patch("image.thumbnail.UnsplashProvider.search") as mock_search:
            result = generate_thumbnail("Title", "keyword", "existing-slug")
            assert result[0].name == expected.name
            mock_search.assert_not_called()  # API 호출 안 함


class TestPollinationsClient:
    """image/pollinations_client.py 테스트."""

    @patch("image.pollinations_client.urllib.request.urlopen")
    def test_generate_image_returns_url(self, mock_urlopen):
        """이미지 생성 성공 → Result.ok + 로컬 파일 저장."""
        from image.pollinations_client import generate_image
        from PIL import Image
        import io

        img = Image.new("RGB", (200, 200))
        buf = io.BytesIO()
        img.save(buf, "JPEG")
        valid_jpeg = buf.getvalue()

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = valid_jpeg
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = generate_image("test prompt", slug="test-slug")

        assert result.ok
        assert isinstance(result.value, Path)
        assert result.value.exists()
        assert "test-slug" in result.value.name
        req = mock_urlopen.call_args[0][0]
        assert "image.pollinations.ai" in req.full_url
        assert "width=1024" in req.full_url
        assert "model=flux" in req.full_url

    @patch("image.pollinations_client.urllib.request.urlopen")
    def test_generate_image_handles_error(self, mock_urlopen):
        """URL 접근 실패 시 Result.failure 반환."""
        from image.pollinations_client import generate_image

        mock_urlopen.side_effect = Exception("Network error")

        result = generate_image("test prompt", slug="test")
        assert not result.ok
        assert result.error is not None
        assert "Network error" in result.error.message
        mock_urlopen.assert_called()


class TestPromptBuilder:
    """image/prompt_builder.py 테스트."""

    def test_build_full_prompt_returns_english(self):
        """한국어 주제 → 영어 프롬프트 조립 (string concat, no AI call)."""
        from image.prompt_builder import build_full_prompt

        prompt = build_full_prompt("산 일몰 풍경", "rotcha", chain_type="depth", step=1)

        assert isinstance(prompt, str)
        assert len(prompt) > 10
        # rotcha style prompt contains English keywords
        assert "k-pop" in prompt
        assert "step 1 of depth chain" in prompt

    def test_get_image_style_for_blog(self):
        """블로그별 이미지 스타일 반환."""
        from image.prompt_builder import get_image_style_for_blog

        styles = {
            "rotcha": get_image_style_for_blog("rotcha"),
            "infohot": get_image_style_for_blog("infohot"),
            "techpawz": get_image_style_for_blog("techpawz"),
        }

        for blog, style in styles.items():
            assert isinstance(style, str)
            assert len(style) > 0

    def test_get_aspect_ratio(self):
        """종횡비 반환."""
        from image.prompt_builder import get_aspect_ratio

        assert get_aspect_ratio("rotcha") == (1024, 1024)   # known blog key → 1:1
        assert get_aspect_ratio("unknown") == (1200, 675)  # unknown key → default


class TestImageInjector:
    """image/injector.py 테스트."""

    @patch("image.injector._find_image_file", return_value=Path("output/images/thumb_test-slug.webp"))
    def test_inject_images_into_draft_adds_thumbnail_frontmatter(self, mock_find):
        """이미지 존재 시 <!--todo:image--> 마커 → Hugo figure shortcode 치환."""
        from image.injector import inject_images_into_draft

        draft = """---
title: "Test Post"
draft: true
---
<!--todo:image-->

## Content

Body text."""

        result = inject_images_into_draft(draft, "test-slug", "rotcha", 1, "Test Title")

        assert "{{< figure" in result
        assert "/images/thumb_test-slug.webp" in result
        assert "<!--todo:image-->" not in result

    @patch("image.injector._find_image_file", return_value=Path("output/images/thumb_test-slug.webp"))
    def test_inject_images_into_draft_adds_content_image_marker(self, mock_find):
        """이미지 존재 시 <!--todo:image--> 마커 → Hugo figure shortcode로 치환."""
        from image.injector import inject_images_into_draft

        draft = """---
title: "Test"
draft: true
---

## First H2

<!--todo:image-->

Content.

## Second H2

More content."""

        result = inject_images_into_draft(draft, "test-slug", "rotcha", 1, "Test Title")

        assert "{{< figure" in result
        assert "<!--todo:image-->" not in result
        # Figure should appear before ## Second H2 (after ## First H2)
        fig_idx = result.index("{{< figure")
        h2_idx = result.index("## First H2")
        assert fig_idx > h2_idx

    def test_inject_images_into_draft_preserves_frontmatter(self):
        """기존 frontmatter 필드 보존."""
        from image.injector import inject_images_into_draft

        draft = """---
title: "Original Title"
description: "Original desc"
tags: ["태그1", "태그2"]
categories: ["카테고리"]
draft: true
---

Body."""

        result = inject_images_into_draft(draft, "slug", "rotcha", 1, "Title")

        assert "title: \"Original Title\"" in result
        assert "description: \"Original desc\"" in result
        assert 'tags: ["태그1", "태그2"]' in result
        assert 'categories: ["카테고리"]' in result

    @patch("image.injector._find_image_file", return_value=None)
    def test_inject_images_handles_missing_frontmatter(self, mock_find):
        """frontmatter 없고 이미지도 없으면 draft 그대로 반환."""
        from image.injector import inject_images_into_draft

        draft = "Just body content without frontmatter."

        result = inject_images_into_draft(draft, "slug", "rotcha", 1, "Title")

        assert result == draft
        assert "body content" in result


class TestImagePackageInit:
    """image/__init__.py 익스포트 테스트."""

    def test_exports_expected_functions(self):
        """필요한 함수들이 익스포트됨."""
        import image

        assert hasattr(image, "generate_image")
        assert hasattr(image, "build_full_prompt")
        assert hasattr(image, "inject_images_into_draft")
        assert hasattr(image, "generate_thumbnail")
        assert hasattr(image, "add_text_overlay")


class TestKreaClient:
    """image/krea_client.py 테스트 (optional)."""

    @patch("image.krea_client.requests.post")
    @patch("image.krea_client.requests.get")
    def test_generate_image_polls_until_complete(self, mock_get, mock_post):
        """비동기 작업 완료까지 폴링 → krea_{slug}.jpg 저장."""
        from image.krea_client import generate_image

        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"job_id": "job-123"},
        )
        mock_get.side_effect = [
            MagicMock(status_code=200, json=lambda: {"status": "processing", "id": "job-123"}),
            MagicMock(status_code=200, json=lambda: {"status": "completed", "result": {"urls": ["https://krea.ai/result.jpg"]}, "id": "job-123"}),
            MagicMock(status_code=200, content=b"fake_image_bytes", raise_for_status=lambda: None),
        ]

        with patch("time.sleep", return_value=None):
            result = generate_image("test prompt", slug="test")
            assert result is not None
            assert result.name == "krea_test.jpg"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])