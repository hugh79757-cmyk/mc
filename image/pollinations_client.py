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
):
    """
    Pollinations.ai flux 호출 → 로컬 파일 저장.
    Returns: Result(Path) — 성공 시 value=Path, 실패 시 error=Error
    """
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from chain_models import Result, ErrorCategory

    params = {
        "width": str(width),
        "height": str(height),
        "model": model,
    }
    if seed is not None:
        params["seed"] = str(seed)

    encoded = urllib.parse.quote(prompt)
    query = urllib.parse.urlencode(params)
    url = f"{POLLINATIONS_BASE.format(encoded=encoded)}?{query}"

    IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    last_error = ""
    for attempt in range(retries):
        try:
            print(f"  [image] 요청: {url[:120]}...")
            req = urllib.request.Request(url, headers={"User-Agent": "mc-bot/1.0"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                image_bytes = resp.read()

            if len(image_bytes) < 1000:
                last_error = f"응답 너무 작음 ({len(image_bytes)} bytes)"
                print(f"  [image] ⚠️ {last_error}, 재시도...")
                continue

            filename = f"{slug}_{width}x{height}.webp"
            dest = IMAGE_DIR / filename
            img = Image.open(BytesIO(image_bytes)).convert("RGB")
            img.save(dest, "WEBP", quality=85)
            print(f"  [image] ✅ 저장: {dest} ({dest.stat().st_size:,} bytes, WebP)")
            return Result.success(dest)

        except urllib.error.HTTPError as e:
            if e.code == 429:
                last_error = f"Rate limit (HTTP {e.code})"
                print(f"  [image] ⚠️ {last_error} (attempt {attempt+1}/{retries})")
                if attempt < retries - 1:
                    time.sleep(10 * (attempt + 1))
                    continue
                return Result.failure(ErrorCategory.RATE_LIMITED, last_error, "pollinations")
            else:
                last_error = f"HTTP {e.code}"
                print(f"  [image] ⚠️ {last_error} (attempt {attempt+1}/{retries})")
                if attempt < retries - 1:
                    time.sleep(5)
                    continue
                return Result.failure(ErrorCategory.TRANSIENT, last_error, "pollinations")
        except urllib.error.URLError as e:
            last_error = f"URL Error: {e.reason}"
            print(f"  [image] ⚠️ {last_error} (attempt {attempt+1}/{retries})")
            if attempt < retries - 1:
                time.sleep(10)
                continue
            return Result.failure(ErrorCategory.TRANSIENT, last_error, "pollinations")
        except Exception as e:
            last_error = str(e)
            return Result.failure(ErrorCategory.PERMANENT, last_error, "pollinations")

    return Result.failure(ErrorCategory.PERMANENT, f"{retries}회 재시도 실패: {last_error}", "pollinations")


# ── CLI test ──
if __name__ == "__main__":
    import sys
    prompt = sys.argv[1] if len(sys.argv) > 1 else "A cute puppy on a mountain, digital art"
    out = generate_image(prompt)
    print(f"\nImage saved to: {out}" if out else "\nFailed")
