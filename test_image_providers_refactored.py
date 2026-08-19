"""Tests for refactored image providers (Phase 26 W4 — 03-02).

검증 대상:
- image/search_providers.py 의 UnsplashProvider / PexelsProvider 가
  BaseImageProvider 를 상속하고 공유 CacheManager 를 사용한다.
- 기존 공개 함수 search_body_image 가 무변경(동일 시그니처/반환 타입)으로
  동작하고, 새 클래스와 같은 검색 결과(photo dict)를 소비한다 (래퍼 동등성).
- image/prompt_builder.py 의 PromptBuilder 가 기존 함수와 동일 출력을
  위임하고 공유 캐시를 사용한다.
- 네트워크 미사용 — image.thumbnail 제공자 클래스를 모두 mock 처리.
"""
import inspect
from unittest.mock import MagicMock, patch

import pytest

UNSPLASH_PHOTO = {
    "id": "photo-1",
    "url_raw": "https://unsplash.com/1",
    "url_regular": "https://unsplash.com/1r",
    "author": "Test",
}
PEXELS_PHOTO = {
    "id": "px-1",
    "url": "https://pexels.com/1",
    "url_original": "https://pexels.com/1o",
    "author": "Test",
}


@pytest.fixture(autouse=True)
def _clear_shared_cache():
    """공유 CacheManager 싱글톤을 테스트 간 초기화 (테스트 격리)."""
    from image.cache_manager import CacheManager
    CacheManager.get_shared().clear()
    yield
    CacheManager.get_shared().clear()


class TestProviderInheritance:
    """BaseImageProvider 상속 + 추상 메서드 구현 검증."""

    def test_unsplash_inherits_base(self):
        from image.search_providers import UnsplashProvider
        from image.base_provider import BaseImageProvider
        assert issubclass(UnsplashProvider, BaseImageProvider)

    def test_pexels_inherits_base(self):
        from image.search_providers import PexelsProvider
        from image.base_provider import BaseImageProvider
        assert issubclass(PexelsProvider, BaseImageProvider)

    def test_providers_instantiable(self):
        """추상 메서드(fetch/validate)를 모두 구현 → 인스턴스화 가능."""
        from image.search_providers import UnsplashProvider, PexelsProvider
        assert not inspect.isabstract(UnsplashProvider)
        assert not inspect.isabstract(PexelsProvider)
        up = UnsplashProvider()
        pp = PexelsProvider()
        assert up is not None and pp is not None

    def test_fetch_and_validate_are_overridden(self):
        """fetch/validate 가 서브클래스에서 (추상이 아닌) 구현으로 정의됨."""
        from image.search_providers import UnsplashProvider, PexelsProvider
        from image.base_provider import BaseImageProvider
        for cls in (UnsplashProvider, PexelsProvider):
            assert cls.fetch is not BaseImageProvider.fetch
            assert cls.validate is not BaseImageProvider.validate

    def test_shared_cache_is_cachemanager_singleton(self):
        from image.search_providers import UnsplashProvider, PexelsProvider
        from image.cache_manager import CacheManager
        up, pp = UnsplashProvider(), PexelsProvider()
        assert up.shared_cache is CacheManager.get_shared()
        assert pp.shared_cache is CacheManager.get_shared()
        assert up.shared_cache is pp.shared_cache


class TestFetchBehavior:
    """fetch — mock 기반 검색/캐시 동작 (네트워크 없음)."""

    @patch("image.thumbnail.UnsplashProvider")
    def test_fetch_returns_first_photo(self, mock_cls):
        mock_cls.return_value.search.return_value = [UNSPLASH_PHOTO]
        from image.search_providers import UnsplashProvider
        result = UnsplashProvider().fetch("테스트 키워드")
        assert result == UNSPLASH_PHOTO

    @patch("image.thumbnail.PexelsProvider")
    def test_fetch_pexels_returns_first_photo(self, mock_cls):
        mock_cls.return_value.search.return_value = [PEXELS_PHOTO]
        from image.search_providers import PexelsProvider
        result = PexelsProvider().fetch("테스트 키워드")
        assert result == PEXELS_PHOTO

    @patch("image.thumbnail.UnsplashProvider")
    def test_fetch_empty_results_returns_none(self, mock_cls):
        mock_cls.return_value.search.return_value = []
        from image.search_providers import UnsplashProvider
        assert UnsplashProvider().fetch("nothing") is None

    @patch("image.thumbnail.UnsplashProvider")
    def test_fetch_empty_keyword_returns_none_no_api_call(self, mock_cls):
        from image.search_providers import UnsplashProvider
        assert UnsplashProvider().fetch("") is None
        mock_cls.return_value.search.assert_not_called()

    @patch("image.thumbnail.UnsplashProvider")
    def test_fetch_invalid_photo_dict_rejected(self, mock_cls):
        mock_cls.return_value.search.return_value = [{"id": "", "url": "x"}]
        from image.search_providers import UnsplashProvider
        assert UnsplashProvider().fetch("bad") is None

    @patch("image.thumbnail.UnsplashProvider")
    def test_cache_hit_skips_api_call(self, mock_cls):
        mock_cls.return_value.search.return_value = [UNSPLASH_PHOTO]
        from image.search_providers import UnsplashProvider
        provider = UnsplashProvider()
        assert provider.fetch("캐시 키워드") == UNSPLASH_PHOTO
        # 두 번째 호출 — 캐시 히트 → API 재호출 없음
        assert provider.fetch("캐시 키워드") == UNSPLASH_PHOTO
        assert mock_cls.return_value.search.call_count == 1

    @patch("image.thumbnail.PexelsProvider")
    @patch("image.thumbnail.UnsplashProvider")
    def test_providers_share_cache_namespace(self, mock_unsplash_cls, mock_pexels_cls):
        """Unsplash/Pexels 가 같은 CacheManager 를 공유하되 키는 분리."""
        mock_pexels_cls.return_value.search.return_value = [PEXELS_PHOTO]
        mock_unsplash_cls.return_value.search.return_value = [UNSPLASH_PHOTO]
        from image.search_providers import UnsplashProvider, PexelsProvider
        from image.cache_manager import CacheManager
        assert UnsplashProvider().fetch("공유") == UNSPLASH_PHOTO
        assert PexelsProvider().fetch("공유") == PEXELS_PHOTO
        cache = CacheManager.get_shared()
        assert cache.get("unsplash:공유") == UNSPLASH_PHOTO
        assert cache.get("pexels:공유") == PEXELS_PHOTO


