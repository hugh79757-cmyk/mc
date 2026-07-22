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
from typing import Optional

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

def search_body_image(keyword: str, slug: str) -> Optional[tuple[Path, str]]:
    """
    Search for a body image via Unsplash -> Pexels.

    Args:
        keyword: Search keyword.
        slug: Post slug for filename.

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

    # Try Unsplash first
    from image.thumbnail import UnsplashProvider

    provider = UnsplashProvider(_UNSPLASH_KEY)
    if results := provider.search(keyword):
        photo = results[0]
        downloaded = provider.download(photo)
        if downloaded and downloaded.exists():
            # Rename to body_{slug}_unsplash_{id}.webp
            body_path = _to_body_path(downloaded, slug, "unsplash", photo.get("id", "0"))
            _write_cache(cache_key, {"path": str(body_path), "source": "unsplash"})
            return (body_path, "unsplash")

    # Fallback to Pexels
    from image.thumbnail import PexelsProvider

    provider = PexelsProvider(_PEXELS_KEY)
    if results := provider.search(keyword):
        photo = results[0]
        downloaded = provider.download(photo)
        if downloaded and downloaded.exists():
            body_path = _to_body_path(downloaded, slug, "pexels", str(photo.get("id", "0")))
            _write_cache(cache_key, {"path": str(body_path), "source": "pexels"})
            return (body_path, "pexels")

    # All providers failed — cache the miss to avoid repeat calls
    _write_cache(cache_key, {"path": "", "source": ""})
    return None


# ── Helpers ──

def _to_body_path(downloaded: Path, slug: str, source: str, photo_id: str) -> Path:
    """Rename downloaded image to body_{slug}_{source}_{id}.webp in output/images."""
    IMAGE_DIR = Path("output/images")
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    safe_id = re.sub(r"[^a-zA-Z0-9_-]", "", photo_id)[:20] if photo_id else "0"
    dest = IMAGE_DIR / f"body_{slug}_{source}_{safe_id}.webp"
    try:
        import shutil
        shutil.copy2(downloaded, dest)
        return dest
    except OSError:
        return downloaded



