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

_REASONING_LEAK_CONFIG = _LEAK_CONFIG.get("reasoning_leak", {})
_REASONING_PATTERNS = _compile_patterns(_REASONING_LEAK_CONFIG.get("patterns", []))
_REASONING_MIN_SIGNALS = _REASONING_LEAK_CONFIG.get("min_signals", 2)
_HTML_TAGS = _LEAK_CONFIG.get("html_tag_leak", {}).get("tags", [])
_JSON_LEAK_PATTERN = re.compile(_LEAK_CONFIG.get("json_leak", {}).get("pattern", r'(?<!`)\n\s*\{\s*"(?:image_type|chart_type|image_keyword)"'))


# ── 공개 상수 (Phase 26: 상수 모듈 연동) ────────────────────────────────
# 릭 패턴의 단일 진실 공급원은 config/leak_defense.yaml 이다 (reload_config()
# 로 재로드). LEAK_PATTERNS / LEAK_REGEX 는 상수 모듈 소비자(테스트 등)와
# `from leak_defense import LEAK_PATTERNS` 호환을 위한 공개 파생 값이며,
# reload_config() 에서 함께 갱신된다.

LEAK_PATTERNS: List[str] = (
_LEAK_CONFIG.get("prompt_leak", {}).get("patterns", [])
    + _LEAK_CONFIG.get("cta_leak", {}).get("patterns", [])
    + _LEAK_CONFIG.get("cta_leak", {}).get("forbidden_cta", [])
    + _LEAK_CONFIG.get("reasoning_leak", {}).get("patterns", [])
)
LEAK_REGEX: List[re.Pattern] = _compile_patterns(LEAK_PATTERNS)


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

    # 1.5 Reasoning leak 문단 단위 제거 (context: "body", "test"에서)
    if context in ("body", "test"):
        cleaned, reasoning_report = _remove_reasoning_leaks_paragraph(cleaned)
        report["reasoning_leak"] = reasoning_report

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
        "reasoning_leak": {"removed": 0, "matches": []},
        "cta_leak": {"removed": 0, "matches": []},
        "placeholder_leak": {"removed": 0, "matches": []},
        "html_leak": {"removed": 0, "matches": []},
        "json_leak": {"removed": 0, "matches": []},
    }


