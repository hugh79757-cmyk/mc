"""
chain_models.py — 파이프라인 계약 모델 (3개 계약의 기반)

계약 1: AIOutput   — AI 출력의 단일 파싱 진입점 + 스키마 검증
계약 2: CleanedDraft — 흰색 목록 기반 본문 추출
계약 3: ImageMeta   — 이미지 메타데이터 단일 객체
"""

from __future__ import annotations

import re
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Literal, List, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ── 예외 계층 ──────────────────────────────────────────────────────

class PipelineError(Exception):
    pass


class AIParseError(PipelineError):
    """AI 출력에서 JSON 파싱 실패 또는 스키마 검증 실패"""
    pass


class BodyExtractionError(PipelineError):
    """흰색 목록 본문 추출 실패 — 허용되지 않은 요소 발견"""
    pass


class DeployValidationError(PipelineError):
    """배포 전 검증 실패 — 배포 중단"""
    pass


class ImageGenerationError(PipelineError):
    """이미지 생성 외부 호출 실패"""
    pass


# ── Result 타입 (외부 호출 실패 모델링) ─────────────────────────────

class ErrorCategory(Enum):
    TRANSIENT = "transient"
    PERMANENT = "permanent"
    RATE_LIMITED = "rate_limited"


@dataclass(frozen=True)
class Error:
    category: ErrorCategory
    message: str
    source: str


@dataclass(frozen=True)
class Result:
    ok: bool
    value: Any = None
    error: Optional[Error] = None

    @classmethod
    def success(cls, value: Any) -> Result:
        return cls(ok=True, value=value)

    @classmethod
    def failure(cls, category: ErrorCategory, message: str, source: str = "") -> Result:
        return cls(ok=False, error=Error(category=category, message=message, source=source))


# ── 계약 1: AIOutput ──────────────────────────────────────────────

class AIOutputMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image_type: Literal["chart", "photo", "none"] = "none"
    image_keyword: Optional[str] = None
    image_reason: Optional[str] = None
    chart_type: Optional[str] = None
    chart_data: Optional[Any] = None

    @field_validator("image_keyword")
    @classmethod
    def require_keyword_for_photo(cls, v: str | None, info) -> str | None:
        if info.data.get("image_type") == "photo" and not v:
            raise ValueError(
                "image_type='photo'일 때 image_keyword는 필수입니다. "
                "slug fallback은 허용되지 않습니다."
            )
        return v

    @field_validator("chart_type", "chart_data")
    @classmethod
    def require_chart_fields(cls, v: Any, info) -> Any:
        if info.data.get("image_type") == "chart":
            field_name = info.field_name
            if v is None:
                # Phase 19: lenient — null chart fields force fallback to "none"
                # rather than raising (which bypasses body cleaning).
                # Downstream (chain_drafter.py) already handles this via
                # image_type="none" fallback.
                pass
        return v


class AIOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: str = Field(min_length=1, description="JSON이 완전히 제거된 깨끗한 마크다운")
    meta: AIOutputMeta = Field(default_factory=AIOutputMeta)


# ── 계약 2: CleanedDraft ──────────────────────────────────────────

class CleanedDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    frontmatter: str = ""
    body: str = Field(min_length=1)


# ── 계약 3: ImageMeta ────────────────────────────────────────────

class ImageMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image_type: Literal["chart", "photo", "none"] = "none"
    image_keyword: Optional[str] = None
    image_url: Optional[str] = None
    thumbnail_path: Optional[str] = None
    thumbnail_source: Optional[str] = None
    thumbnail_r2_url: Optional[str] = None
    thumbnail_path: Optional[str] = None
    content_image_path: Optional[str] = None
    content_image_source: Optional[str] = None
    chart_type: Optional[str] = None
    chart_data: Optional[Any] = None
    image_reason: Optional[str] = None

    def is_complete(self) -> bool:
        if self.image_type == "photo":
            return bool(self.image_keyword)
        if self.image_type == "chart":
            return bool(self.chart_type and self.chart_data)
        return True


# ── 공통 헬퍼: JSON 블록 탐지 (중괄호 깊이 카운팅) ────────────────

def _find_json_blocks(text: str, max_lookback: int = 2000) -> List[Tuple[int, int, dict]]:
    """
    text에서 중괄호 깊이 카운팅으로 JSON 블록을 탐지.
    "image_type" 또는 "chart_type" 키를 포함하는 유효한 JSON 객체만 반환.

    Returns:
        List of (start_idx, end_idx, parsed_dict) — end_idx는 exclusive.
        텍스트에서 등장하는 순서대로 정렬됨 (첫 번째 → 마지막).
    """
    blocks = []
    i = 0
    while i < len(text):
        if text[i] == '{':
            depth = 0
            start = i
            # 순방향으로 중괄호 매칭 (최대 max_lookback 문자까지)
            for j in range(i, min(len(text), i + max_lookback)):
                if text[j] == '{':
                    depth += 1
                elif text[j] == '}':
                    depth -= 1
                    if depth == 0:
                        candidate = text[start:j + 1]
                        if '"image_type"' in candidate or '"chart_type"' in candidate:
                            try:
                                parsed = json.loads(candidate)
                                if isinstance(parsed, dict):
                                    blocks.append((start, j + 1, parsed))
                            except (json.JSONDecodeError, TypeError):
                                pass
                        break
            i = j + 1
        else:
            i += 1
    return blocks


