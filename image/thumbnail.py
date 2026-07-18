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

IMAGE_DIR = Path("static/images")
IMAGE_DIR.mkdir(parents=True, exist_ok=True)

FONT_PATH = Path("assets/fonts/NotoSansKR-Regular.otf")
FONT_BOLD_PATH = Path("assets/fonts/NotoSansKR-Bold.otf")  # optional

# ── API 키 로딩 ──

def _load_env() -> dict:
    """Load env vars from .env.common or system env."""
    env_path = Path(".env.common")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
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


# ── Krea Fallback (placeholder) ──

def _krea_fallback(prompt: str, slug: str) -> Optional[Path]:
    """Krea AI fallback (stub — no public API yet)."""
    print("  [thumbnail] Krea fallback not implemented, returning None")
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
    """
    Add text overlay to a thumbnail image.

    - Resizes/crops image to target_size (center-square crop then resize).
    - Adds a dark gradient overlay at the bottom for readability.
    - Draws title text (large, centered) and optional subtitle (smaller).

    Returns path to the overlaid image.
    """
    img = Image.open(image_path).convert("RGB")

    # ── 1:1 center crop ──
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    img = img.crop((left, top, left + side, top + side))
    img = img.resize(target_size, Image.LANCZOS)

    # ── dark gradient overlay (bottom 60%) ──
    overlay = Image.new("RGBA", target_size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    for y in range(target_size[1]):
        # gradient: start at 40% height, 0 opacity → 100% at bottom
        gradient_start = int(target_size[1] * 0.35)
        if y < gradient_start:
            continue
        t = (y - gradient_start) / (target_size[1] - gradient_start)
        alpha = int(t * 180)  # max 180/255
        overlay_draw.line([(0, y), (target_size[0], y)], fill=(0, 0, 0, alpha))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(img)

    # ── title font sizing ──
    title_font_size = 48
    subtitle_font_size = 28

    # Scale font based on title length
    if len(title) > 30:
        title_font_size = 36
    elif len(title) > 50:
        title_font_size = 28

    title_font = _load_font(title_font_size)
    sub_font = _load_font(subtitle_font_size)

    padding = 60
    usable_w = target_size[0] - padding * 2

    # ── wrap & draw title ──
    wrapped_title = _fit_text(draw, title, title_font, usable_w)
    title_lines = wrapped_title.split("\n")
    line_height = title_font_size + 8
    total_title_h = len(title_lines) * line_height

    # subtitle
    sub_h = 0
    wrapped_sub = ""
    if subtitle:
        wrapped_sub = _fit_text(draw, subtitle, sub_font, usable_w)
        sub_h = len(wrapped_sub.split("\n")) * (subtitle_font_size + 6)

    # ── vertical position (bottom-aligned) ──
    total_h = total_title_h + sub_h + 20
    y_start = target_size[1] - padding - total_h

    # draw title
    y = y_start
    for line in title_lines:
        bbox = draw.textbbox((0, 0), line, font=title_font)
        lw = bbox[2] - bbox[0]
        x = (target_size[0] - lw) // 2
        # text shadow for readability
        draw.text((x + 2, y + 2), line, font=title_font, fill=(0, 0, 0, 200))
        draw.text((x, y), line, font=title_font, fill=(255, 255, 255))
        y += line_height

    # draw subtitle
    if subtitle and wrapped_sub:
        y += 10
        for line in wrapped_sub.split("\n"):
            bbox = draw.textbbox((0, 0), line, font=sub_font)
            lw = bbox[2] - bbox[0]
            x = (target_size[0] - lw) // 2
            draw.text((x + 1, y + 1), line, font=sub_font, fill=(0, 0, 0, 160))
            draw.text((x, y), line, font=sub_font, fill=(220, 220, 220))
            y += subtitle_font_size + 6

    # ── save ──
    safe_slug = re.sub(r"[^a-zA-Z0-9가-힣_-]", "", str(image_path.stem))[:60]
    out_path = IMAGE_DIR / f"thumb_{safe_slug}.jpg"
    img.save(out_path, "JPEG", quality=92)
    print(f"  [thumbnail] Text overlay saved → {out_path}")
    return out_path


# ── 메인 오케스트레이터 ──

def generate_thumbnail(
    title: str,
    keyword: str,
    slug: str = "",
    subtitle: Optional[str] = None,
) -> Optional[Path]:
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
        Path to the final thumbnail image, or None if all providers failed.
    """
    env = _load_env()
    config = load_config()
    thumb_cfg = config.get("thumbnail", {})
    provider = thumb_cfg.get("provider", "auto")
    fallback_chain = thumb_cfg.get("fallback_chain", ["pexels", "pollinations", "krea"])
    target_size = tuple(thumb_cfg.get("target_size", [1024, 1024]))

    downloaded: Optional[Path] = None

    # ── Provider 1: Unsplash ──
    if provider in ("auto", "unsplash"):
        unsplash = UnsplashProvider(env["unsplash_key"])
        if results := unsplash.search(keyword):
            photo = random.choice(results)
            print(f"  [thumbnail] Unsplash → {photo['id']} by {photo['author']}")
            downloaded = unsplash.download(photo)
            if downloaded:
                return add_text_overlay(downloaded, title, subtitle, target_size)

    # ── Fallback chain ──
    for fallback_name in fallback_chain:
        if downloaded:
            break

        if fallback_name == "pexels":
            pexels = PexelsProvider(env["pexels_key"])
            if results := pexels.search(keyword):
                photo = random.choice(results)
                print(f"  [thumbnail] Pexels → {photo['id']} by {photo['author']}")
                downloaded = pexels.download(photo)
                if downloaded:
                    return add_text_overlay(downloaded, title, subtitle, target_size)

        elif fallback_name == "pollinations":
            print(f"  [thumbnail] Pollinations fallback → {keyword}")
            downloaded = _pollinations_fallback(keyword, slug or title)
            if downloaded:
                return add_text_overlay(downloaded, title, subtitle, target_size)

        elif fallback_name == "krea":
            print(f"  [thumbnail] Krea fallback → {keyword}")
            downloaded = _krea_fallback(keyword, slug or title)
            if downloaded:
                return add_text_overlay(downloaded, title, subtitle, target_size)

    print(f"  [thumbnail] All providers failed for '{keyword}'")
    return None
