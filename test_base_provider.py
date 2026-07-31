"""
test_base_provider.py — BaseImageProvider 추상 베이스 테스트 (Phase 26 W3)

핵심 계약:
- 추상 클래스는 직접 인스턴스화할 수 없다 (TypeError)
- 두 추상 메서드(fetch/validate) 중 하나만 구현하면 여전히 추상
- 둘 다 구현해야 인스턴스화 가능
- 공유 캐시(CacheManager 싱글톤)가 제공됨
"""

import pytest

from image.base_provider import BaseImageProvider
from image.cache_manager import CacheManager


def test_cannot_instantiate_abstract():
    """추상 메서드 미구현 상태에서는 인스턴스화 불가."""
    with pytest.raises(TypeError):
        BaseImageProvider()


def test_partial_subclass_still_abstract():
    """fetch 만 구현하면 validate 가 남아 여전히 추상."""
    class PartialProvider(BaseImageProvider):
        def fetch(self, keyword: str, timeout: float = 30.0):
            return None

    with pytest.raises(TypeError):
        PartialProvider()


def test_validate_only_subclass_still_abstract():
    """validate 만 구현하면 fetch 가 남아 여전히 추상."""
    class PartialProvider(BaseImageProvider):
        def validate(self, result) -> bool:
            return result is not None

    with pytest.raises(TypeError):
        PartialProvider()


def test_full_subclass_instantiable():
    """두 추상 메서드를 모두 구현하면 인스턴스화 가능 + 호출 동작."""
    class ConcreteProvider(BaseImageProvider):
        def fetch(self, keyword: str, timeout: float = 30.0):
            return {"id": "1", "url": f"https://img.example/{keyword}"}

        def validate(self, result) -> bool:
            return bool(result and result.get("url"))

    provider = ConcreteProvider()
    assert provider.fetch("로또") == {"id": "1", "url": "https://img.example/로또"}
    assert provider.validate(provider.fetch("로또")) is True
    assert provider.validate(None) is False


def test_abstract_methods_defined():
    """추상 메서드가 인터페이스에 정의되어 있고 NotImplementedError 를 던진다."""
    assert BaseImageProvider.fetch.__isabstractmethod__ is True
    assert BaseImageProvider.validate.__isabstractmethod__ is True
    with pytest.raises(NotImplementedError):
        BaseImageProvider.fetch(BaseImageProvider, "키워드")
    with pytest.raises(NotImplementedError):
        BaseImageProvider.validate(BaseImageProvider, None)


def test_fetch_has_timeout_param():
    """T-26-21: fetch 는 timeout 파라미터를 기본 30초로 지원."""
    import inspect
    sig = inspect.signature(BaseImageProvider.fetch)
    params = sig.parameters
    assert "timeout" in params
    assert params["timeout"].default == 30.0


def test_shared_cache_is_cachemanager():
    """클래스 속성 shared_cache 는 공유 CacheManager 싱글톤."""
    assert isinstance(BaseImageProvider.shared_cache, CacheManager)
    assert BaseImageProvider.shared_cache is CacheManager.get_shared()


def test_shared_cache_usable_from_subclass():
    """서브클래스에서 공유 캐시를 그대로 사용할 수 있다."""
    class ConcreteProvider(BaseImageProvider):
        def fetch(self, keyword: str, timeout: float = 30.0):
            return {"id": "1"}

        def validate(self, result) -> bool:
            return bool(result)

    cache = ConcreteProvider.shared_cache
    cache.set("shared-test-key", {"v": 1}, ttl=60)
    assert cache.get("shared-test-key") == {"v": 1}
    cache.clear()
