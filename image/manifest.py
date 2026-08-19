"""
manifest — 썸네일 생성 이력 JSONL 관리

data/thumbnails/manifest.jsonl에 구조화된 생성 기록을 append한다.
used_images DB(실시간 dedup)와 병행 운영: manifest는 감사용, DB는 실시간 dedup용.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

MANIFEST_PATH = Path("data/thumbnails/manifest.jsonl")


def _ensure_manifest_dir():
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)


def compute_sha256(file_path: Path) -> str:
    """파일의 SHA-256 해시를 계산한다."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def append_manifest(
    slug: str,
    thumbnail_path: str,
    provider: str,
    provider_asset_id: str,
    query: str,
    sha256: str,
    *,
    is_placeholder: bool = False,
    source_url: str = "",
) -> None:
    """
    manifest.jsonl에 생성 기록을 append한다.

    Args:
        slug: 포스트 슬러그
        thumbnail_path: 생성된 썸네일 파일 경로
        provider: 이미지 provider (unsplash/pexels)
        provider_asset_id: provider 제공 photo ID
        query: 검색에 사용된 쿼리
        sha256: 생성된 파일의 SHA-256 해시
        is_placeholder: 플레이스홀더 이미지 여부
        source_url: 원본 소스 URL (선택)
    """
    _ensure_manifest_dir()

    record = {
        "slug": slug,
        "thumbnail_path": thumbnail_path,
        "provider": provider,
        "provider_asset_id": provider_asset_id,
        "query": query,
        "sha256": sha256,
        "is_placeholder": is_placeholder,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if source_url:
        record["source_url"] = source_url

    # 파일 잠금으로 병렬 쓰기 충돌 방지
    lock_path = MANIFEST_PATH.with_suffix(".lock")
    lock_fd = None
    try:
        lock_fd = open(lock_path, "w")
        fcntl.flock(lock_fd, fcntl.LOCK_EX)

        existing = ""
        if MANIFEST_PATH.exists():
            try:
                existing = MANIFEST_PATH.read_text(encoding="utf-8")
            except OSError:
                existing = ""

        temp_path = MANIFEST_PATH.with_suffix(MANIFEST_PATH.suffix + ".tmp")
        try:
            temp_path.write_text(
                existing + json.dumps(record, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            os.replace(temp_path, MANIFEST_PATH)
            logger.debug(f"[manifest] append: {slug} ({provider}:{provider_asset_id})")
        except OSError as exc:
            logger.warning(f"[manifest] 기록 실패: {exc}")
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
    finally:
        if lock_fd:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                lock_fd.close()
            except OSError:
                pass


def slug_exists_in_manifest(slug: str) -> bool:
    """manifest에 해당 slug가 존재하는지 확인한다 (멱등성 체크용)."""
    if not MANIFEST_PATH.exists():
        return False
    try:
        with open(MANIFEST_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    if rec.get("slug") == slug:
                        return True
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return False
