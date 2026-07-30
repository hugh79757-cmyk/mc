import os
import json
import time
import hashlib
import logging
from urllib.request import Request, urlopen
from urllib.parse import quote
from urllib.error import HTTPError

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# 검색어 자동 보정
# config의 term_corrections 매핑을 조회해 잘못된 표기를 올바른 표기로 교체
# ─────────────────────────────────────────────────────────────

def apply_term_correction(keyword: str, cfg: dict = None) -> str:
    """
    검색어 자동 보정: cfg['term_corrections'] 에 등록된 잘못된 표기를 올바른 표기로 교체.

    Args:
        keyword: 원본 검색어 (사용자 입력)
        cfg: chain_config.yaml 전체 설정 dict (term_corrections 섹션 포함)

    Returns:
        보정된 검색어 (매핑이 없으면 원본 유지)
    """
    if not cfg:
        return keyword

    corrections = cfg.get("term_corrections", {})
    if not corrections:
        return keyword

    # 1) exact match
    if keyword in corrections:
        corrected = corrections[keyword]
        logger.info("[term_correction] '%s' → '%s' (exact match)", keyword, corrected)
        return corrected

    # 2) strip whitespace match: "영덕시 포트리조트" → match even without spaces
    stripped = keyword.replace(" ", "")
    for wrong, correct in corrections.items():
        if wrong.replace(" ", "") == stripped:
            logger.info("[term_correction] '%s' → '%s' (normalized match via '%s')", keyword, correct, wrong)
            return correct

    return keyword

_cache: dict[str, tuple] = {}

def _cache_key(endpoint: str, query: str, display: int) -> str:
    raw = f"{endpoint}:{query}:{display}"
    return hashlib.md5(raw.encode()).hexdigest()

def _get_cached(key: str, ttl: int = 300) -> str | None:
    if key in _cache:
        ts, data = _cache[key]
        if time.time() - ts < ttl:
            return data
        del _cache[key]
    return None

def _set_cache(key: str, data: str):
    _cache[key] = (time.time(), data)

class NaverSearchClient:
    def __init__(self, client_id: str = None, client_secret: str = None):
        self.client_id = client_id or os.environ.get("NAVER_CLIENT_ID", "")
        self.client_secret = client_secret or os.environ.get("NAVER_CLIENT_SECRET", "")
        self._quota_used = 0

    def search(self, query: str, endpoint: str = "webkr",
               display: int = 5, start: int = 1, sort: str = "sim") -> tuple:
        """
        Search Naver API endpoint.
        Returns: (ok: bool, result: str)
          ok=True -> result is JSON string
          ok=False -> result is error message
        """
        if not self.client_id or not self.client_secret:
            return (False, "NAVER_CLIENT_ID/NAVER_CLIENT_SECRET not configured")

        ck = _cache_key(endpoint, query, display)
        cached = _get_cached(ck)
        if cached:
            return (True, cached)

        if self._quota_used >= 25000:
            logger.warning("[search] Daily Naver API quota exhausted (25,000)")
            return (False, "Daily quota exhausted")

        try:
            enc_query = quote(query)
            url = f"https://openapi.naver.com/v1/search/{endpoint}.json?query={enc_query}&display={display}&start={start}&sort={sort}"
            req = Request(url)
            req.add_header("X-Naver-Client-Id", self.client_id)
            req.add_header("X-Naver-Client-Secret", self.client_secret)

            with urlopen(req, timeout=10) as resp:
                data = resp.read().decode("utf-8")
                self._quota_used += 1
                _set_cache(ck, data)
                return (True, data)
        except HTTPError as e:
            return (False, f"Naver API HTTP {e.code}: {e.reason}")
        except Exception as e:
            return (False, f"Naver API error: {e}")

    @property
    def quota_used(self) -> int:
        return self._quota_used

def _strip_b_tags(text: str) -> str:
    return text.replace("<b>", "").replace("</b>", "")

def retrieve_context_for_post(
    keyword: str,
    angle: str,
    client: NaverSearchClient,
    max_sources: int = 5,
    cfg: dict = None,
) -> tuple:
    """
    Search Naver for sources relevant to a post's angle.

    angle: 'basic' | 'advanced' | 'expert'
    Returns: (ok: bool, context_md_or_err: str)

    Context Markdown format:
    ## 참고 자료
    ...
    ### N. Title
    > Description
    ...
    """
    endpoints_map = {
        "basic": ["encyc", "kin", "webkr"],
        "advanced": ["webkr", "news", "blog"],
        "expert": ["news", "webkr", "cafearticle"],
    }

    if cfg and "search" in cfg:
        ep_map = cfg["search"].get("endpoints_by_angle", {})
        if angle in ep_map:
            endpoints_map[angle] = ep_map[angle]

    endpoints = endpoints_map.get(angle, ["webkr"])
    max_per = max(1, max_sources // len(endpoints))

    # ── 검색어 자동 보정 ────────────────────────────────────────
    corrected_keyword = apply_term_correction(keyword, cfg)
    if corrected_keyword != keyword:
        logger.info("[search] 검색어 보정: '%s' → '%s'", keyword, corrected_keyword)
    # ─────────────────────────────────────────────────────────────

    seen_links: set = set()
    results: list[dict] = []

    for ep in endpoints:
        ok, data = client.search(corrected_keyword, endpoint=ep, display=max_per)
        if not ok:
            logger.debug("[search] %s failed: %s", ep, data)
            continue

        try:
            parsed = json.loads(data)
            for item in parsed.get("items", []):
                link = item.get("link", "").strip()
                if not link or link in seen_links:
                    continue
                seen_links.add(link)
                results.append({
                    "title": _strip_b_tags(item.get("title", "")),
                    "description": _strip_b_tags(item.get("description", "")),
                    "link": link,
                })
        except json.JSONDecodeError:
            continue

    if not results:
        return (False, "No search results found")

    lines = [
        "## 참고 자료",
        "",
        "다음은 이 글의 주제와 관련된 검색 결과입니다. 내용을 참고하여 풍부한 글을 작성하세요.",
        "",
    ]
    for i, r in enumerate(results[:max_sources], 1):
        lines.append(f"### {i}. {r['title']}")
        if r["description"]:
            lines.append(f"> {r['description']}")
        lines.append("")

    return (True, "\n".join(lines))