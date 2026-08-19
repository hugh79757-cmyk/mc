"""
keyword_extractor — 한국어 키워드/제목 → 구체적 영어 검색어 변환

Gemini API를 사용하여 블로그 글의 제목/설명/카테고리에서
Unsplash/Pexels 검색에 적합한 구체적 영어 명사구 1~3개를 추출한다.
LLM 실패 시 카테고리 기반 fallback 검색어를 반환한다.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.request
import urllib.error
from typing import Optional

logger = logging.getLogger(__name__)

# ── Generic 단어 거부 목록 ──────────────────────────────────────────────────
# 이 단어들이 포함된 검색어는 구체성이 부족하여 스톡 사진 검색에 부적합

GENERIC_WORDS = frozenset({
    "technology", "business", "innovation", "artificial intelligence",
    "startup", "company", "news", "digital", "modern", "future",
    "concept", "abstract", "background", "pattern", "texture",
    "nature", "landscape", "scenery", "view", "scene",
    "people", "person", "man", "woman", "team", "group",
    "office", "workspace", "desk", "computer", "screen",
    "graph", "chart", "data", "statistics", "growth",
    "global", "world", "international", "market", "economy",
    "research", "science", "education", "learning",
    "health", "medical", "hospital", "care",
    "security", "protection", "safety",
    "environment", "energy", "sustainable",
    "communication", "network", "connection",
    "management", "strategy", "planning",
    "development", "progress", "advancement",
    "service", "solution", "system", "platform",
    "product", "brand", "quality",
})

# ── Gemini 프롬프트 ──────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are an image search keyword extractor for stock photo websites (Unsplash, Pexels).

Given a blog post title, description, and category in Korean, generate 1-3 specific English noun phrases suitable for searching real stock photos.

Rules:
- Output ONLY concrete noun phrases (company names, place names, product names, industry scenes, specific objects)
- NEVER use generic words: technology, business, nature, innovation, AI, digital, modern, future, concept, abstract, background, people, office, graph, data, growth, global, market, research, health, security, environment, energy, management, strategy, development, service, solution, product, brand
- Each phrase should be 2-4 words
- Prioritize visual specificity: what would a photographer actually photograph?
- Use present tense, lowercase
- Output format: one phrase per line, no numbering, no quotes

Proper noun rules (CRITICAL):
1. If the original keyword contains a proper noun (person, character, brand, place name), ALWAYS include it in the English search query transliterated or in English.
   Example: "스파이더맨 브랜뉴데이" → must contain "spider-man", NOT "comic book store"
   Example: "고성 윈덤호텔" → must contain "goseong wyndham hotel", NOT "luxury resort"
   Example: "다이슨 에어랩" → must contain "dyson airwrap", NOT "hair styling tool"
2. Each step (s1/s2/s3) should emphasize a different visual aspect, but the core proper noun must appear in all.
   Example: s1="spider-man brand new day poster", s2="spider-man comic action scene", s3="spider-man brand new day cover art"
3. Use concrete noun combinations searchable on stock sites. No abstract words (concept, theme, mood).

Examples:
- Title: "삼성전자 AI 반도체 경쟁력 분석" → samsung semiconductor chip
- Title: "서울시 청년 주택 지원금 신청 방법" → seoul apartment building
- Title: "치매 초기 증상 및 예방법" → elderly person memory
- Title: "비트코인 가격 전망 2026" → bitcoin cryptocurrency coin
- Title: "일본 여행 후쿠오카 맛집 추천" → japanese food restaurant
- Title: "스파이더맨 브랜뉴데이 정보" → spider-man brand new day movie poster
- Title: "고성 윈덤호텔 객실 타입" → goseong wyndham hotel room
- Title: "다이슨 에어랩 비교 리뷰" → dyson airwrap hair styler
"""


def extract_search_queries(
    title: str,
    description: str = "",
    category: str = "",
    max_queries: int = 3,
    step: str = "",
) -> list[str]:
    """
    한국어 제목/설명/카테고리에서 영어 검색어를 추출한다.

    Args:
        title: 블로그 글 제목
        description: 글 설명 (선택)
        category: 카테고리 (선택)
        max_queries: 최대 검색어 수
        step: 스텝 ID (s1/s2/s3) — step별 시각적 측면 차별화용 (선택)

    Returns:
        구체적 영어 검색어 리스트 (1~3개)
    """
    queries = _extract_with_llm(title, description, category, step=step)
    if queries:
        queries = _filter_generic(queries)
    if not queries:
        queries = _fallback_queries(title, category)
    final = queries[:max_queries]
    return final


