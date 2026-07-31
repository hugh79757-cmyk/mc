"""
base_provider.py — 이미지 제공자 공통 베이스 클래스 (Phase 26 W3)

모든 이미지 제공자(Unsplash/Pexels 등)가 구현해야 하는 인터페이스를 정의한다.
- fetch: 키워드 기반 이미지 검색/획득 (네트워크 I/O 포함 가능)
- validate: fetch 결과가 유효한 이미지인지 검증

구체 제공자(03-02 에서 UnsplashProvider/PexelsProvider 를 이 인터페이스로
적응)는 이 클래스를 상속해 두 추상 메서드를 모두 구현해야 한다.

T-26-21 (Denial of Service): fetch 는 timeout 파라미터를 지원해
행잉(hanging) 연결을 방지한다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from .cache_manager import CacheManager


class BaseImageProvider(ABC):
    """이미지 제공자 공통 인터페이스 (추상 베이스).

    클래스 속성:
        shared_cache: 제공자 인스턴스들이 공유하는 모듈 레벨 LRU+TTL 캐시.
            (image.cache_manager.CacheManager 싱글톤)

    구현 규칙:
        - fetch 와 validate 를 반드시 구현해야 인스턴스화할 수 있다.
        - fetch 는 네트워크 실패/무결과 시 None 을 반환하고 예외를
          삼키지 않되, 호출자가 None 으로 fallback 하도록 한다.
        - validate 는 fetch 결과가 다운로드 가능한 유효 이미지인지
          검증한다 (url/파일 존재, id 필수 필드 등).
    """

    shared_cache: CacheManager = CacheManager.get_shared()

    @abstractmethod
    def fetch(self, keyword: str, timeout: float = 30.0) -> Optional[dict]:
        """키워드로 이미지 메타데이터를 검색/획득한다.

        Args:
            keyword: 검색 키워드.
            timeout: 네트워크 요청 타임아웃(초). T-26-21: 행잉 연결 방지.

        Returns:
            이미지 메타데이터 dict (예: {"id": ..., "url": ..., "width": ...})
            또는 결과 없음/실패 시 None.
        """
        raise NotImplementedError

    @abstractmethod
    def validate(self, result: Any) -> bool:
        """fetch 결과가 유효한 이미지 메타데이터인지 검증한다.

        Args:
            result: fetch 가 반환한 메타데이터 (dict 또는 None).

        Returns:
            유효한 이미지면 True, 아니면 False.
        """
        raise NotImplementedError
