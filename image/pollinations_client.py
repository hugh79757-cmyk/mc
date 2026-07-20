"""
pollinations_client.py — Pollinations.ai flux 이미지 생성

REST API: GET https://image.pollinations.ai/prompt/{description}
Returns: image bytes → 로컬 파일 저장
"""

import json
import time
import re
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

from PIL import Image
from io import BytesIO

import mc_paths  # noqa: F401 — ensure_5000_on_path 사이드 이펙트

POLLINATIONS_BASE = "https://image.pollinations.ai/prompt/{encoded}"

# mc 루트/output/images/ 에 저장
IMAGE_DIR = Path(__file__).resolve().parent.parent / "output" / "images"


def _sanitize_filename(label: str, max_len: int = 60) -> str:
    """파일명에 쓸 수 없는 문자 제거 + 길이 제한."""
    safe = re.sub(r"[^\w\-_]", "_", label)
    safe = re.sub(r"_+", "_", safe).strip("_")
    if not safe:
        safe = "generated"
    return safe[:max_len]


def generate_image(
    prompt: str,
    slug: str = "post",
    width: int = 1024,
    height: int = 1024,
    model: str = "flux",
    seed: int = None,
    retries: int = 3,
) -> Path | None:
    """
    Pollinations.ai flux 호출 → 로컬 파일 저장.
    Returns: 저장된 이미지 Path (실패 시 None)

    Args:
        prompt: 영문 이미지 생성 프롬프트
        slug:  파일명 식별자
        width/height: 해상도 (기본 1:1)
        model: "flux" (기본)
        seed:  고정 시드 (None=랜덤)
    """
    params = {
        "width": str(width),
        "height": str(height),
        "model": model,
    }
    if seed is not None:
        params["seed"] = str(seed)

    # 프롬프트 URL 인코딩
    encoded = urllib.parse.quote(prompt)
    query = urllib.parse.urlencode(params)
    url = f"{POLLINATIONS_BASE.format(encoded=encoded)}?{query}"

    IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    for attempt in range(retries):
        try:
            print(f"  [image] 요청: {url[:120]}...")
            req = urllib.request.Request(url, headers={"User-Agent": "mc-bot/1.0"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                image_bytes = resp.read()

            if len(image_bytes) < 1000:
                print(f"  [image] ⚠️ 응답이 너무 작음 ({len(image_bytes)} bytes), 재시도...")
                continue

            filename = f"{slug}_{width}x{height}.webp"
            dest = IMAGE_DIR / filename
            img = Image.open(BytesIO(image_bytes)).convert("RGB")
            img.save(dest, "WEBP", quality=85)
            print(f"  [image] ✅ 저장: {dest} ({dest.stat().st_size:,} bytes, WebP)")
            return dest

        except urllib.error.HTTPError as e:
            print(f"  [image] ⚠️ HTTP {e.code} (attempt {attempt+1}/{retries})")
            if attempt < retries - 1:
                time.sleep(5)
        except urllib.error.URLError as e:
            print(f"  [image] ⚠️ URL Error: {e.reason} (attempt {attempt+1}/{retries})")
            if attempt < retries - 1:
                time.sleep(10)

    print(f"  [image] ❌ {retries}회 재시도 실패")
    return None


# ── CLI test ──
if __name__ == "__main__":
    import sys
    prompt = sys.argv[1] if len(sys.argv) > 1 else "A cute puppy on a mountain, digital art"
    out = generate_image(prompt)
    print(f"\nImage saved to: {out}" if out else "\nFailed")
