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


def classify_keyword(keyword: str) -> str:
    """
    시드 키워드 성격 자동 분류.
    prompts.yaml의 keyword_categories 패턴을 읽어 판별.
    Returns: "travel" | "real_estate" | "automotive" | "stock" | "etc"
    """
    import re

    kw = keyword.lower()
    prompts = load_prompts()
    categories = prompts.get("keyword_categories", {})

    for cat_name, cat_config in categories.items():
        patterns = cat_config.get("patterns", [])
        for pat in patterns:
            if re.search(pat, kw):
                return cat_name

    return "etc"


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