def _remove_reasoning_leaks_paragraph(text: str) -> Tuple[str, Dict[str, Any]]:
    """
    문단 단위 reasoning leak 제거.

    동일 문단 내에 고특이도 reasoning leak 시그니처가 min_signals(기본 2)개
    이상 동시 출현 시 그 문단 전체를 제거한다.
    문단 경계는 빈 줄로 정의. 표/코드블록/리스트/헤더는 문단으로 간주하지 않음.
    """
    if _REASONING_MIN_SIGNALS <= 1:
        return text, {"removed": 0, "matches": []}

    lines = text.splitlines(keepends=True)
    out = []
    in_frontmatter = False
    past_frontmatter = False
    removed = 0
    matches = []

    # 문단 단위 처리를 위해 먼저 문단별로 분리
    paragraphs = []
    current_paragraph = []
    in_frontmatter = False
    past_frontmatter = False

    in_code_block = False

    for ln in lines:
        stripped = ln.strip()

        if stripped == "---":
            if not in_frontmatter and not past_frontmatter:
                in_frontmatter = True
            elif in_frontmatter:
                in_frontmatter = False
                past_frontmatter = True
            if current_paragraph:
                paragraphs.append((current_paragraph, "frontmatter"))
                current_paragraph = []
            continue

        # 빈 줄 = 문단 경계 (코드 블록 내부에서는 무시)
        if not stripped and not in_code_block:
            if current_paragraph:
                paragraphs.append((current_paragraph, "content"))
                current_paragraph = []
            continue

        # 코드 블록 토글
        if stripped.startswith("```"):
            if in_code_block:
                # 코드 블록 종료 - 보호된 라인으로만 추가 (내용은 버림)
                paragraphs.append(([ln], "protected"))
                in_code_block = False
                current_paragraph = []  # 코드 블록 내용은 버림
                continue
            else:
                # 코드 블록 시작
                if current_paragraph:
                    paragraphs.append((current_paragraph, "content"))
                    current_paragraph = []
                paragraphs.append(([ln], "protected"))
                in_code_block = True
                continue

        # 코드 블록 내부에서는 모든 라인을 현재 문단에 추가 (보호)
        if in_code_block:
            current_paragraph.append(ln)
            continue

        # 빈 줄 = 문단 경계 (코드 블록 외부에서만)
        if not stripped:
            if current_paragraph:
                paragraphs.append((current_paragraph, "content"))
                current_paragraph = []
            continue

        # 헤더/표/리스트는 별도 문단으로 처리 (보호)
        stripped_ln = stripped
        if (stripped_ln.startswith("#") or
            stripped_ln.startswith("|") or
            stripped_ln.startswith(("- ", "* ", "+ ", "-", "*", "+"))):
            if current_paragraph:
                paragraphs.append((current_paragraph, "content"))
                current_paragraph = []
            # 이러한 라인은 개별 문단으로 추가
            paragraphs.append(([ln], "protected"))
            continue

        current_paragraph.append(ln)

    # 마지막 문단 처리
    if current_paragraph:
        paragraphs.append((current_paragraph, "content"))

    # 각 문단 검사 및 처리
    for i, (para_lines, para_type) in enumerate(paragraphs):
        print(f"  Para {i}: type={para_type}, lines={len(para_lines)}, text={''.join(para_lines)[:50]}")
    out_lines = []
    for para_lines, para_type in paragraphs:
        if para_type in ("frontmatter", "protected"):
            out_lines.extend(para_lines)
            continue

        # 문단 내 고특이도 시그니처 개수 세기
        para_text = "".join(para_lines)
        signal_count = 0
        matched_patterns = []

        for pattern in _REASONING_PATTERNS:
            matches = list(pattern.finditer(para_text))
            if matches:
                signal_count += len(matches)
                for m in matches:
                    matched_patterns.append({
                        "pattern": pattern.pattern,
                        "match": m.group()[:50],
                        "position": m.start()
                    })

        if signal_count >= _REASONING_MIN_SIGNALS:
            # 2신호 이상 → 문단 전체 제거
            removed += 1
            matches.append({
                "signals": signal_count,
                "patterns": matched_patterns,
                "action": "paragraph_removed",
                "preview": para_text[:100]
            })
            logger.warning(f"[REASONING-LEAK] 문단 제거: {signal_count}개 시그니처 감지 - '{para_text[:80]}...'")
        else:
            # 보존
            out_lines.extend(para_lines)

    return "".join(out_lines), {"removed": removed, "matches": matches}


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
    global LEAK_PATTERNS, LEAK_REGEX

    _LEAK_CONFIG = _load_leak_patterns()
    _PROMPT_LEAK_PATTERNS = _compile_patterns(_LEAK_CONFIG.get("prompt_leak", {}).get("patterns", []))
    _CTA_LEAK_PATTERNS = _compile_patterns(_LEAK_CONFIG.get("cta_leak", {}).get("patterns", []))
    _FORBIDDEN_CTA_PATTERNS = _compile_patterns(_LEAK_CONFIG.get("cta_leak", {}).get("forbidden_cta", []))
    _PLACEHOLDER_PATTERN = re.compile(_LEAK_CONFIG.get("placeholder_leak", {}).get("pattern", r'\{\{(?!<|%)([^}]+)\}\}'))

_REASONING_LEAK_CONFIG = _LEAK_CONFIG.get("reasoning_leak", {})
_REASONING_PATTERNS = _compile_patterns(_REASONING_LEAK_CONFIG.get("patterns", []))
_REASONING_MIN_SIGNALS = _REASONING_LEAK_CONFIG.get("min_signals", 2)
_HTML_TAGS = _LEAK_CONFIG.get("html_tag_leak", {}).get("tags", [])
_JSON_LEAK_PATTERN = re.compile(_LEAK_CONFIG.get("json_leak", {}).get("pattern", r'(?<!`)\n\s*\{\s*"(?:image_type|chart_type|image_keyword)"'))
LEAK_PATTERNS = (
_LEAK_CONFIG.get("prompt_leak", {}).get("patterns", [])
+ _LEAK_CONFIG.get("cta_leak", {}).get("patterns", [])
+ _LEAK_CONFIG.get("cta_leak", {}).get("forbidden_cta", [])
)
LEAK_REGEX = _compile_patterns(LEAK_PATTERNS)