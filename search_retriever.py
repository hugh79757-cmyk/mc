import os
import json
import time
import hashlib
import logging
from urllib.request import Request, urlopen
from urllib.parse import quote
from urllib.error import HTTPError

logger = logging.getLogger(__name__)

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
    
    seen_links: set = set()
    results: list[dict] = []
    
    for ep in endpoints:
        ok, data = client.search(keyword, endpoint=ep, display=max_per)
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