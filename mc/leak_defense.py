"""
mc/leak_defense.py — 통합 릭 방어 모듈 (Phase 22)

config/leak_defense.yaml 기반으로 모든 프롬프트 릭, CTA 릭, 플레이스홀더 릭,
HTML 태그 릭, JSON 릭을 통합 처리합니다.

기존 4개 파일의 개별 leak 방어 호출을 이 모듈로 교체:
- chain_drafter.py::_strip_prompt_leak()
- chain_publisher_core.py::D8-GATE CTA/placeholder 스캐너
- audit/audit_chain.py::check_prompt_leak(), check_cta_leak()
- conftest.py::assert_no_prompt_leak(), assert_no_cta_leak()
"""

import re
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional

import yaml

logger = logging.getLogger(__name__)


# ── 설정 로드 ───────────────────────────────────────────────────────

def _load_leak_patterns() -> Dict[str, Any]:
    """config/leak_defense.yaml 로드"""
    path = Path(__file__).resolve().parent.parent / "config" / "leak_defense.yaml"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


_LEAK_CONFIG = _load_leak_patterns()


# ── 패턴 컴파일 ──────────────────────────────────────────────────────

def _compile_patterns(patterns: List[str]) -> List[re.Pattern]:
    """문자열 패턴 리스트를 컴파일된 regex 리스트로 변환"""
    return [re.compile(p, re.MULTILINE) for p in patterns]


_PROMPT_LEAK_PATTERNS = _compile_patterns(_LEAK_CONFIG.get("prompt_leak", {}).get("patterns", []))
_CTA_LEAK_PATTERNS = _compile_patterns(_LEAK_CONFIG.get("cta_leak", {}).get("patterns", []))
_FORBIDDEN_CTA_PATTERNS = _compile_patterns(_LEAK_CONFIG.get("cta_leak", {}).get("forbidden_cta", []))
_PLACEHOLDER_PATTERN = re.compile(_LEAK_CONFIG.get("placeholder_leak", {}).get("pattern", r'\{\{(?!<|%)([^}]+)\}\}'))
_HTML_TAGS = _LEAK_CONFIG.get("html_tag_leak", {}).get("tags", [])
_JSON_LEAK_PATTERN = re.compile(_LEAK_CONFIG.get("json_leak", {}).get("pattern", r'(?<!`)\n\s*\{\s*"(?:image_type|chart_type|image_keyword)"'))


# ── 핵심 함수 ────────────────────────────────────────────────────────

def strip_leaks(text: str, context: str = "body") -> Tuple[str, Dict[str, Any]]:
    """
    통합 릭 제거 함수.

    Args:
        text: 원본 텍스트
        context: "draft" | "body" | "html" | "test" — 컨텍스트별 규칙 적용

    Returns:
        (cleaned_text, report_dict)
        report_dict: {
            "prompt_leak": {"removed": int, "matches": [...]},
            "cta_leak": {"removed": int, "matches": [...]},
            "placeholder_leak": {"removed": int, "matches": [...]},
            "html_leak": {"removed": int, "matches": [...]},
            "json_leak": {"removed": int, "matches": [...]},
        }
    """
    if not text:
        return text, _empty_report()

    report = _empty_report()
    cleaned = text

    # 1. Prompt leak 제거 (context: "draft"에서만)
    if context in ("draft", "test"):
        cleaned, prompt_report = _remove_prompt_leaks(cleaned)
        report["prompt_leak"] = prompt_report

    # 2. CTA leak 제거 (context: "body", "test"에서)
    if context in ("body", "test"):
        cleaned, cta_report = _remove_cta_leaks(cleaned)
        report["cta_leak"] = cta_report

    # 3. Placeholder leak 제거 (모든 context)
    cleaned, placeholder_report = _remove_placeholders(cleaned)
    report["placeholder_leak"] = placeholder_report

    # 4. HTML tag leak 제거 (context: "html", "test"에서)
    if context in ("html", "test"):
        cleaned, html_report = _remove_html_tags(cleaned)
        report["html_leak"] = html_report

    # 5. JSON leak 제거 (context: "draft", "body", "test"에서)
    if context in ("draft", "body", "test"):
        cleaned, json_report = _remove_json_leaks(cleaned)
        report["json_leak"] = json_report

    return cleaned, report


