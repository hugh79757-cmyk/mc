"""
mc — 경로 해석 및 5000 import 지원 (Phase 2)

핵심 역할:
  1. 프로젝트 루트/경로 상수 정의
  2. 5000 프로젝트를 sys.path 에 추가 → `shared.*` 모듈 import 가능하게 함
  3. config/*.yaml → 파이썬 dict 로 로드
"""

import json
import logging
import os
import sys
import yaml
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ── 프로젝트 루트 ──
MC_PATH = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = MC_PATH
CONFIG_DIR = os.path.join(PROJECT_ROOT, "config")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
DRAFTS_DIR = os.path.join(OUTPUT_DIR, "drafts")

# ── Config 파일 경로 ──
PROMPTS_PATH = os.path.join(CONFIG_DIR, "prompts.yaml")
CHAIN_CONFIG_PATH = os.path.join(CONFIG_DIR, "chain_config.yaml")

# ── 5000 경로 (하드코딩) ──
PATH_5000 = "/Users/twinssn/Projects/5000"

# ── Phase 5: mde2 경로 ──
PATH_MDE2 = "/Users/twinssn/Projects/mde2"

# ── DB 경로 (lazy init) ──
MC_DB_PATH = None  # set by init_db_path()


def init_db_path():
    """chain_config.yaml 에서 db_path 를 읽어 MC_DB_PATH 설정."""
    global MC_DB_PATH
    cfg = load_config("chain_config.yaml")
    MC_DB_PATH = cfg.get("db_path", os.path.join(PROJECT_ROOT, "data", "mc_chains.db"))


def ensure_5000_on_path():
    """5000 프로젝트 루트를 sys.path 에 추가 (중복 방지)."""
    if PATH_5000 not in sys.path:
        sys.path.insert(0, PATH_5000)


def ensure_mde2_on_path():
    """Phase 5: mde2 프로젝트 루트를 sys.path 에 추가."""
    if PATH_MDE2 not in sys.path:
        sys.path.insert(0, PATH_MDE2)


def load_config(config_name: str = "chain_config.yaml") -> Dict[str, Any]:
    """config/ 디렉토리에서 YAML 파일 로드."""
    path = os.path.join(CONFIG_DIR, config_name)
    if not os.path.exists(path):
        raise FileNotFoundError(f"[mc] Config not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_prompts() -> Dict[str, str]:
    """config/prompts.yaml → dict."""
    return load_config("prompts.yaml")


def resolve_blog_id(site_key: str) -> str:
    """사이트 키 → blog_id 변환."""
    cfg = load_config()
    blog_id = cfg.get("sites", {}).get(site_key, {}).get("blog_id")
    if not blog_id:
        raise KeyError(f"[mc] Unknown site_key: {site_key}")
    return blog_id


def get_chain_blog_key(depth: int) -> str:
    """체인 뎁스(0, 1, 2) → 사이트 키 반환."""
    cfg = load_config()
    key = cfg.get("chain_blogs", {}).get(depth)
    if not key:
        raise KeyError(f"[mc] No blog configured for chain depth {depth}")
    return key


def get_chain_direction_role(chain_type: str, step: int) -> str:
    """
    체인 방향(depth/swallow/lateral)과 step(1/2/3)에 따른 역할명 반환.
    예: get_chain_direction_role("swallow", 1) → "구매/소비형"
    """
    cfg = load_config()
    direction = cfg.get("chain_directions", {}).get(chain_type, {})
    roles = direction.get("step_roles", {})
    return roles.get(step, f"Step {step}")


# ── LLM 분류기 ──────────────────────────────────────────────────────────

_CATEGORY_CACHE_PATH = os.path.join(PROJECT_ROOT, "data", "category_cache.json")

# LLM 분류 프롬프트 — 9개 지원 카테고리 + 4개 보류
_CLASSIFY_SYSTEM = """아래 키워드의 블로그 글 카테고리를 하나만 선택하시오.

카테고리 목록과 판단 기준:
- travel: 장소 방문, 여행지, 축제, 팝업스토어, 박물관, 공원, 맛집, 카페, 동물원, 식물원, 분수대, 공원 산책
- entertainment: 영화, 드라마, 애니메이션, 게임, 웹툰, 소설, 결말, 줄거리, 리뷰, 만화, 애니 캐릭터
- knowledge: 용어 뜻풀이, 인물 정보, 역사, 교양, 상식, 시사 이슈, 동물/곤충 정보, 시기/발달, 식단/이유식
- product: 제품 구매, 가전, 생활용품, IT기기, 캠핑장비, 비교, 추천, 한정판/에디션 제품
- medicine: 의약품, 건강기능식품, 증상, 효능, 부작용, 복용법
- customer_service: 고객센터, AS센터, 전화번호, 문의 방법
- gov_finance: 정부지원, 보험, 연금, 실업급여, 보조금, 신청방법
- shopping_brand: 쇼핑몰, 브랜드, 할인, 세일, 기획전, 멤버십
- golf_course: 골프장, 그린피, 예약, 코스 정보

판단이 어려우면 가장 가까운 카테고리를 선택하시오.
반드시 위 카테고리 중 하나만 답하시오. 카테고리명만 출력하시오."""

# 지원 카테고리 (계약서 존재 + 분류 가능)
LLM_SUPPORTED_CATEGORIES = frozenset({
    "travel", "entertainment", "knowledge",
    "product", "customer_service", "gov_finance",
    "shopping_brand", "golf_course", "medicine",
})

# 보류 카테고리 → reject
_REJECTED_CATEGORIES = frozenset({
    "real_estate", "automotive", "stock", "etc",
})


def _load_category_cache() -> Dict[str, str]:
    """파일 기반 캐시 로드. 없으면 빈 dict."""
    try:
        with open(_CATEGORY_CACHE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, OSError, ValueError):
        return {}


def _save_category_cache(cache: Dict[str, str]) -> None:
    """캐시를 파일에 저장."""
    try:
        os.makedirs(os.path.dirname(_CATEGORY_CACHE_PATH), exist_ok=True)
        tmp = _CATEGORY_CACHE_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
        os.replace(tmp, _CATEGORY_CACHE_PATH)
    except OSError as exc:
        logger.warning("[classify] 캐시 저장 실패: %s", exc)


def _classify_with_llm(keyword: str) -> Optional[str]:
    """LLM으로 키워드 분류. Gemini API 직접 호출. 429 시 1회 재시도."""
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        logger.warning("[classify] GEMINI_API_KEY 없음 — LLM 분류 불가")
        return None

    import time
    import urllib.request
    import urllib.error

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-flash-lite-latest:generateContent"
        f"?key={api_key}"
    )
    payload = json.dumps({
        "contents": [{"parts": [{"text": f"{_CLASSIFY_SYSTEM}\n\n키워드: {keyword}"}]}],
        "generationConfig": {"temperature": 0.0, "maxOutputTokens": 20},
    }).encode("utf-8")

    for attempt in range(2):  # max 2 attempts (original + 1 retry)
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            text = data["candidates"][0]["content"]["parts"][0]["text"].strip().lower()
            if text in LLM_SUPPORTED_CATEGORIES:
                return text
            logger.warning("[classify] LLM이 지원되지 않는 카테고리 반환: %s", text)
            return None
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt == 0:
                time.sleep(2.0)  # 2초 대기 후 재시도
                continue
            logger.warning("[classify] LLM 호출 실패: %s", exc)
            return None
        except Exception as exc:
            logger.warning("[classify] LLM 호출 실패: %s", exc)
            return None
    return None


