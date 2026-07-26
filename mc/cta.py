"""
mc/cta.py — CTA 템플릿 관리 및 AI CTA 감지/교체 (Phase 22)

Phase 17 v2 설계 기반:
- CTA 문구는 전 카테고리 "더 알아보기 →" 통일
- 링크 목적지만 카테고리×depth별로 분기
- AI 생성 CTA 감지 및 공식 CTA로 교체
"""

import re
import logging
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)


# ── 설정 로드 ───────────────────────────────────────────────────────

def _load_cta_templates() -> dict:
    """config/cta_templates.yaml 로드"""
    path = Path(__file__).resolve().parent.parent / "config" / "cta_templates.yaml"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


_CTA_TEMPLATES = _load_cta_templates()


# ── CTA 생성 ─────────────────────────────────────────────────────────

def get_cta(
    category: str,
    depth: int,
    next_url: Optional[str] = None,
    hub_url: Optional[str] = None,
) -> dict:
    """
    카테고리와 depth에 맞는 공식 CTA 반환.
    
    Args:
        category: keyword_categories 키 (travel, real_estate, automotive, stock, etc)
        depth: 0, 1, 2 (step = depth + 1)
        next_url: 다음 단계 포스트 URL (chain_card용)
        hub_url: hub 페이지 URL (Step 3 hub_cta용)
    
    Returns:
        dict: {
            'html': '...',           # 최종 렌더링될 HTML/shortcode
            'text': '더 알아보기 →',  # 표시 문구
            'style': 'red-bg',
            'url': 'https://...',    # 실제 링크
            'type': 'chain_card' | 'hub' | 'dual_info'
        }
    """
    templates = _CTA_TEMPLATES.get("cta_templates", {})
    link_dest = _CTA_TEMPLATES.get("link_destinations", {})
    
    # Depth별 CTA 타입 결정
    if depth == 2:  # Step 3
        cta_type = "hub"
        text = templates.get("hub_cta", {}).get("text", "전체 글 모아보기 →")
        style = templates.get("hub_cta", {}).get("style", "red-bg")
        url = hub_url or ""
        placeholder = templates.get("hub_cta", {}).get("placeholder", "{{ENTRY_LINK}}")
    elif depth in (0, 1):  # Step 1, 2
        cta_type = "chain_card"
        text = templates.get("chain_card", {}).get("text", "더 알아보기 →")
        style = templates.get("chain_card", {}).get("style", "red-bg")
        url = next_url or ""
    else:
        cta_type = "dual_info"
        text = templates.get("dual_info", {}).get("text", "이 시리즈 보기 →")
        style = templates.get("dual_info", {}).get("style", "red-bg")
        url = next_url or ""

    # HTML/shortcode 생성
    if cta_type == "chain_card":
        html = f'{{{{< chain-card title="다음 글" url="{url}" cta="{text}" >}}}}'
    elif cta_type == "hub":
        html = f'{{{{< chain-card title="전체 시리즈" url="{url}" cta="{text}" >}}}}'
    else:
        html = f'{{{{< chain-card title="관련 글" url="{url}" cta="{text}" >}}}}'

    return {
        "html": html,
        "text": text,
        "style": style,
        "url": url,
        "type": cta_type,
        "placeholder": placeholder if cta_type == "hub" else None,
    }


# ── AI CTA 감지 ───────────────────────────────────────────────────────

_AI_CTA_PATTERNS = [
    r"더\s*(?:깊이\s*)?알아보기",
    r"계속\s*읽기",
    r"관련\s*주제",
    r"아래\s*버튼",
    r"링크를\s*클릭",
    r"관련\s*글",
    r"시리즈\s*보기",
    r"이\s*시리즈\s*보기",
    r"전체\s*글\s*모아보기",
    r"모아보기",
    r"이어서\s*(?:실전\s*)?적용법",
    r"관련\s*주제\s*보기",
    r"더\s*자세히\s*보기",
    r"더\s*깊이\s*알아보기",
]

_FORBIDDEN_CTA_PATTERNS = [
    r"지금\s*(?:구매|매수|계약|청약|예약)",
    r"한정\s*수량",
    r"마감\s*임박",
    r"최저가\s*보장",
    r"오늘만\s*특가",
    r"곤두박질",
    r"오늘\s*계약",
    r"아래\s*버튼",
    r"링크를\s*클릭",
]

