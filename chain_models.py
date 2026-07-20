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
from typing import Any, Optional, Literal

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
                raise ValueError(
                    f"image_type='chart'일 때 {field_name}은 필수입니다."
                )
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


# ── 파싱 함수: AI 출력의 단일 진입점 ──────────────────────────────

def _extract_body_from_raw(raw: str) -> str:
    """raw에서 JSON 코드블록 및 raw JSON을 제거한 깨끗한 본문만 추출"""

    cleaned = raw

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

    for p in range(len(cleaned) - 1, -1, -1):
        if cleaned[p] == '}':
            depth = 0
            for q in range(p, max(0, p - 500), -1):
                if cleaned[q] == '}':
                    depth += 1
                elif cleaned[q] == '{':
                    depth -= 1
                    if depth == 0:
                        candidate = cleaned[q:p + 1]
                        if '"image_type"' in candidate or '"chart_type"' in candidate:
                            cleaned = cleaned[:q]
                        break
            break

    cleaned = re.sub(r'<!--\s*(thumbnail|image)\s*:\s*.*?-->', '', cleaned)
    cleaned = re.sub(r'<!--\s*todo:\s*(image|chart)\s*-->', '', cleaned)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)

    return cleaned.strip()


def _extract_meta_from_raw(raw: str) -> dict:
    """raw에서 JSON 메타데이터를 추출하여 dict로 반환"""
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

    for p in range(len(raw) - 1, -1, -1):
        if raw[p] == '}':
            depth = 0
            for q in range(p, max(0, p - 500), -1):
                if raw[q] == '}':
                    depth += 1
                elif raw[q] == '{':
                    depth -= 1
                    if depth == 0:
                        candidate = raw[q:p + 1]
                        if '"image_type"' in candidate or '"chart_type"' in candidate:
                            try:
                                parsed = json.loads(candidate)
                                if isinstance(parsed, dict):
                                    return parsed
                            except (json.JSONDecodeError, TypeError):
                                pass
                        break
            break

    return {}


def parse_ai_output(raw: str) -> AIOutput:
    """
    AI 출력의 단일 파싱 진입점.

    1. JSON 메타데이터를 추출하여 AIOutputMeta 스키마로 검증
    2. 본문에서 JSON/HTML 주석/플레이스홀더를 완전히 제거
    3. AIOutput을 반환 (body가 비어있으면 AIParseError)

    Raises:
        AIParseError: 스키마 검증 실패 또는 본문이 비어있을 때
    """
    meta_dict = _extract_meta_from_raw(raw)

    meta: AIOutputMeta
    if meta_dict:
        try:
            meta = AIOutputMeta(**meta_dict)
        except Exception as e:
            raise AIParseError(
                f"AI 메타데이터 스키마 검증 실패: {e}\n"
                f"원본 JSON: {json.dumps(meta_dict, ensure_ascii=False, indent=2)}"
            )
    else:
        meta = AIOutputMeta()

    body = _extract_body_from_raw(raw)

    if not body.strip():
        raise AIParseError("AI 출력 본문이 비어있습니다")

    return AIOutput(body=body, meta=meta)
