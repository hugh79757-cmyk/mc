"""
thumbnail — Unsplash/Pexels 실사 사진 + 텍스트 오버레이 썸네일 생성

Provider chain:
  1. Unsplash (실사 사진, primary)
  2. Pexels (실사 사진, 1st fallback)
  3. Pollinations (AI 생성, 2nd fallback)
  4. Krea (AI 생성, 3rd fallback)

Output: 1024×1024 square image with title text overlay.
"""

from __future__ import annotations

import os
import re
import time
import random
from pathlib import Path
from typing import Optional

import requests
from PIL import Image, ImageDraw, ImageFont

from mc_paths import load_config

# ── 디렉토리 ──

IMAGE_DIR = Path("output/images")
IMAGE_DIR.mkdir(parents=True, exist_ok=True)


def _infer_source_from_path(path: Path) -> str:
    name = path.name.lower()
    if "unsplash" in name:
        return "unsplash"
    if "pexels" in name:
        return "pexels"
    if "pollinations" in name:
        return "pollinations"
    return "unknown"

FONT_PATH = Path("assets/fonts/NotoSansKR-Regular.otf")
FONT_BOLD_PATH = Path("assets/fonts/NotoSansKR-Bold.otf")  # optional

# ── API 키 로딩 ──

def _load_env() -> dict:
    """Load env vars from ~/.env.common (절대경로 우선), then local .env/.env.common, then system env."""
    candidates = [
        Path.home() / ".env.common",
        Path(".env.common"),
        Path(".env"),
    ]
    for env_path in candidates:
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return {
        "unsplash_key": os.getenv("UNSPLASH_ACCESS_KEY", ""),
        "pexels_key": os.getenv("PEXELS_API_KEY", ""),
    }


# ── Unsplash Provider ──