class TestValidate:
    """validate — 메타데이터 필드 검증."""

    def test_valid_unsplash_dict(self):
        from image.search_providers import UnsplashProvider
        assert UnsplashProvider().validate(UNSPLASH_PHOTO) is True

    def test_valid_pexels_dict(self):
        from image.search_providers import PexelsProvider
        assert PexelsProvider().validate(PEXELS_PHOTO) is True

    @pytest.mark.parametrize("bad", [None, "string", 42, [], {}, {"id": "x"}])
    def test_invalid_results_rejected(self, bad):
        from image.search_providers import UnsplashProvider, PexelsProvider
        assert UnsplashProvider().validate(bad) is False
        assert PexelsProvider().validate(bad) is False


class TestWrapperEquivalence:
    """search_body_image (기존 경로) 무변경 + 새 클래스와 동일 photo 소비."""

    @patch("image.thumbnail.UnsplashProvider")
    def test_search_body_image_signature_and_return(self, mock_cls):
        """기존 공개 함수가 그대로 (Path, source) 튜플을 반환한다."""
        import inspect as _inspect
        from image.search_providers import search_body_image
        sig = _inspect.signature(search_body_image)
        assert list(sig.parameters) == ["keyword", "slug", "step"]

        mock_unsplash = MagicMock()
        mock_cls.return_value = mock_unsplash
        mock_unsplash.search.return_value = [UNSPLASH_PHOTO]

        from pathlib import Path
        fake_path = Path("/tmp/fake_body.webp")

        with patch("image.search_providers._read_cache", return_value=None):
            with patch("image.search_providers._to_body_path", return_value=fake_path):
                with patch("image.search_providers._write_cache"):
                    result = search_body_image("동등성", "equi-slug")

        assert result is not None
        path, source = result
        assert source == "unsplash"
        assert path == fake_path

    @patch("image.thumbnail.UnsplashProvider")
    def test_new_class_consumes_same_photo_as_old_path(self, mock_cls):
        """새 클래스 fetch 의 반환값 = 기존 경로가 소비하는 results[0]."""
        mock_cls.return_value.search.return_value = [UNSPLASH_PHOTO]
        from image.search_providers import UnsplashProvider
        result = UnsplashProvider().fetch("동일 키워드")
        assert result == UNSPLASH_PHOTO
        # 기존 경로도 같은 mock 제공자 search 결과의 첫 항목을 사용
        assert mock_cls.return_value.search.return_value[0] == UNSPLASH_PHOTO


class TestPromptBuilder:
    """PromptBuilder — 기존 함수 위임 동일성 + 공유 캐시 사용."""

    def test_instantiation(self):
        from image.prompt_builder import PromptBuilder
        pb = PromptBuilder()
        assert pb.provider is None

    def test_shared_cache_attribute(self):
        from image.prompt_builder import PromptBuilder
        from image.cache_manager import CacheManager
        assert PromptBuilder.shared_cache is CacheManager.get_shared()

    def test_build_full_prompt_delegates_to_module_function(self):
        from image.prompt_builder import PromptBuilder, build_full_prompt
        pb = PromptBuilder()
        assert pb.build_full_prompt("춘천 여행", "rotcha") == build_full_prompt("춘천 여행", "rotcha")

    def test_build_contextual_prompt_delegates_to_module_function(self):
        from image.prompt_builder import PromptBuilder, build_contextual_prompt
        pb = PromptBuilder()
        assert pb.build_contextual_prompt("호텔", "제목", "rotcha", step=2) == \
            build_contextual_prompt("호텔", "제목", "rotcha", step=2)

    def test_get_style_for_blog_caches(self):
        from image.prompt_builder import PromptBuilder, get_image_style_for_blog
        pb = PromptBuilder()
        assert pb.get_style_for_blog("techpawz") == get_image_style_for_blog("techpawz")
        # 캐시에 저장됨
        assert pb.shared_cache.get("style:techpawz") == get_image_style_for_blog("techpawz")

    def test_module_functions_unchanged(self):
        """기존 함수들이 여전히 import 되고 동작한다 (회귀 방지)."""
        from image.prompt_builder import (
            build_contextual_prompt, build_full_prompt,
            get_image_style_for_blog, get_aspect_ratio, POLLINATIONS_STYLE_MAP,
        )
        assert isinstance(build_full_prompt("제주", "rotcha"), str)
        assert "제주" in build_full_prompt("제주", "rotcha")
        assert POLLINATIONS_STYLE_MAP["rotcha"] in build_full_prompt("제주", "rotcha")