def has_leaks(text: str, context: str = "test") -> bool:
    """릭 존재 여부만 검사 (제거하지 않음)"""
    if not text:
        return False

    # Prompt leak
    if context in ("draft", "test"):
        for pattern in _PROMPT_LEAK_PATTERNS:
            if pattern.search(text):
                return True

    # CTA leak
    if context in ("body", "test"):
        for pattern in _CTA_LEAK_PATTERNS:
            if pattern.search(text):
                return True
        for pattern in _FORBIDDEN_CTA_PATTERNS:
            if pattern.search(text):
                return True

    # Placeholder
    if _PLACEHOLDER_PATTERN.search(text):
        return True

    # HTML tags
    if context in ("html", "test"):
        for tag in _HTML_TAGS:
            if re.search(rf'<{tag}[\s>]', text):
                return True

    # JSON
    if context in ("draft", "body", "test"):
        if _JSON_LEAK_PATTERN.search(text):
            return True

    return False


# ── 내부 헬퍼 ────────────────────────────────────────────────────────

def _empty_report() -> Dict[str, Any]:
    return {
        "prompt_leak": {"removed": 0, "matches": []},
        "cta_leak": {"removed": 0, "matches": []},
        "placeholder_leak": {"removed": 0, "matches": []},
        "html_leak": {"removed": 0, "matches": []},
        "json_leak": {"removed": 0, "matches": []},
    }


def _remove_prompt_leaks(text: str) -> Tuple[str, Dict[str, Any]]:
    """Prompt leak 패턴 제거 (헤더 블록 단위)"""
    lines = text.splitlines(keepends=True)
    out = []
    in_frontmatter = False
    past_frontmatter = False
    skip_block = False
    removed = 0
    matches = []

    for ln in lines:
        stripped = ln.strip()
        if stripped == "---":
            if not in_frontmatter and not past_frontmatter:
                in_frontmatter = True
            elif in_frontmatter:
                in_frontmatter = False
                past_frontmatter = True
            out.append(ln)
            skip_block = False
            continue
        if in_frontmatter or not past_frontmatter:
            out.append(ln)
            continue

        if skip_block:
            if stripped.startswith("#") and not any(p.match(stripped) for p in _PROMPT_LEAK_PATTERNS):
                skip_block = False
                out.append(ln)
            continue

        matched = False
        for pattern in _PROMPT_LEAK_PATTERNS:
            if pattern.match(stripped):
                matched = True
                matches.append({"pattern": pattern.pattern, "match": stripped[:50], "action": "block_removed"})
                removed += 1
                break

        if matched:
            if stripped.startswith("#"):
                skip_block = True
            continue

        out.append(ln)

    return "".join(out), {"removed": removed, "matches": matches}


def _remove_cta_leaks(text: str) -> Tuple[str, Dict[str, Any]]:
    """CTA leak 패턴 제거"""
    cleaned = text
    removed = 0
    matches = []

    # 일반 CTA 패턴
    for pattern in _CTA_LEAK_PATTERNS:
        for m in pattern.finditer(cleaned):
            matches.append({"pattern": pattern.pattern, "match": m.group(), "position": m.start(), "type": "cta"})
            removed += 1

    # 금지 CTA 패턴 (더 강한 로깅)
    for pattern in _FORBIDDEN_CTA_PATTERNS:
        for m in pattern.finditer(cleaned):
            matches.append({"pattern": pattern.pattern, "match": m.group(), "position": m.start(), "type": "forbidden_cta"})
            removed += 1
            logger.warning(f"[LEAK] 금지 CTA 감지: '{m.group()}' @ pos {m.start()}")

    # 제거 (일반 + 금지)
    for pattern in _CTA_LEAK_PATTERNS + _FORBIDDEN_CTA_PATTERNS:
        cleaned = pattern.sub('', cleaned)

    return cleaned, {"removed": removed, "matches": matches}


