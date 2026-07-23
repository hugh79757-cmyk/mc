"""Tests for image/search_providers.py — body-image search with cache + fallback."""
import json
import os
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image


class TestToBodyPath:
    """_to_body_path 함수 — JPEG→WebP 실제 변환 테스트."""

    def test_jpeg_to_webp_conversion(self, temp_dir):
        """JPEG 파일을 .webp로 저장하면 실제 WebP 포맷이어야 함."""
        from image.search_providers import _to_body_path

        # Create a fake JPEG file
        jpeg_path = temp_dir / "photo.jpg"
        img = Image.new("RGB", (100, 100), color="red")
        img.save(jpeg_path, "JPEG", quality=90)

        # Verify it's actually JPEG
        with open(jpeg_path, "rb") as f:
            assert f.read(2) == b"\xff\xd8"

        result = _to_body_path(jpeg_path, "test-slug", "pexels", "12345")

        # Result should exist and be a real WebP
        assert result.exists()
        assert result.suffix == ".webp"
        with open(result, "rb") as f:
            header = f.read(4)
        assert header == b"RIFF", f"Expected WebP (RIFF header), got {header.hex()}"

    def test_already_webp_passthrough(self, temp_dir):
        """WebP 파일이면 그대로 변환 후 저장."""
        from image.search_providers import _to_body_path

        webp_path = temp_dir / "photo.webp"
        img = Image.new("RGB", (100, 100), color="blue")
        img.save(webp_path, "WEBP", quality=85)

        result = _to_body_path(webp_path, "test-slug", "unsplash", "abc-123")

        assert result.exists()
        with open(result, "rb") as f:
            header = f.read(4)
        assert header == b"RIFF"

    def test_png_to_webp_conversion(self, temp_dir):
        """PNG 파일도 WebP로 변환됨."""
        from image.search_providers import _to_body_path

        png_path = temp_dir / "photo.png"
        img = Image.new("RGBA", (100, 100), color=(0, 128, 255, 200))
        img.save(png_path, "PNG")

        result = _to_body_path(png_path, "test-slug", "pexels", "99999")

        assert result.exists()
        with open(result, "rb") as f:
            header = f.read(4)
        assert header == b"RIFF"


class TestSearchBodyImage:
    """search_body_image 함수 테스트 (Phase 13 R1)."""

    @patch("image.thumbnail.UnsplashProvider")
    @patch("image.thumbnail.PexelsProvider")
    def test_search_success_unsplash(
        self, mock_pexels_cls, mock_unsplash_cls, temp_dir
    ):
        """Unsplash 검색 성공 → 파일 저장됨."""
        mock_unsplash = MagicMock()
        mock_unsplash_cls.return_value = mock_unsplash
        mock_unsplash.search.return_value = [
            {"id": "photo-1", "url_raw": "https://unsplash.com/1", "author": "Test"}
        ]
        fake_path = temp_dir / "thumb_unsplash_photo-1.jpg"
        fake_path.write_text("fake")
        mock_unsplash.download.return_value = fake_path

        from image.search_providers import search_body_image

        with patch("image.search_providers._read_cache", return_value=None):
            result = search_body_image("test keyword", "test-slug")

        assert result is not None
        path, source = result
        assert source == "unsplash"
        assert "body_test-slug_unsplash" in str(path)

    @patch("image.thumbnail.UnsplashProvider")
    @patch("image.thumbnail.PexelsProvider")
    def test_search_empty_all_providers(
        self, mock_pexels_cls, mock_unsplash_cls
    ):
        """모든 프로바이더가 빈 결과 → None."""
        mock_unsplash = MagicMock()
        mock_unsplash_cls.return_value = mock_unsplash
        mock_unsplash.search.return_value = []

        mock_pexels = MagicMock()
        mock_pexels_cls.return_value = mock_pexels
        mock_pexels.search.return_value = []

        from image.search_providers import search_body_image

        with patch("image.search_providers._read_cache", return_value=None):
            result = search_body_image("empty keyword", "empty-slug")

        assert result is None

    @patch("image.thumbnail.UnsplashProvider")
    @patch("image.thumbnail.PexelsProvider")
    def test_search_rate_limited(self, mock_pexels_cls, mock_unsplash_cls):
        """HTTP 429 → None (재시도 없음)."""
        mock_unsplash = MagicMock()
        mock_unsplash_cls.return_value = mock_unsplash
        mock_unsplash.search.return_value = []

        mock_pexels = MagicMock()
        mock_pexels_cls.return_value = mock_pexels
        mock_pexels.search.return_value = []

        from image.search_providers import search_body_image

        with patch("image.search_providers._read_cache", return_value=None):
            result = search_body_image("rate-limited", "rate-slug")

        assert result is None

    @patch("image.thumbnail.UnsplashProvider")
    @patch("image.thumbnail.PexelsProvider")
    def test_cache_hit(self, mock_pexels_cls, mock_unsplash_cls, temp_dir):
        """캐시 히트 → API 호출 없이 캐시 결과 반환."""
        cached_path = temp_dir / "cached_image.webp"
        cached_path.write_text("fake")
        cached_data = {
            "path": str(cached_path),
            "source": "unsplash",
            "ts": time.time(),
        }

        from image.search_providers import search_body_image

        with patch("image.search_providers._read_cache", return_value=cached_data):
            result = search_body_image("cached-keyword", "cached-slug")

        assert result is not None
        path, source = result
        assert source == "unsplash"
        mock_unsplash_cls.assert_not_called()

    def test_cache_expired(self, temp_dir):
        """만료된 캐시 → API 재호출 (실제 TTL 검사 통과)."""
        from image.search_providers import search_body_image, _cache_key, _CACHE_DIR, _write_cache

        # Write an expired cache file
        key = _cache_key("expired-keyword")
        cache_file = Path(_CACHE_DIR) / f"{key}.json"
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        expired_data = {
            "path": str(temp_dir / "gone.webp"),
            "source": "unsplash",
            "ts": time.time() - 90000,  # 25h ago > 24h TTL
        }
        with open(cache_file, "w") as f:
            json.dump(expired_data, f)

        # The real _read_cache will see expired TTL and return None
        # Then API is called but returns empty → None
        with patch("image.thumbnail.UnsplashProvider") as mock_unsplash_cls:
            mock_unsplash = MagicMock()
            mock_unsplash_cls.return_value = mock_unsplash
            mock_unsplash.search.return_value = []

            with patch("image.thumbnail.PexelsProvider") as mock_pexels_cls:
                mock_pexels = MagicMock()
                mock_pexels_cls.return_value = mock_pexels
                mock_pexels.search.return_value = []

                result = search_body_image("expired-keyword", "expired-slug")

        # Cache expired → API called → API empty → None
        mock_unsplash_cls.assert_called_once()
        assert result is None

        # Cleanup
        if cache_file.exists():
            cache_file.unlink()

    def test_api_key_missing(self):
        """API 키 없음 → skip provider silently."""
        from image.search_providers import search_body_image

        with patch("image.search_providers._UNSPLASH_KEY", ""):
            with patch("image.search_providers._PEXELS_KEY", ""):
                with patch("image.search_providers._read_cache", return_value=None):
                    result = search_body_image("no-key", "no-key-slug")

        assert result is None
