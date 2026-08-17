"""Reusable thumbnail quality gates, hashing, manifest, and duplicate checks."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from PIL import Image, ImageStat


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def quality_issues(path: Path, expected_size=(1024, 1024), min_bytes=15 * 1024) -> list[str]:
    issues: list[str] = []
    if not path.exists():
        return ["missing_file"]
    if path.stat().st_size < min_bytes:
        issues.append("too_small")
    try:
        with Image.open(path) as image:
            image.load()
            if image.format != "WEBP":
                issues.append("wrong_format")
            if image.size != tuple(expected_size):
                issues.append("wrong_dimensions")
            rgb = image.convert("RGB")
            luma = ImageStat.Stat(rgb.convert("L")).mean[0]
            saturation = ImageStat.Stat(rgb.convert("HSV")).mean[1]
            if luma < 52:
                issues.append("too_dark")
            if saturation < 16:
                issues.append("low_saturation")
    except Exception:
        issues.append("invalid_image")
    return issues


def duplicate_hash(path: Path, library_root: Path) -> str | None:
    digest = sha256_file(path)
    for candidate in library_root.glob("thumb_*"):
        if candidate.resolve() == path.resolve() or not candidate.is_file():
            continue
        try:
            if sha256_file(candidate) == digest:
                return str(candidate)
        except OSError:
            continue
    return None


def append_manifest(path: Path, *, slug: str, provider: str, query: str, source_url: str = "", provider_asset_id: str = "", issues=None) -> dict[str, Any]:
    record = {
        "slug": slug,
        "thumbnail_path": str(path),
        "provider": provider,
        "provider_asset_id": provider_asset_id,
        "query": query,
        "source_url": source_url,
        "sha256": sha256_file(path) if path.exists() else "",
        "is_placeholder": False,
        "quality_passed": not issues,
        "quality_issues": issues or [],
    }
    manifest = path.parent / "thumbnail_manifest.jsonl"
    with manifest.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def semantic_issues(query: str, asset: dict) -> list[str]:
    text = str(query or '').lower()
    alt = str((asset or {}).get('alt') or '').lower()
    event_terms = ['festival', 'event', 'exhibition', 'pokemon', '', '', '']
    generic_terms = ['landscape', 'mountain', 'nature', 'scenery', 'monochrome', 'sky']
    if any(term in text for term in ['', '', '', 'festival', 'event', 'exhibition']):
        if any(term in alt for term in generic_terms) and not any(term in alt for term in event_terms):
            return ['semantic_mismatch_event_generic_scenery']
    return []

def validate_thumbnail(path: Path, *, slug: str, provider: str, query: str, asset: dict | None = None, expected_size=(1024, 1024)) -> tuple[bool, list[str], dict]:
    issues = quality_issues(path, expected_size=expected_size)
    asset = asset or {}
    issues.extend(semantic_issues(query, asset))
    duplicate = duplicate_hash(path, path.parent) if not issues else None
    if duplicate:
        issues.append("duplicate_hash")
    record = append_manifest(
        path,
        slug=slug,
        provider=provider,
        query=query,
        source_url=str(asset.get("url") or asset.get("url_raw") or asset.get("url_original") or ""),
        provider_asset_id=str(asset.get("id") or ""),
        issues=issues,
    )
    return not issues, issues, record