def _remove_placeholders(text: str) -> Tuple[str, Dict[str, Any]]:
    """플레이스홀더 {{...}} 제거 (shortcode {{< >}} 제외)"""
    cleaned = text
    removed = 0
    matches = []

    for m in _PLACEHOLDER_PATTERN.finditer(cleaned):
        matches.append({"match": m.group(), "position": m.start(), "inner": m.group(1)})
        removed += 1

    cleaned = _PLACEHOLDER_PATTERN.sub('', cleaned)

    return cleaned, {"removed": removed, "matches": matches}


def _remove_html_tags(text: str) -> Tuple[str, Dict[str, Any]]:
    """허용되지 않은 HTML 태그 제거 (블록 단위)"""
    cleaned = text
    removed = 0
    matches = []

    for tag in _HTML_TAGS:
        # <tag ...> ... </tag> 블록 전체 제거
        pattern = re.compile(rf'<{tag}[^>]*>.*?</{tag}>', re.DOTALL | re.IGNORECASE)
        for m in pattern.finditer(cleaned):
            matches.append({"tag": tag, "match": m.group()[:100], "position": m.start()})
            removed += 1

        # 단일 태그 <tag .../> 도 제거
        pattern2 = re.compile(rf'<{tag}[^>]*/>', re.IGNORECASE)
        for m in pattern2.finditer(cleaned):
            matches.append({"tag": tag, "match": m.group()[:100], "position": m.start()})
            removed += 1

        cleaned = pattern.sub('', cleaned)
        cleaned = pattern2.sub('', cleaned)

    return cleaned, {"removed": removed, "matches": matches}


def _remove_json_leaks(text: str) -> Tuple[str, Dict[str, Any]]:
    """Raw JSON 객체 제거 (image_type, chart_type 포함)"""
    cleaned = text
    removed = 0
    matches = []

    for m in _JSON_LEAK_PATTERN.finditer(cleaned):
        matches.append({"match": m.group()[:100], "position": m.start()})
        removed += 1

    cleaned = _JSON_LEAK_PATTERN.sub('', cleaned)

    return cleaned, {"removed": removed, "matches": matches}


# ── 설정 리로드 (테스트용) ──────────────────────────────────────────

def reload_config() -> None:
    """leak_defense.yaml 재로드"""
    global _LEAK_CONFIG, _PROMPT_LEAK_PATTERNS, _CTA_LEAK_PATTERNS
    global _FORBIDDEN_CTA_PATTERNS, _PLACEHOLDER_PATTERN
    global _HTML_TAGS, _JSON_LEAK_PATTERN

    _LEAK_CONFIG = _load_leak_patterns()
    _PROMPT_LEAK_PATTERNS = _compile_patterns(_LEAK_CONFIG.get("prompt_leak", {}).get("patterns", []))
    _CTA_LEAK_PATTERNS = _compile_patterns(_LEAK_CONFIG.get("cta_leak", {}).get("patterns", []))
    _FORBIDDEN_CTA_PATTERNS = _compile_patterns(_LEAK_CONFIG.get("cta_leak", {}).get("forbidden_cta", []))
    _PLACEHOLDER_PATTERN = re.compile(_LEAK_CONFIG.get("placeholder_leak", {}).get("pattern", r'\{\{(?!<|%)([^}]+)\}\}'))
    _HTML_TAGS = _LEAK_CONFIG.get("html_tag_leak", {}).get("tags", [])
    _JSON_LEAK_PATTERN = re.compile(_LEAK_CONFIG.get("json_leak", {}).get("pattern", r'(?<!`)\n\s*\{\s*"(?:image_type|chart_type|image_keyword)"'))