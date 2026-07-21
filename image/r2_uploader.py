"""
mc 전용 R2 이미지 업로더

mde2/app/services/r2_uploader.py를 기반으로 독립 구성.
- thumbnail.webp (레거시) + thumb_*.webp (새 패턴) 모두 지원
- 환경변수는 .env.common에서 로드 (mc 패턴)
"""

import os
import boto3
from pathlib import Path
from typing import Optional, Tuple
from dotenv import load_dotenv

# ── 환경변수 로딩 ──

_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

R2_ENDPOINT_URL = os.getenv("R2_ENDPOINT_URL")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME")
R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL", "").rstrip("/")

# ── Hugo 사이트별 R2 도메인 매핑 (mde2와 동일) ──

HUGO_R2_DOMAINS = {
    "rotcha": ("images/rotcha", "https://img.rotcha.kr"),
    "informationhot": ("images/informationhot", "https://img.informationhot.kr"),
    "hotissue": ("images/hotissue", "https://img-hotissue.rotcha.kr"),
    "stock": ("images/stock", "https://img-stock.informationhot.kr"),
    "issue-techpawz": ("images/issue-techpawz", "https://img-issue.techpawz.com"),
    "biz.techpawz": ("images/biz-techpawz", "https://img.aikorea24.kr"),
    "kuta": ("images/kuta", "https://img-kuta.informationhot.kr"),
    "techpawz-hugo": ("images/techpawz", "https://img.techpawz.com"),
}

CONTENT_TYPES = {
    ".webp": "image/webp",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
}


# ── R2 클라이언트 ──

def get_r2_client():
    """R2 S3 클라이언트 생성 (환경변수 미설정 시 None 반환)"""
    if not all([R2_ENDPOINT_URL, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY]):
        return None
    return boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT_URL,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


def get_r2_config(site_path: str) -> tuple:
    """사이트 경로에서 R2 prefix와 도메인 반환"""
    for key, (prefix, domain) in HUGO_R2_DOMAINS.items():
        if key in site_path:
            return prefix, domain
    return None, None


# ── 포맷 검증 ──

def _validate_image_format(file_path: Path) -> bool:
    """파일의 실제 포맷과 확장자가 일치하는지 검증"""
    _magic_map = {
        b"\xff\xd8\xff":       (".jpg", ".jpeg"),
        b"\x89PNG":             (".png",),
        b"RIFF":                 (".webp",),
        b"GIF8":                 (".gif",),
    }
    try:
        with open(file_path, "rb") as _f:
            _header = _f.read(4)
        _suffix = file_path.suffix.lower()
        for _magic, _exts in _magic_map.items():
            if _header.startswith(_magic):
                if _suffix not in _exts:
                    print(f"[R2] ⚠️ 포맷 불일치: {file_path.name} — 헤더={_header.hex()} 확장자={_suffix}")
                    return False
                return True
        return True
    except Exception:
        return True


# ── 메인 업로더 ──

def upload_all_images(post_dir: Path, slug: str, r2_prefix: str, r2_domain: str) -> dict:
    """
    포스트 이미지를 R2에 업로드하고 {로컬파일명: R2 URL} 반환

    지원하는 썸네일 패턴:
      1. thumbnail.webp / cover.webp / thumbnail.png (레거시)
      2. thumb_*.webp / thumb_*.jpg (새 패턴, assets/ 하위)
    """
    client = get_r2_client()
    if not client:
        return {}

    url_map = {}

    def _upload(file_path, r2_key):
        try:
            format_ok = _validate_image_format(file_path)
            if not format_ok:
                print(f"[R2] ⚠️ 포맷 불일치에도 업로드 진행: {r2_key}")

            ct = CONTENT_TYPES.get(file_path.suffix.lower(), "application/octet-stream")
            client.upload_file(str(file_path), R2_BUCKET_NAME, r2_key, ExtraArgs={"ContentType": ct})

            try:
                client.head_object(Bucket=R2_BUCKET_NAME, Key=r2_key)
            except Exception:
                print(f"[R2] ⚠️ 업로드 후 검증 실패 (파일 없음): {r2_key}")
                return None

            return f"{r2_domain}/{r2_key}"
        except Exception as e:
            print(f"[R2] failed {r2_key}: {e}")
            return None

    # ── 썸네일 (레거시): thumbnail.webp / cover.webp / thumbnail.png ──
    for thumb_name in ["thumbnail.webp", "cover.webp", "thumbnail.png"]:
        thumb = post_dir / thumb_name
        if thumb.exists():
            r2_key = f"{r2_prefix}/{slug}/{thumb_name}"
            url = _upload(thumb, r2_key)
            if url:
                url_map[thumb_name] = url
            break

    # ── 썸네일 (새 패턴): assets/thumb_*.webp / thumb_*.jpg ──
    if not any(k.startswith("thumb") for k in url_map):
        assets_dir = post_dir / "assets"
        if assets_dir.exists():
            for pattern in ["*.webp", "*.jpg", "*.jpeg"]:
                for thumb in assets_dir.glob(pattern):
                    if "thumb" in thumb.name.lower():
                        r2_key = f"{r2_prefix}/{slug}/{thumb.name}"
                        url = _upload(thumb, r2_key)
                        if url:
                            url_map[thumb.name] = url
                            break
                if any(k.startswith("thumb") for k in url_map):
                    break

    # ── assets 폴더 전체 ──
    assets_dir = post_dir / "assets"
    if assets_dir.exists():
        for f in assets_dir.iterdir():
            if f.is_file() and f.suffix.lower() in CONTENT_TYPES:
                r2_key = f"{r2_prefix}/{slug}/{f.name}"
                url = _upload(f, r2_key)
                if url:
                    url_map[f.name] = url

    return url_map


def upload_thumbnail_to_r2(post_dir: Path, r2_prefix: str = "thumbnails", r2_domain: str = None) -> Tuple[bool, Optional[str]]:
    """썸네일만 R2에 업로드"""
    if not r2_domain:
        r2_domain = R2_PUBLIC_URL

    client = get_r2_client()
    if not client:
        return False, "R2 클라이언트 생성 실패"

    for thumb_name in ["thumbnail.webp", "cover.webp", "thumbnail.png"]:
        thumb = post_dir / thumb_name
        if thumb.exists():
            r2_key = f"{r2_prefix}/{post_dir.name}{thumb.suffix}"
            try:
                ct = CONTENT_TYPES.get(thumb.suffix.lower(), "image/webp")
                client.upload_file(str(thumb), R2_BUCKET_NAME, r2_key, ExtraArgs={"ContentType": ct})
                return True, f"{r2_domain}/{r2_key}"
            except Exception as e:
                return False, str(e)

    return False, "썸네일 없음"


def check_r2_connection() -> Tuple[bool, str]:
    """R2 연결 상태 확인"""
    client = get_r2_client()
    if not client:
        return False, "R2 클라이언트 생성 실패 (환경변수 확인)"
    try:
        client.head_bucket(Bucket=R2_BUCKET_NAME)
        return True, f"R2 연결 성공: {R2_BUCKET_NAME}"
    except Exception as e:
        return False, f"R2 연결 실패: {e}"
