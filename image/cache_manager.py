"""
cache_manager.py — 이미지 캐시 매니저 (LRU + TTL) (Phase 26 W3)

여러 이미지 제공자 인스턴스가 공유할 수 있는 인메모리 캐시.
LRU(Least Recently Used) 퇴출 + TTL(Time-To-Live) 만료를 지원한다.

T-26-20 (Information Disclosure): 캐시 값은 이미지 메타데이터/로컬 파일 경로
등 비민감 데이터만 저장하는 것을 원칙으로 한다 (API 키/토큰/개인정보 저장 금지).
clear() 로 캐시 전체를 즉시 비울 수 있다.

사용법:
    cache = CacheManager(maxsize=128, ttl=3600)   # 제공자별 개별 인스턴스
    cache = CacheManager.get_shared()             # 모듈 레벨 공유 싱글톤
    cache.set("keyword", {"id": "x", "path": "/tmp/a.webp"})
    result = cache.get("keyword")                 # 히트 or None (TTL 만료 시 미스)
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Any, Optional


class CacheManager:
    """LRU + TTL 인메모리 캐시. 스레드 세이프.

    내부 저장 형태: OrderedDict[key -> (timestamp, value, expires_at)].
    - timestamp: time.monotonic() 기준 저장 시각 (시계 변경 영향 없음)
    - expires_at: 절대 만료 시각 (개별 ttl 반영)
    - 히트 시 move_to_end 로 LRU 순서 갱신
    - maxsize 초과 시 가장 오래 사용되지 않은 항목(LRU)부터 퇴출
    """

    _shared_instance: Optional["CacheManager"] = None
    _shared_lock = threading.Lock()

    def __init__(self, maxsize: int = 128, ttl: float = 3600.0):
        """캐시 생성.

        Args:
            maxsize: 최대 보관 항목 수. 초과 시 LRU 퇴출 (1 미만이면 1로 상향).
            ttl: 기본 만료 시간(초). set() 에서 개별 ttl 로 오버라이드 가능.
        """
        self.maxsize = max(1, int(maxsize))
        self.ttl = max(0.0, float(ttl))
        self._cache: "OrderedDict[str, tuple[float, Any, float]]" = OrderedDict()
        self._lock = threading.Lock()

    @classmethod
    def get_shared(cls, maxsize: int = 128, ttl: float = 3600.0) -> "CacheManager":
        """모듈 레벨 공유 싱글톤 — 여러 제공자 인스턴스가 같은 캐시를 공유.

        첫 호출 시 생성된 인스턴스가 이후 호출에서 그대로 반환된다.
        """
        with cls._shared_lock:
            if cls._shared_instance is None:
                cls._shared_instance = cls(maxsize=maxsize, ttl=ttl)
            return cls._shared_instance

    @staticmethod
    def _normalize_key(key: str) -> str:
        """키는 str 만 허용 (타입 오염 방지: int/None 등으로 인한 충돌 차단)."""
        if not isinstance(key, str):
            raise TypeError(f"cache key must be str, got {type(key).__name__}: {key!r}")
        return key

    # ── 핵심 API ─────────────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        """키 조회.

        Returns:
            히트 시 값, 미스 또는 TTL 만료 시 default (기본 None).
            히트하면 LRU 순서가 최신(MRU)으로 갱신된다.
        """
        k = self._normalize_key(key)
        with self._lock:
            item = self._cache.get(k)
            if item is None:
                return default
            ts, value, expires_at = item
            if time.monotonic() > expires_at:
                del self._cache[k]
                return default
            self._cache.move_to_end(k)
            return value

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """키-값 저장.

        Args:
            key: str 키.
            value: 캐시 값 (비민감 데이터만 — T-26-20).
            ttl: 개별 만료 시간(초). None 이면 생성자 기본 ttl 사용.
        """
        k = self._normalize_key(key)
        item_ttl = self.ttl if ttl is None else max(0.0, float(ttl))
        now = time.monotonic()
        with self._lock:
            self._cache[k] = (now, value, now + item_ttl)
            self._cache.move_to_end(k)
            # maxsize 초과 → LRU 퇴출
            while len(self._cache) > self.maxsize:
                self._cache.popitem(last=False)

    def clear(self) -> None:
        """캐시 전체 비우기 (T-26-20: 민감 데이터 잔존 방지)."""
        with self._lock:
            self._cache.clear()

    def prune(self) -> int:
        """만료된 항목을 제거하고 제거한 개수를 반환.

        get() 은 만료 항목을 지연(lazy) 제거하지만, prune() 은 캐시 전체를
        한 번에 정리한다 (주기적 유지보수용).
        """
        now = time.monotonic()
        removed = 0
        with self._lock:
            expired = [k for k, (_, _, expires_at) in self._cache.items() if now > expires_at]
            for k in expired:
                del self._cache[k]
                removed += 1
        return removed

    # ── 유틸 ─────────────────────────────────────────────────

    def __len__(self) -> int:
        with self._lock:
            return len(self._cache)

    def keys(self) -> list:
        """저장 키 목록 (LRU 오래된 순서)."""
        with self._lock:
            return list(self._cache.keys())