def _classify_with_regex(keyword: str) -> str:
    """기존 정규식 분류 (fallback)."""
    import re

    kw = keyword.lower()

    if kw.endswith("주가"):
        return "stock"

    prompts = load_prompts()
    categories = prompts.get("keyword_categories", {})

    cat_names = [c for c in categories.keys() if c != "etc"]
    cat_names.sort(key=lambda c: (categories.get(c, {}) or {}).get("priority", 100))

    for cat_name in cat_names:
        cat_config = categories.get(cat_name, {}) or {}
        patterns = cat_config.get("patterns", []) or []
        for pat in patterns:
            if re.search(pat, kw) or re.search(pat, keyword):
                return cat_name

    return _postprocess_stock_priority(kw, "etc")


def classify_keyword(keyword: str, *, use_llm: bool = True, use_cache: bool = True) -> str:
    """
    시드 키워드 성격 자동 분류.

    1순위: 파일 기반 캐시 (같은 키워드 재분류 방지)
    2순위: LLM 분류 (gemini-flash-lite, 가장 저렴)
    3순위: 기존 정규식 패턴 매칭 (fallback)

    Returns: 지원 카테고리 중 하나, 또는 "etc" (보류/미분류).
    """
    # ~주가 키워드는 즉시 stock (LLM 불필요)
    if keyword.lower().endswith("주가"):
        return "stock"

    # 1. 캐시 확인 (LLM 호출 불필요)
    if use_cache:
        cache = _load_category_cache()
        if keyword in cache:
            return cache[keyword]

    # 2. LLM 분류 (use_llm=True일 때만)
    if use_llm:
        llm_result = _classify_with_llm(keyword)
        if llm_result:
            if use_cache:
                cache[keyword] = llm_result
                _save_category_cache(cache)
            return llm_result

    # 3. 정규식 fallback
    return _classify_with_regex(keyword)


def _postprocess_stock_priority(keyword: str, category: str) -> str:
    """키워드가 ~주가로 끝나면 stock 우선."""
    if keyword.endswith("주가"):
        return "stock"
    return category


def resolve_chain_type(keyword: str, override: str = None) -> str:
    """
    키워드로 체인 방향 결정.
    override 가 있으면 해당 값 사용.
    Returns: "depth" | "swallow" | "lateral"
    """
    if override and override in ("depth", "swallow", "lateral"):
        return override

    cfg = load_config()
    mapping = cfg.get("keyword_mapping", {})
    category = classify_keyword(keyword)
    return mapping.get(category, "depth")


# ── 최초 import 시 DB 경로 초기화 + 5000/mde2 경로 추가 ──
ensure_5000_on_path()
ensure_mde2_on_path()
init_db_path()
