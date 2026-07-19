"""
krea_client.py — KREA AI 비동기 이미지 생성 클라이언트 (Phase 9)

패턴:
  1. POST /generate/image/krea/krea-2/medium → job_id
  2. GET /jobs/{job_id} 폴링 (2s 간격, 최대 90s)
  3. completed 시 result.urls[0] 다운로드 → output/images/krea_{slug}.jpg

pollinations_client.py와 동일한 반환 타입 (Path | None).
"""

import os
import time
import requests
from pathlib import Path

from mc_paths import load_config

API_BASE = "https://api.krea.ai"
MODEL_ENDPOINT = "/generate/image/krea/krea-2/medium"
IMAGE_DIR = Path(__file__).resolve().parent.parent / "output" / "images"


def _load_api_key() -> str:
    env_path = Path(".env.common")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() == "KREA_API_KEY":
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return os.getenv("KREA_API_KEY", "")


def _poll_job(job_id: str, api_key: str, interval: float, timeout: float) -> dict:
    """Poll GET /jobs/{job_id} until completed/failed or timeout."""
    url = f"{API_BASE}/jobs/{job_id}"
    headers = {"Authorization": f"Bearer {api_key}"}
    elapsed = 0.0
    while elapsed < timeout:
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            job = resp.json()
            status = job.get("status", "")
            if status == "completed":
                return job
            if status in ("failed", "cancelled"):
                return job
            print(f"  [krea] job {job_id[:8]}... status={status} ({elapsed:.0f}s elapsed)")
            time.sleep(interval)
            elapsed += interval
        except requests.RequestException as e:
            print(f"  [krea] poll error: {e}")
            time.sleep(interval)
            elapsed += interval
    return {"status": "timeout"}


def generate_image(
    prompt: str,
    slug: str = "post",
    aspect_ratio: str = "1:1",
    resolution: str = "1K",
) -> Path | None:
    """KREA AI 이미지 생성 (async job pattern). Returns Path | None."""
    api_key = _load_api_key()
    if not api_key:
        print("  [krea] ⚠️ KREA_API_KEY not set")
        return None

    config = load_config()
    krea_cfg = config.get("krea", {})
    model_endpoint = krea_cfg.get("model", MODEL_ENDPOINT.lstrip("/"))
    poll_interval = krea_cfg.get("poll_interval_seconds", 2)
    poll_timeout = krea_cfg.get("poll_timeout_seconds", 90)

    IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    # Step 1: Create job
    url = f"{API_BASE}/generate/image/{model_endpoint}"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "resolution": resolution,
    }
    try:
        print(f"  [krea] creating job: {url}")
        resp = requests.post(url, headers=headers, json=body, timeout=30)
        resp.raise_for_status()
        job = resp.json()
        job_id = job.get("job_id")
        if not job_id:
            print(f"  [krea] ⚠️ no job_id in response: {job}")
            return None
        print(f"  [krea] job created: {job_id[:8]}...")
    except requests.RequestException as e:
        print(f"  [krea] ⚠️ job creation failed: {e}")
        return None

    # Step 2: Poll
    final_job = _poll_job(job_id, api_key, poll_interval, poll_timeout)
    status = final_job.get("status", "unknown")

    if status == "completed":
        try:
            image_url = final_job["result"]["urls"][0]
        except (KeyError, IndexError, TypeError):
            print(f"  [krea] ⚠️ malformed result: {final_job.get('result')}")
            return None
        try:
            print(f"  [krea] downloading: {image_url[:80]}...")
            img_resp = requests.get(image_url, timeout=60)
            img_resp.raise_for_status()
            filename = f"krea_{slug}.jpg"
            dest = IMAGE_DIR / filename
            dest.write_bytes(img_resp.content)
            print(f"  [krea] ✅ saved: {dest} ({len(img_resp.content):,} bytes)")
            return dest
        except requests.RequestException as e:
            print(f"  [krea] ⚠️ download failed: {e}")
            return None

    print(f"  [krea] ❌ job ended with status={status}")
    return None


if __name__ == "__main__":
    import sys
    prompt = sys.argv[1] if len(sys.argv) > 1 else "A cute puppy on a mountain, digital art"
    out = generate_image(prompt, slug="krea-test")
    if out:
        print(f"Saved: {out}")
    else:
        print("Failed")
