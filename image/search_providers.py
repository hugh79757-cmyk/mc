"""
search_providers.py — Body-image search from Unsplash/Pexels with 24h cache + Pollinations fallback

Used by the Hugo photo branch to find contextually relevant body images.
All failures return None — caller falls through to existing Pollinations path.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Optional

from url_utils import normalize_url  # noqa: F401 — URL 처리 단일 진실 공급원 (Phase 26)

# Phase 26 W4: BaseImageProvider 인터페이스 + 공유 CacheManager 적응 (03-02)
from .base_provider import BaseImageProvider

# ── Cache ──

_CACHE_DIR = "output/image_cache"
_CACHE_TTL = 86400  # 24 hours


def _cache_key(keyword: str) -> str:
    return hashlib.md5(keyword.encode()).hexdigest()


def _read_cache(key: str) -> dict | None:
    path = os.path.join(_CACHE_DIR, f"{key}.json")
    if os.path.exists(path):
        try:
            with open(path) as f:
                data = json.load(f)
            if time.time() - data.get("ts", 0) < _CACHE_TTL:
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return None


def _write_cache(key: str, result: dict):
    os.makedirs(_CACHE_DIR, exist_ok=True)
    result["ts"] = time.time()
    path = os.path.join(_CACHE_DIR, f"{key}.json")
    try:
        with open(path, "w") as f:
            json.dump(result, f)
    except OSError:
        pass


# ── API Keys (env only, no hardcoding) ──

_UNSPLASH_KEY = os.environ.get("UNSPLASH_ACCESS_KEY", "")
_PEXELS_KEY = os.environ.get("PEXELS_API_KEY", "")


# ── Main entry point ──

def search_body_image(keyword: str, slug: str, step: int = 1) -> Optional[tuple[Path, str]]:
    """
    Search for a body image via Unsplash -> Pexels.

    Args:
        keyword: Search keyword.
        slug: Post slug for filename.
        step: Chain step (1-based). Used for dedup offset into results.

    Returns:
        (path, source_name) tuple, or None if all providers failed.
        source_name: "unsplash" | "pexels"
    """
    cache_key = _cache_key(keyword)
    cached = _read_cache(cache_key)
    if cached:
        path_str = cached.get("path", "")
        source = cached.get("source", "")
        if path_str and os.path.exists(path_str):
            return (Path(path_str), source)

    # Dedup: 이전에 사용한 photo_id 회피
    _used_ids = set()
    try:
        from chain_db import get_used_photo_ids
        _used_ids = get_used_photo_ids(keyword)
    except Exception:
        pass  # DB 연결 실패 시 dedup 스킵

    # Try Unsplash first
    from image.thumbnail import UnsplashProvider

    provider = UnsplashProvider(_UNSPLASH_KEY)
    if results := provider.search(keyword):
        _fresh = [r for r in results if str(r.get("id", "")) not in _used_ids] or results
        photo = _fresh[min(step - 1, len(_fresh) - 1)]
        downloaded = provider.download(photo)
        if downloaded and downloaded.exists():
            body_path = _to_body_path(downloaded, slug, "unsplash", photo.get("id", "0"))
            _write_cache(cache_key, {"path": str(body_path), "source": "unsplash"})
            try:
                from chain_db import record_used_image
                record_used_image(keyword, photo.get("id", "0"), "unsplash")
            except Exception:
                pass
            return (body_path, "unsplash")

    # Fallback to Pexels
    from image.thumbnail import PexelsProvider

    provider = PexelsProvider(_PEXELS_KEY)
    if results := provider.search(keyword):
        _fresh = [r for r in results if str(r.get("id", "")) not in _used_ids] or results
        photo = _fresh[min(step - 1, len(_fresh) - 1)]
        downloaded = provider.download(photo)
        if downloaded and downloaded.exists():
            body_path = _to_body_path(downloaded, slug, "pexels", str(photo.get("id", "0")))
            _write_cache(cache_key, {"path": str(body_path), "source": "pexels"})
            try:
                from chain_db import record_used_image
                record_used_image(keyword, str(photo.get("id", "0")), "pexels")
            except Exception:
                pass
            return (body_path, "pexels")

    # All providers failed — cache the miss to avoid repeat calls
    _write_cache(cache_key, {"path": "", "source": ""})
    return None


# ── Helpers ──

def _to_body_path(downloaded: Path, slug: str, source: str, photo_id: str) -> Path:
    """Convert downloaded image to actual WebP and save as body_{slug}_{source}_{id}.webp."""
    IMAGE_DIR = Path("output/images")
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    safe_id = re.sub(r"[^a-zA-Z0-9_-]", "", photo_id)[:20] if photo_id else "0"
    dest = IMAGE_DIR / f"body_{slug}_{source}_{safe_id}.webp"
    try:
        from PIL import Image
        with Image.open(downloaded) as img:
            img.convert("RGB").save(dest, "WEBP", quality=85)
        return dest
    except Exception:
        import shutil
        try:
            shutil.copy2(downloaded, dest)
        except OSError:
            return downloaded
        return dest


# ── BaseImageProvider 기반 클래스 제공자 (Phase 26 W4 — 03-02) ──────
# 기존 함수 기반 search_body_image 경로와 동일한 검색 로직(API 키 env,
# image.thumbnail 의 search) 을 BaseImageProvider 인터페이스(fetch/validate)
# 로 노출하는 적응 클래스. 캐싱은 BaseImageProvider.shared_cache (공유
# CacheManager 싱글톤) 를 사용한다.
#
# ⚠ 행동 보존: 기존 공개 함수 search_body_image / _read_cache /
#   _write_cache (24h 파일 캐시) 는 무변경 유지 — 이미지 파이프라인
#   테스트(test_image_search.py 등)가 이 경로에 의존한다. 새 클래스는
#   위 함수를 건드리지 않으며, 인메모리 캐시(메타데이터)와 파일
#   캐시(다운로드 경로)는 별도 네임스페이스로 공존한다.

class UnsplashProvider(BaseImageProvider):
    """Unsplash body-image 제공자 (BaseImageProvider 인터페이스).

    fetch(keyword, timeout=30.0) → photo 메타데이터 dict 또는 None.
      - image.thumbnail.UnsplashProvider 검색 로직 재사용 (API 키는
        env UNSPLASH_ACCESS_KEY 또는 생성자 access_key).
      - 결과는 공유 CacheManager 에 캐시 — 같은 키워드 재요청 시
        네트워크 호출 없이 즉시 반환.
    validate(result) → dict + id + 이미지 URL 필드 존재 여부 검증.
    """

    def __init__(self, access_key: Optional[str] = None):
        """access_key 미지정 시 env UNSPLASH_ACCESS_KEY 사용."""
        self._access_key = access_key

    def fetch(self, keyword: str, timeout: float = 30.0) -> Optional[dict]:
        if not keyword:
            return None
        cache_key = f"unsplash:{keyword}"
        cached = self.shared_cache.get(cache_key)
        if cached is not None:
            return cached if isinstance(cached, dict) else None
        from image.thumbnail import UnsplashProvider as ThumbProvider
        provider = ThumbProvider(self._access_key or _UNSPLASH_KEY)
        results = provider.search(keyword)
        result = results[0] if results else None
        if self.validate(result):
            self.shared_cache.set(cache_key, result)
            return result
        return None

    def validate(self, result: Any) -> bool:
        if not isinstance(result, dict):
            return False
        if not result.get("id"):
            return False
        return bool(result.get("url_raw") or result.get("url_regular") or result.get("url"))


class PexelsProvider(BaseImageProvider):
    """Pexels body-image 제공자 (BaseImageProvider 인터페이스).

    fetch(keyword, timeout=30.0) → photo 메타데이터 dict 또는 None.
      - image.thumbnail.PexelsProvider 검색 로직 재사용 (API 키는
        env PEXELS_API_KEY 또는 생성자 api_key).
      - 결과는 공유 CacheManager 에 캐시.
    validate(result) → dict + id + 이미지 URL 필드 존재 여부 검증.
    """

    def __init__(self, api_key: Optional[str] = None):
        """api_key 미지정 시 env PEXELS_API_KEY 사용."""
        self._api_key = api_key

    def fetch(self, keyword: str, timeout: float = 30.0) -> Optional[dict]:
        if not keyword:
            return None
        cache_key = f"pexels:{keyword}"
        cached = self.shared_cache.get(cache_key)
        if cached is not None:
            return cached if isinstance(cached, dict) else None
        from image.thumbnail import PexelsProvider as ThumbProvider
        provider = ThumbProvider(self._api_key or _PEXELS_KEY)
        results = provider.search(keyword)
        result = results[0] if results else None
        if self.validate(result):
            self.shared_cache.set(cache_key, result)
            return result
        return None

    def validate(self, result: Any) -> bool:
        if not isinstance(result, dict):
            return False
        if not result.get("id"):
            return False
        return bool(result.get("url") or result.get("url_original") or result.get("url_raw"))