def extract_image_keywords(keyword: str, step: str = "", max_queries: int = 3) -> list[str]:
    """
    시드 키워드에서 영어 검색어를 추출한다 (extract_search_queries의 편의 래퍼).

    Args:
        keyword: 한국어 시드 키워드 (예: "스파이더맨 브랜뉴데이")
        step: 스텝 ID (s1/s2/s3) (선택)
        max_queries: 최대 검색어 수

    Returns:
        구체적 영어 검색어 리스트
    """
    return extract_search_queries(keyword, category=keyword, step=step, max_queries=max_queries)


def _extract_with_llm(
    title: str, description: str, category: str, step: str = ""
) -> list[str]:
    """Gemini API로 검색어 추출. 실패 시 빈 리스트 반환."""
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        logger.debug("[keyword_extractor] GEMINI_API_KEY 없음 — fallback 사용")
        return []

    user_msg = f"제목: {title}"
    if description:
        user_msg += f"\n설명: {description}"
    if category:
        user_msg += f"\n카테고리: {category}"
    if step:
        user_msg += f"\n단계: {step} (각 단계는 서로 다른 시각적 측면을 강조하되, 핵심 고유명사는 유지)"

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-flash-lite-latest:generateContent"
        f"?key={api_key}"
    )
    payload = json.dumps({
        "contents": [{"parts": [{"text": f"{_SYSTEM_PROMPT}\n\n{user_msg}"}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 100},
    }).encode("utf-8")

    for attempt in range(2):
        req = urllib.request.Request(
            url, data=payload, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            queries = _parse_response(text)
            if queries:
                logger.info(
                    f"[keyword_extractor] LLM 추출: {queries} (제목: {title[:30]})"
                )
                return queries
            return []
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt == 0:
                import time
                time.sleep(2.0)
                continue
            logger.warning(f"[keyword_extractor] Gemini 호출 실패: {exc}")
            return []
        except Exception as exc:
            logger.warning(f"[keyword_extractor] Gemini 호출 실패: {exc}")
            return []
    return []


def _parse_response(text: str) -> list[str]:
    """LLM 응답에서 검색어 리스트를 파싱한다."""
    queries = []
    for line in text.strip().splitlines():
        line = line.strip().strip('"').strip("'").strip("- ").strip("0123456789. ")
        if line and len(line) <= 60:
            queries.append(line)
    return queries[:3]


def _filter_generic(queries: list[str]) -> list[str]:
    """generic 단어로만 구성된 검색어를 필터링한다.
    고유명사(spider-man, goseong 등)와 혼재된 경우 보존한다.
    예: 'spider-man brand new day movie poster' → 보존 (brand는 generic이지만 spider-man이 공존)
    예: 'modern workplace' → 필터링 (모두 generic)
    """
    result = []
    for q in queries:
        words = set(q.lower().split())
        non_generic = words - GENERIC_WORDS
        if not non_generic:
            continue  # 모든 단어가 generic → 필터링
        result.append(q)
    return result


def _fallback_queries(title: str, category: str) -> list[str]:
    """LLM 실패 시 카테고리 기반 fallback 검색어를 생성한다."""
    queries = []

    # 카테고리에서 영어 키워드 매핑
    _CAT_MAP = {
        "IT": "computer technology",
        "기술": "computer technology",
        "금융": "finance banking",
        "경제": "finance economy",
        "건강": "health wellness",
        "의료": "medical hospital",
        "교육": "education classroom",
        "여행": "travel destination",
        "부동산": "real estate house",
        "투자": "finance investment",
        "복지": "community service",
        "자격증시험": "study books exam",
        "스포츠": "sports athlete",
        "생활정보": "daily life tips",
        "최신뉴스": "newspaper headlines",
        "정부지원금": "government office",
        "재테크": "finance saving",
        "문화여가": "culture entertainment",
        "돌봄서비스": "caregiver elderly",
        "교통복지": "public transport bus",
        "생활지원": "community help",
        "연금생활지원": "retirement savings",
        "일자리금융": "job office work",
        "공시분석": "stock market board",
        "실적분석": "business meeting chart",
        "배당분석": "dividend finance",
        "IPO분석": "stock exchange bell",
        "ETF분석": "investment portfolio",
        "시장분석": "stock market screen",
        "부동산": "apartment building",
        "실거래가": "real estate sign",
        "청약정보": "housing construction",
        "임대주택": "apartment rental",
        "부동산세금": "tax documents",
        "전월세": "rental contract",
        "브랜드아파트": "brand apartment tower",
    }

    if category:
        cat = category.strip()
        if cat in _CAT_MAP:
            queries.append(_CAT_MAP[cat])
        else:
            # 부분 매칭
            for key, eng in _CAT_MAP.items():
                if key in cat or cat in key:
                    queries.append(eng)
                    break

    if not queries:
        queries.append("modern workplace")

    return queries