class UnsplashProvider:
    """Search & download real photos from Unsplash API."""

    BASE = "https://api.unsplash.com"

    def __init__(self, access_key: str):
        self.headers = {"Authorization": f"Client-ID {access_key}"}

    def search(self, query: str, per_page: int = 5) -> list[dict]:
        """Search photos by keyword. Returns list of {id, url_raw, url_regular, author}."""
        if not self.headers.get("Authorization"):
            return []
        try:
            resp = requests.get(
                f"{self.BASE}/search/photos",
                headers=self.headers,
                params={"query": query, "per_page": per_page, "orientation": "squarish"},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            results = []
            for r in data.get("results", []):
                results.append({
                    "id": r["id"],
                    "url_raw": r["urls"]["raw"] + "&w=1024&h=1024&fit=crop",
                    "url_regular": r["urls"]["regular"],
                    "author": r["user"]["name"],
                    "alt": r.get("alt_description", ""),
                })
            return results
        except requests.RequestException as e:
            print(f"  [thumbnail] Unsplash search error: {e}")
            return []

    def download(self, photo: dict) -> Optional[Path]:
        """Download photo to local file. Returns Path or None."""
        url = photo.get("url_raw") or photo.get("url_regular")
        if not url:
            return None
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            ext = ".jpg"
            filename = f"thumb_unsplash_{photo['id']}{ext}"
            dest = IMAGE_DIR / filename
            dest.write_bytes(resp.content)
            return dest
        except requests.RequestException as e:
            print(f"  [thumbnail] Unsplash download error: {e}")
            return None


# ── Pexels Provider ──

class PexelsProvider:
    """Search & download real photos from Pexels API."""

    BASE = "https://api.pexels.com/v1"

    def __init__(self, api_key: str):
        self.headers = {"Authorization": api_key}

    def search(self, query: str, per_page: int = 5) -> list[dict]:
        """Search photos by keyword. Returns list of {id, url, author}."""
        if not self.headers.get("Authorization"):
            return []
        try:
            resp = requests.get(
                f"{self.BASE}/search",
                headers=self.headers,
                params={"query": query, "per_page": per_page, "orientation": "square"},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            results = []
            for r in data.get("photos", []):
                results.append({
                    "id": r["id"],
                    "url": r["src"]["large"],
                    "url_original": r["src"]["original"],
                    "author": r["photographer"],
                    "alt": r.get("alt", ""),
                })
            return results
        except requests.RequestException as e:
            print(f"  [thumbnail] Pexels search error: {e}")
            return []

    def download(self, photo: dict) -> Optional[Path]:
        """Download photo to local file. Returns Path or None."""
        url = photo.get("url")
        if not url:
            return None
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            ext = ".jpg"
            filename = f"thumb_pexels_{photo['id']}{ext}"
            dest = IMAGE_DIR / filename
            dest.write_bytes(resp.content)
            return dest
        except requests.RequestException as e:
            print(f"  [thumbnail] Pexels download error: {e}")
            return None


# ── Pollinations Fallback ──

def _pollinations_fallback(prompt: str, slug: str) -> Optional[Path]:
    """Generate image via Pollinations.ai as fallback."""
    try:
        from image.pollinations_client import generate_image
        return generate_image(prompt, slug=slug)
    except Exception as e:
        print(f"  [thumbnail] Pollinations fallback error: {e}")
        return None


# ── Krea Fallback ──

def _krea_fallback(prompt: str, slug: str) -> Optional[Path]:
    """Krea AI fallback (async job pattern)."""
    try:
        from image.krea_client import generate_image
        return generate_image(prompt, slug=slug)
    except Exception as e:
        print(f" [thumbnail] Krea fallback error: {e}")
        return None


# ── 텍스트 오버레이 ──

def _load_font(size: int) -> ImageFont.FreeTypeFont:
    """Load NotoSansKR; fall back to default if missing."""
    font_path = FONT_PATH if FONT_PATH.exists() else None
    if font_path:
        return ImageFont.truetype(str(font_path), size)
    return ImageFont.load_default()


def _fit_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
) -> str:
    """
    Wrap text to fit within max_width by inserting line breaks.
    Preserves existing newlines.
    """
    lines = []
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append("")
            continue
        words = list(paragraph)  # CJK: each char as a "word"
        current_line = ""
        for ch in words:
            test_line = current_line + ch
            bbox = draw.textbbox((0, 0), test_line, font=font)
            w = bbox[2] - bbox[0]
            if w > max_width and current_line:
                lines.append(current_line)
                current_line = ch
            else:
                current_line = test_line
        if current_line:
            lines.append(current_line)
    return "\n".join(lines)


def add_text_overlay(
    image_path: Path,
    title: str,
    subtitle: Optional[str] = None,
    target_size: tuple[int, int] = (1024, 1024),
) -> Path:
    """실사 사진 위에 큰 제목 + 하단 강조 그라데이션 오버레이."""
    img = Image.open(image_path).convert("RGB")

    W, H = target_size

    # 1:1 center crop + resize
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    img = img.crop((left, top, left + side, top + side)).resize(target_size, Image.LANCZOS)

    # 하단 강조 그라데이션 (55% 지점부터, 최대 alpha 220)
    overlay = Image.new("RGBA", target_size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    g_start = int(H * 0.45)
    for y in range(g_start, H):
        t = (y - g_start) / (H - g_start)
        alpha = int((t ** 1.3) * 220)
        od.line([(0, y), (W, y)], fill=(0, 0, 0, alpha))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(img)

    padding = 64
    usable_w = W - padding * 2

    # 제목 폰트: 길이에 따라 크게 (기존보다 대폭 확대)
    n = len(title)
    if n <= 18:
        title_size = 88
    elif n <= 28:
        title_size = 72
    elif n <= 40:
        title_size = 60
    else:
        title_size = 50
    sub_size = max(28, int(title_size * 0.42))

    title_font = _load_font(title_size)
    sub_font = _load_font(sub_size)

    wrapped_title = _fit_text(draw, title, title_font, usable_w)
    title_lines = wrapped_title.split("\n")
    line_h = title_size + 14
    total_title_h = len(title_lines) * line_h

    wrapped_sub = ""
    sub_h = 0
    if subtitle:
        wrapped_sub = _fit_text(draw, subtitle, sub_font, usable_w)
        sub_lines = wrapped_sub.split("\n")
        sub_h = len(sub_lines) * (sub_size + 8)

    # 컬러 강조 바 + 제목을 하단 1/3 지점에 배치 (바닥에서 살짝 위로)
    block_h = total_title_h + (sub_h + 24 if subtitle else 0)
    y_start = H - padding - block_h - 20

    # 좌측 컬러 강조 바
    bar_x = padding - 24
    draw.rectangle([bar_x, y_start, bar_x + 8, y_start + block_h], fill=(255, 90, 60))

    # 제목 (좌측 정렬, 그림자)
    y = y_start
    for line in title_lines:
        draw.text((padding + 3, y + 3), line, font=title_font, fill=(0, 0, 0))
        draw.text((padding, y), line, font=title_font, fill=(255, 255, 255))
        y += line_h

    # 부제목
    if subtitle and wrapped_sub:
        y += 12
        for line in wrapped_sub.split("\n"):
            draw.text((padding + 2, y + 2), line, font=sub_font, fill=(0, 0, 0))
            draw.text((padding, y), line, font=sub_font, fill=(230, 230, 230))
            y += sub_size + 8

    safe_slug = re.sub(r"[^a-zA-Z0-9가-힣_-]", "", str(image_path.stem))[:60]
    safe_slug = re.sub(r"^thumb_", "", safe_slug)
    out_path = IMAGE_DIR / f"thumb_{safe_slug}.webp"
    img.save(out_path, "WEBP", quality=88)
    print(f"  [thumbnail] Text overlay saved → {out_path}")
    return out_path

# ── 메인 오케스트레이터 ──

def generate_thumbnail(
  title: str,
  keyword: str,
  slug: str = "",
  subtitle: Optional[str] = None,
) -> Optional[tuple[Path, str]]:
  """
  Generate a thumbnail photo with text overlay.

  Provider order:
  1. Unsplash (real photo)
  2. Pexels (real photo, fallback)
  3. Pollinations (AI generated, fallback)
  4. Krea (AI generated, fallback)

  Args:
    title: Title text to overlay on the image.
    keyword: Search keyword for photo lookup.
    slug: Unique slug for filename.
    subtitle: Optional sub-title line.

  Returns:
    (path, source_name) tuple, or None if all providers failed.
    source_name: 'unsplash' | 'pexels' | 'pollinations' | 'pillow_chart' | 'unknown'
  """
  # Idempotency: if file already exists at expected path, return it directly
  if slug:
    expected = IMAGE_DIR / f"thumb_{slug}.webp"
    # 하위호환: 기존 .jpg 파일도 확인
    expected_jpg = IMAGE_DIR / f"thumb_{slug}.jpg"
    if not expected.exists() and expected_jpg.exists():
        expected = expected_jpg
    if expected.exists():
      print(f" [thumbnail] 파일 존재, 재사용: {expected}")
      return (expected, _infer_source_from_path(expected))

  env = _load_env()
  config = load_config()
  thumb_cfg = config.get("thumbnail", {})
  provider = thumb_cfg.get("provider", "auto")
  fallback_chain = thumb_cfg.get("fallback_chain", ["pexels", "pollinations", "krea"])
  target_size = tuple(thumb_cfg.get("target_size", [1024, 1024]))

  downloaded: Optional[Path] = None
  source: str = "unknown"

  # ── Provider 1: Unsplash ──
  if provider in ("auto", "unsplash"):
    unsplash = UnsplashProvider(env["unsplash_key"])
    if results := unsplash.search(keyword):
      photo = random.choice(results)
      print(f" [thumbnail] Unsplash → {photo['id']} by {photo['author']}")
      downloaded = unsplash.download(photo)
      if downloaded:
        source = "unsplash"
        result = add_text_overlay(downloaded, title, subtitle, target_size)
        if result:
          return (result, source)

  # ── Fallback chain ──
  for fallback_name in fallback_chain:
    if downloaded:
      break

    if fallback_name == "pexels":
      pexels = PexelsProvider(env["pexels_key"])
      if results := pexels.search(keyword):
        photo = random.choice(results)
        print(f" [thumbnail] Pexels → {photo['id']} by {photo['author']}")
        downloaded = pexels.download(photo)
        if downloaded:
          source = "pexels"
          result = add_text_overlay(downloaded, title, subtitle, target_size)
          if result:
            return (result, source)

    elif fallback_name == "pollinations":
      print(f" [thumbnail] Pollinations fallback → {keyword}")
      downloaded = _pollinations_fallback(keyword, slug or title)
      if downloaded:
        source = "pollinations"
        result = add_text_overlay(downloaded, title, subtitle, target_size)
        if result:
          return (result, source)

    elif fallback_name == "krea":
      print(f" [thumbnail] Krea fallback → {keyword}")
      downloaded = _krea_fallback(keyword, slug or title)
      if downloaded:
        source = "krea"
        result = add_text_overlay(downloaded, title, subtitle, target_size)
        if result:
          return (result, source)

  print(f" [thumbnail] All providers failed for '{keyword}'")
  return None


def generate_content_image(
    prompt: str,
    slug: str = "post",
    width: int = 1024,
    height: int = 1024,
    model: str = "unsplash",
    seed: int = None,
    retries: int = 3,
) -> "Result":
    """
    Unsplash/Pexels 실사 사진을 콘텐츠 이미지로 저장 (텍스트 오버레이 없음).

    generate_thumbnail()과 동일한 Unsplash→Pexels provider chain 사용.
    차이점: add_text_overlay()를 적용하지 않고 원본 사진을 그대로 저장.

    Args:
        prompt: 이미지 검색 키워드 (build_full_prompt() 출력)
        slug: 파일명용 고유 식별자
        width: 대상 너비 (보존 목적, 실제 사용은 provider가 결정)
        height: 대상 높이 (보존 목적)
        model: 무시 (호환성 유지용)
        seed: 무시 (호환성 유지용)
        retries: 재시도 횟수

    Returns:
        Result.success(Path) 또는 Result.failure(...)
    """
    # chain_models는 mc_paths를 통해 지연 임포트
    from chain_models import Result, ErrorCategory

    # prompt에서 실제 검색용 키워드 추출 (영문 키워드 우선)
    keyword = prompt.strip()
    # 파일명용 slug
    _slug = slug or "post"

    # Idempotency
    save_name = f"{_slug}_{width}x{height}.webp"
    expected = IMAGE_DIR / save_name
    if expected.exists():
        print(f" [content_image] 파일 존재, 재사용: {expected}")
        return Result.success(expected)

    env = _load_env()
    config = load_config()
    thumb_cfg = config.get("thumbnail", {})
    fallback_chain = thumb_cfg.get("fallback_chain", ["pexels", "pollinations", "krea"])

    downloaded: Optional[Path] = None

    # ── Provider 1: Unsplash ──
    unsplash_key = env.get("unsplash_key", "")
    if unsplash_key:
        try:
            unsplash = UnsplashProvider(unsplash_key)
            if results := unsplash.search(keyword):
                photo = random.choice(results)
                print(f" [content_image] Unsplash → {photo['id']} by {photo['author']}")
                downloaded = unsplash.download(photo)
                if downloaded:
                    # 저장: 텍스트 오버레이 없이 원본 리사이즈만
                    img = Image.open(downloaded).convert("RGB")
                    img = img.resize((width, height), Image.LANCZOS)
                    img.save(expected, "WEBP", quality=85)
                    print(f" [content_image] ✅ 저장: {expected}")
                    return Result.success(expected)
        except Exception as e:
            print(f" [content_image] Unsplash 실패: {e}")

    # ── Fallback: Pexels ──
    pexels_key = env.get("pexels_key", "")
    if pexels_key and "pexels" in fallback_chain:
        try:
            pexels = PexelsProvider(pexels_key)
            if results := pexels.search(keyword):
                photo = random.choice(results)
                print(f" [content_image] Pexels → {photo['id']} by {photo['author']}")
                downloaded = pexels.download(photo)
                if downloaded:
                    img = Image.open(downloaded).convert("RGB")
                    img = img.resize((width, height), Image.LANCZOS)
                    img.save(expected, "WEBP", quality=85)
                    print(f" [content_image] ✅ 저장: {expected}")
                    return Result.success(expected)
        except Exception as e:
            print(f" [content_image] Pexels 실패: {e}")

    print(f" [content_image] 모든 provider 실패: '{keyword}'")
    return Result.failure(ErrorCategory.PERMANENT, f"이미지 생성 실패: {keyword}", source="unsplash/pexels")