def detect_ai_cta(text: str) -> list[dict]:
    """
    본문에서 AI가 생성한 임의 CTA 패턴 감지.
    
    Returns:
        list of dict: {'pattern': str, 'match': str, 'position': int}
    """
    matches = []
    
    # 일반 AI CTA 패턴
    for pattern in _AI_CTA_PATTERNS:
        for m in re.finditer(pattern, text):
            matches.append({
                "pattern": pattern,
                "match": m.group(),
                "position": m.start(),
            })
    
    # 금지 CTA 패턴 (더 강한 경고)
    for pattern in _FORBIDDEN_CTA_PATTERNS:
        for m in re.finditer(pattern, text):
            matches.append({
                "pattern": pattern,
                "match": m.group(),
                "position": m.start(),
                "forbidden": True,
            })
    
    return matches


def replace_ai_cta(text: str, official_cta: str = "더 알아보기 →") -> str:
    """
    감지된 AI CTA를 제거하고 공식 CTA 안내 주석으로 대체.
    
    Args:
        text: 원본 텍스트
        official_cta: 공식 CTA 문구 (기본: "더 알아보기 →")
    
    Returns:
        정제된 텍스트
    """
    if not text:
        return text
    
    cleaned = text
    matches = detect_ai_cta(text)
    
    if matches:
        logger.warning(f"[CTA] AI CTA {len(matches)}개 감지: {[m['match'] for m in matches]}")
    
    # 금지 CTA는 완전 제거
    for m in matches:
        if m.get("forbidden"):
            cleaned = re.sub(re.escape(m["match"]), "", cleaned)
    
    # 일반 AI CTA도 제거 (공식 CTA는 card_injector에서 주입하므로 본문에서 제거)
    for m in matches:
        if not m.get("forbidden"):
            cleaned = re.sub(re.escape(m["match"]), "", cleaned)
    
    # 플레이스홀더 {{...}} 제거 (shortcode {{< >}} 제외)
    cleaned = re.sub(r'\{\{(?!<|%)([^}]+)\}\}', '', cleaned)
    
    return cleaned


def verify_cta_count(content: str, depth: int) -> tuple[bool, str]:
    """
    최종 마크다운에 CTA 블록이 정확히 존재하는지 검증.
    
    Args:
        content: 최종 마크다운
        depth: 0, 1, 2 (step = depth + 1)
    
    Returns:
        (pass: bool, message: str)
    """
    chain_card_count = len(re.findall(r'chain-card', content))
    dual_cta_count = len(re.findall(r'dual-cta', content))
    html_cta_count = len(re.findall(r'<div[^>]*class="[^"]*cta[^"]*"', content))
    
    if depth == 2:  # Step 3: hub CTA 1개
        expected_chain = 1
        if chain_card_count == expected_chain and dual_cta_count == 0 and html_cta_count == 0:
            return True, f"CTA 검증 통과: hub CTA {chain_card_count}개"
        return False, f"CTA 검증 실패: chain-card={chain_card_count} (기대 {expected_chain}), dual-cta={dual_cta_count}, html_cta={html_cta_count}"
    
    elif depth in (0, 1):  # Step 1, 2: chain-card 1개 (하단) + 중간 카드 선택적
        if chain_card_count >= 1 and dual_cta_count == 0 and html_cta_count == 0:
            return True, f"CTA 검증 통과: chain-card {chain_card_count}개"
        return False, f"CTA 검증 실패: chain-card={chain_card_count} (최소 1개), dual-cta={dual_cta_count}, html_cta={html_cta_count}"
    
    return True, "CTA 검증 스킵 (depth 불명)"


# ── 편의 함수 ────────────────────────────────────────────────────────

def get_official_cta_text() -> str:
    """공식 CTA 텍스트 반환 (Phase 17 v2: '더 알아보기 →')"""
    return _CTA_TEMPLATES.get("cta_templates", {}).get("chain_card", {}).get("text", "더 알아보기 →")


# ── 설정 리로드 (테스트용) ──────────────────────────────────────────

def reload_templates() -> None:
    """cta_templates.yaml 재로드"""
    global _CTA_TEMPLATES
    _CTA_TEMPLATES = _load_cta_templates()