# ── 파싱 함수: AI 출력의 단일 진입점 ──────────────────────────────

def _extract_meta_from_raw(raw: str) -> dict:
    """raw에서 JSON 메타데이터를 추출하여 dict로 반환"""
    # 1. 코드펜스 패턴 (기존 유지 — 하위호환)
    patterns = [
        r'```json\s*\n(.*?)\n```',
        r'```json\s*\n(.*?)$',
        r'```\s*\n(.*?)\n```',
    ]

    for pattern in patterns:
        m = re.search(pattern, raw, re.DOTALL)
        if m:
            try:
                parsed = json.loads(m.group(1))
                if isinstance(parsed, dict) and ("image_type" in parsed or "chart_type" in parsed):
                    return parsed
            except (json.JSONDecodeError, TypeError):
                continue

    # 2. 중괄호 깊이 카운팅으로 평문/들여쓰기/다중라인 JSON 탐지 (500→2000자 확대)
    blocks = _find_json_blocks(raw, max_lookback=2000)
    if blocks:
        # 첫 번째 유효 메타만 사용 (나머지는 본문 잔류 → 2차 방어로 처리)
        return blocks[0][2]

    return {}


_FM_KEYS = ("title:", "draft:", "categories:", "tags:", "description:",
            "featureimage:", "slug:", "date:", "cover:")


def _strip_all_fm_blocks(text: str) -> str:
    """본문 어디에 있든 FM 키를 포함한 ---...--- 블록을 모두 제거(hr은 보존)."""
    lines = text.split("\n")
    out, i = [], 0
    while i < len(lines):
        if lines[i].strip() == "---":
            j, block, found = i + 1, [], False
            while j < len(lines):
                if lines[j].strip() == "---":
                    found = True
                    break
                block.append(lines[j])
                j += 1
            if found and any(any(k in b for k in _FM_KEYS) for b in block):
                i = j + 1
                continue
        out.append(lines[i])
        i += 1
    return "\n".join(out).lstrip("\n")


def _extract_body_from_raw(raw: str) -> str:
    """raw에서 JSON 코드블록 및 raw JSON을 제거한 깨끗한 본문만 추출"""

    # Phase 24: AI가 출력한 FM 블록(---로 열고 닫힘) 제거
    # AI가 프롬프트 지시를 무시하고 FM을 출력한 경우 대비
    cleaned = _strip_all_fm_blocks(raw)

    # 1. 코드펜스 JSON 제거 (기존 유지 — 하위호환)
    cleaned = re.sub(
        r'```json\s*\n?\{.*?\}\s*\n?```',
        '', cleaned, flags=re.DOTALL
    )
    cleaned = re.sub(
        r'```json\s*\n?\{.*?\}\s*$',
        '', cleaned, flags=re.DOTALL
    )
    cleaned = re.sub(
        r'```\s*\n?\{.*?\}\s*\n?```',
        '', cleaned, flags=re.DOTALL
    )

    # 2. 중괄호 깊이 카운팅으로 평문/들여쓰기/다중라인 JSON 블록 모두 제거
    # 탐지된 블록 위치를 리스트에 모아 역순으로 삭제(인덱스 시프트 방지)
    blocks = _find_json_blocks(cleaned, max_lookback=2000)
    # 역순으로 삭제
    for start, end, _ in sorted(blocks, key=lambda x: x[0], reverse=True):
        cleaned = cleaned[:start] + cleaned[end:]

    # 3. 플레이스홀더/개행 정리 (기존 유지)
    cleaned = re.sub(r'<!--\s*(thumbnail|image)\s*:\s*.*?-->', '', cleaned)
    cleaned = re.sub(r'<!--\s*todo:\s*(image|chart)\s*-->', '', cleaned)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)

    return cleaned.strip()


def parse_ai_output(raw: str) -> AIOutput:
    """
    AI 출력의 단일 파싱 진입점.

    1. JSON 메타데이터를 추출하여 AIOutputMeta 스키마로 검증
    2. 본문에서 JSON/HTML 주석/플레이스홀더를 완전히 제거
    3. AIOutput을 반환 (body가 비어있으면 AIParseError)

    Raises:
        AIParseError: 본문이 비어있을 때 (스키마 검증 실패 시 폴백)
    """
    meta_dict = _extract_meta_from_raw(raw)

    meta: AIOutputMeta
    if meta_dict:
        try:
            meta = AIOutputMeta(**meta_dict)
        except Exception:
            # 스키마 검증 실패 시 폴백: 기본 메타 사용, 본문은 원문 유지 (2차 방어에서 처리)
            meta = AIOutputMeta()
    else:
        meta = AIOutputMeta()

    body = _extract_body_from_raw(raw)

    if not body.strip():
        raise AIParseError("AI 출력 본문이 비어있습니다")

    return AIOutput(body=body, meta=meta)