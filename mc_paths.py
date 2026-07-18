"""
mc — 경로 해석 및 5000 import 지원 (Phase 2)

핵심 역할:
  1. 프로젝트 루트/경로 상수 정의
  2. 5000 프로젝트를 sys.path 에 추가 → `shared.*` 모듈 import 가능하게 함
  3. config/*.yaml → 파이썬 dict 로 로드
"""

import os
import sys
import yaml
from typing import Any, Dict

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


def classify_keyword(keyword: str) -> str:
    """
    시드 키워드 성격 자동 분류.
    Returns: "shopping" | "tech" | "travel" | "issue" | "general"
    """
    import re

    kw = keyword.lower()

    # 쇼핑/소비/브랜드 관련
    shopping_patterns = [
        r"(쇼핑|구매|가격|할인|브랜드|쇼핑몰|코디|옷|의류|패션|신발|가방|악세서리|화장품)",
        r"(mall|shop|store|brand|price|discount|coupon|review\s*product)",
        r"(츄니|츄니토리|무신사|지그재그|에이블리|W컨셉)",
    ]
    for pat in shopping_patterns:
        if re.search(pat, kw):
            return "shopping"

    # IT/기술 관련
    tech_patterns = [
        r"(ai|인공지능|머신러닝|딥러닝|gpt|llm|api|개발|프로그래밍|코딩|클라우드|서버|데이터)",
        r"(it|tech|software|app|애플|아이폰|갤럭시|ios|안드로이드|윈도우|리눅스)",
        r"(파이썬|자바스크립트|타입스크립트|리액트|노드|장고|플라스크)",
    ]
    for pat in tech_patterns:
        if re.search(pat, kw):
            return "tech"

    # 여행/지역/맛집 관련
    travel_patterns = [
        r"(여행|관광|맛집|호텔|리조트|항공|비행기|투어|패키지|배낭|국내여행|해외여행)",
        r"(travel|trip|tour|hotel|restaurant|맛|음식|요리|카페|디저트)",
        r"(제주|부산|서울|경주|강릉|속초|여수|통영|일본|동남아|유럽|미국)",
    ]
    for pat in travel_patterns:
        if re.search(pat, kw):
            return "travel"

    # 이슈/시사 관련
    issue_patterns = [
        r"(이슈|시사|뉴스|정치|경제|사회|환경|기후|전쟁|선거|법률|규제|정책)",
        r"(issue|news|politics|election|war|climate|regulation|policy|trend)",
    ]
    for pat in issue_patterns:
        if re.search(pat, kw):
            return "issue"

    return "general"


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


# ── 최초 import 시 DB 경로 초기화 + 5000 경로 추가 ──
ensure_5000_on_path()
init_db_path()
