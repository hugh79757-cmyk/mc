"""
test_cache_manager.py — CacheManager LRU + TTL 캐시 테스트 (Phase 26 W3)

검증 항목: hit/miss, LRU 퇴출 순서, get 으로 인한 LRU 갱신, TTL 만료,
개별 ttl, clear, prune, 공유 싱글톤, 키 타입 검증.
"""

import time

import pytest

from image.cache_manager import CacheManager


@pytest.fixture()
def cache() -> CacheManager:
    return CacheManager(maxsize=3, ttl=60.0)


# ── 기본 hit/miss ────────────────────────────────────────────

def test_set_get_hit(cache):
    cache.set("a", {"path": "/tmp/a.webp"})
    assert cache.get("a") == {"path": "/tmp/a.webp"}


def test_get_miss_returns_default(cache):
    assert cache.get("nope") is None
    assert cache.get("nope", "default") == "default"


def test_get_miss_after_clear(cache):
    cache.set("a", 1)
    cache.clear()
    assert cache.get("a") is None


def test_overwrite_same_key(cache):
    cache.set("a", 1)
    cache.set("a", 2)
    assert cache.get("a") == 2
    assert len(cache) == 1


def test_len_and_keys(cache):
    assert len(cache) == 0
    cache.set("a", 1)
    cache.set("b", 2)
    assert len(cache) == 2
    assert set(cache.keys()) == {"a", "b"}


# ── LRU 퇴출 ─────────────────────────────────────────────────

def test_lru_eviction_oldest_first(cache):
    """maxsize=3, 4번째 set 시 가장 오래된 항목부터 퇴출."""
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)
    cache.set("d", 4)  # a 가 LRU → 퇴출
    assert cache.get("a") is None
    assert cache.get("b") == 2
    assert cache.get("c") == 3
    assert cache.get("d") == 4
    assert len(cache) == 3


def test_lru_get_refreshes_order(cache):
    """get 으로 접근한 항목은 MRU 가 되어 퇴출에서 제외된다."""
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)
    cache.get("a")  # a 를 최신(MRU)으로 갱신
    cache.set("d", 4)  # 이제 b 가 LRU → 퇴출
    assert cache.get("a") == 1
    assert cache.get("b") is None
    assert cache.get("c") == 3
    assert cache.get("d") == 4


def test_lru_overwrite_refreshes_order(cache):
    """같은 키 재set 도 MRU 갱신으로 취급."""
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)
    cache.set("a", 10)  # a 갱신 → MRU
    cache.set("d", 4)   # b 가 LRU → 퇴출
    assert cache.get("a") == 10
    assert cache.get("b") is None


def test_maxsize_min_one():
    """maxsize 가 1 미만이어도 최소 1로 동작 (0/음수 방어)."""
    c = CacheManager(maxsize=0)
    c.set("a", 1)
    c.set("b", 2)
    assert len(c) == 1
    assert c.get("a") is None
    assert c.get("b") == 2


# ── TTL 만료 ─────────────────────────────────────────────────

def test_ttl_expiry():
    c = CacheManager(ttl=0.1)
    c.set("a", 1)
    assert c.get("a") == 1
    time.sleep(0.15)
    assert c.get("a") is None  # TTL 만료 → 미스
    assert c.get("a", "expired") == "expired"


def test_ttl_individual_override():
    """set() 의 개별 ttl 은 기본 ttl 을 오버라이드."""
    c = CacheManager(ttl=60.0)
    c.set("short", 1, ttl=0.1)
    c.set("long", 2, ttl=60.0)
    time.sleep(0.15)
    assert c.get("short") is None  # 개별 ttl 만료
    assert c.get("long") == 2      # 기본 ttl 유지


def test_ttl_no_expiry_before_time():
    c = CacheManager(ttl=10.0)
    c.set("a", 1)
    assert c.get("a") == 1  # 만료 전 히트


def test_prune_removes_expired_only():
    c = CacheManager(ttl=0.1)
    c.set("expired1", 1)
    c.set("expired2", 2)
    c.set("live", 3, ttl=60.0)
    time.sleep(0.15)
    assert c.prune() == 2
    assert c.get("live") == 3
    assert len(c) == 1


# ── clear / 공유 싱글톤 / 키 검증 ─────────────────────────────

def test_clear_empties_cache(cache):
    cache.set("a", 1)
    cache.set("b", 2)
    cache.clear()
    assert len(cache) == 0
    assert cache.get("a") is None


def test_clear_with_shared_singleton():
    """T-26-20: 공유 캐시도 clear() 로 즉시 비울 수 있다."""
    shared = CacheManager.get_shared()
    shared.clear()
    shared.set("s", 1)
    assert shared.get("s") == 1
    shared.clear()
    assert shared.get("s") is None
    assert len(shared) == 0


def test_shared_singleton_same_instance():
    assert CacheManager.get_shared() is CacheManager.get_shared()
    assert CacheManager.get_shared() is CacheManager._shared_instance


def test_shared_singleton_independent_from_instances(cache):
    """개별 인스턴스는 싱글톤과 독립적이다."""
    shared = CacheManager.get_shared()
    cache.set("x", "instance")
    assert shared.get("x") is None


def test_non_str_key_rejected(cache):
    with pytest.raises(TypeError):
        cache.get(123)
    with pytest.raises(TypeError):
        cache.set(None, "v")
    with pytest.raises(TypeError):
        cache.set(["list"], "v")


def test_get_does_not_leak_expired_items(cache):
    """만료 항목은 get 시 지연 제거되어 keys() 에 남지 않는다."""
    c = CacheManager(ttl=0.1)
    c.set("a", 1)
    time.sleep(0.15)
    assert c.get("a") is None
    assert c.keys() == []
