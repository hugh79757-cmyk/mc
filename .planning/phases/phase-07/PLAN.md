# Phase 7: 검색 증강 작성 (Naver Search API)

**Created:** 2026-07-18  
**Phase Number:** 7  
**Mode:** mvp  

## Goal

Naver Search API를 활용한 검색 증강 글쓰기. `chain_drafter`가 포스트 초안을 생성할 때 Naver 검색 결과를 참고 자료로 프롬프트에 주입하여 더 사실적이고 풍부한 내용의 글을 생성한다.

**핵심:** 검색은 작성 보조 도구일 뿐. 검색 실패/부재 시에도 기존처럼 draft는 정상 진행되어야 함.

## Design Decisions

| Decision | Value | Why |
|----------|-------|------|
| Provider | Naver Search API | 국내 검색 점유율 1위, 한국어 콘텐츠 최적 |
| Endpoints by angle | basic: encyc/kin/webkr, advanced: webkr/news/blog, expert: news/webkr/cafearticle | Step별 특성에 맞는 정보 소스 |
| Context injection | `draft_user` 프롬프트 끝에 `## 참고 자료` 섹션 추가 | 기존 프롬프트 구조 변경 없음 |
| API key source | `twinssn/.env.common` | mc/.env와 분리, 공유 자격 증명 |
| Caching | 메모리 LRU (선택적) | 동일 쿼리 중복 호출 방지 |
| Fallback | 검색 실패/API 키 없음 → 경고 로그 + 기존 draft 진행 | Zero-block design |

## Existing Code Constraints (MUST NOT Violate)

- `draft_chain()` 시그니처 변경 금지 → `use_context=False` 기본값 매개변수만 추가
- `chain_db.py` 기존 함수 수정 금지 → 새로운 `init_search_columns()` + `update_post_context()`만 추가
- `chain_publisher.py` 기존 argparse 플래그 수정 금지 → `--search` / `--no-search`만 추가
- 검색 결과 출처 URL을 최종 글에 절대 노출 금지
- 검색 결과의 `<b>` 태그 제거 필수 (네이버 API는 결과 키워드를 `<b>`로 감쌈)
- API 키 하드코딩 금지 — 항상 환경변수에서 로드

## Wave 1: DB + Config (2 tasks)

### Task 1.1: chain_db.py — Add search columns

**Files to modify:** `chain_db.py`  
**Change type:** Append new functions (do NOT modify existing ones)

Add at end of file (after Phase 6 loop functions):

```python
SEARCH_MIGRATIONS_SQL = [
    "ALTER TABLE chain_posts ADD COLUMN context_md TEXT",
    "ALTER TABLE chain_posts ADD COLUMN search_sources TEXT",
]

def init_search_columns():
    """Add context_md and search_sources columns to chain_posts."""
    conn = get_conn()
    cursor = conn.execute("PRAGMA table_info(chain_posts)")
    cols = {row["name"] for row in cursor.fetchall()}
    for sql in SEARCH_MIGRATIONS_SQL:
        col_name = sql.split("ADD COLUMN ")[1].split(" ")[0]
        if col_name not in cols:
            try:
                conn.execute(sql)
            except sqlite3.OperationalError:
                pass
    conn.commit()
    conn.close()

def update_post_context(post_id: int, context_md: str, search_sources: str = None):
    """Save search context for a post."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    conn.execute(
        "UPDATE chain_posts SET context_md = ?, search_sources = ?, updated_at = ? WHERE id = ?",
        (context_md, search_sources, now, post_id),
    )
    conn.commit()
    conn.close()
```

### Task 1.2: config/chain_config.yaml — Add search section

**Files to modify:** `config/chain_config.yaml`

Add at end of file (before `db_path`):

```yaml
# === 검색 증강 작성 (Phase 7) ===
search:
  enabled: true
  provider: naver
  max_sources: 5
  endpoints_by_angle:
    basic: ["encyc", "kin", "webkr"]
    advanced: ["webkr", "news", "blog"]
    expert: ["news", "webkr", "cafearticle"]
  display_per_endpoint: 5
  timeout: 10
  daily_quota: 25000
```

---

## Wave 2: Search Retriever (1 new file)

### Task 2.1: search_retriever.py — NaverSearchClient + context builder

**New file:** `search_retriever.py`

```python
"""
search_retriever.py — Naver Search API 기반 검색 증강 모듈 (Phase 7)

NaverSearchClient: 네이버 검색 API 래퍼
retrieve_context_for_post: post 각도별 엔드포인트 매핑 + Markdown 컨텍스트 생성
"""

import os
import json
import time
import hashlib
import logging
from urllib.request import Request, urlopen
from urllib.parse import urlencode, quote
from urllib.error import HTTPError

logger = logging.getLogger(__name__)

# ── Memory cache ──
_cache: dict[str, tuple] = {}  # hash → (timestamp, json_str)

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
    """Naver Search API client."""
    
    def __init__(self, client_id: str = None, client_secret: str = None):
        self.client_id = client_id or os.environ.get("NAVER_CLIENT_ID", "")
        self.client_secret = client_secret or os.environ.get("NAVER_CLIENT_SECRET", "")
        self._quota_used = 0
    
    def search(self, query: str, endpoint: str = "webkr",
               display: int = 5, start: int = 1, sort: str = "sim") -> tuple:
        """
        Search Naver API endpoint.
        Returns: (ok: bool, result: str)
          ok=True → result is JSON string
          ok=False → result is error message
        """
        if not self.client_id or not self.client_secret:
            return (False, "NAVER_CLIENT_ID/NAVER_CLIENT_SECRET not configured")
        
        ck = _cache_key(endpoint, query, display)
        cached = _get_cached(ck)
        if cached:
            return (True, cached)
        
        # Check daily quota (25,000/day)
        if self._quota_used >= 25000:
            logger.warning("[search] ⚠️ Daily Naver API quota exhausted (25,000)")
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
    """Remove <b> and </b> tags from Naver API results."""
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
      ok=True → context_md is ready-to-use Markdown reference section
      ok=False → context_md_or_err is error message
    
    Markdown format:
    ## 참고 자료
    
    다음은 이 글의 주제와 관련된 검색 결과입니다. 내용 참고하여 풍부한 글을 작성하세요.
    
    ### [Title](link)
    > Description
    
    ### [Title](link)
    > Description
    ...
    """
    # Resolve endpoints from config or defaults
    endpoints_map = {
        "basic": ["encyc", "kin", "webkr"],
        "advanced": ["webkr", "news", "blog"],
        "expert": ["news", "webkr", "cafearticle"],
    }
    
    if cfg and "search" in cfg:
        ep_cfg = cfg["search"].get("endpoints_by_angle", {})
        if angle in ep_cfg:
            endpoints_map.update({angle: ep_cfg[angle]})
    
    endpoints = endpoints_map.get(angle, ["webkr"])
    max_per_endpoint = max(1, max_sources // len(endpoints))
    
    seen_links: set = set()
    results: list[dict] = []
    
    for ep in endpoints:
        ok, data = client.search(keyword, endpoint=ep, display=max_per_endpoint)
        if not ok:
            logger.debug(f"[search] {ep} failed: {data}")
            continue
        
        try:
            parsed = json.loads(data)
            items = parsed.get("items", [])
            for item in items:
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
    
    # Build context markdown
    lines = [
        "## 참고 자료",
        "",
        "다음은 이 글의 주제와 관련된 검색 결과입니다. 내용을 참고하여 풍부한 글을 작성하세요.",
        "",
    ]
    for i, r in enumerate(results[:max_sources], 1):
        title = r["title"]
        desc = r["description"]
        link = r["link"]
        lines.append(f"### {i}. {title}")
        if desc:
            lines.append(f"> {desc}")
        lines.append("")
    
    context_md = "\n".join(lines)
    return (True, context_md)
```

**Key behaviors:**
- `<b>` 태그 제거 (`_strip_b_tags`)
- 중복 제거 (link 기준)
- 검색 실패 시 `(False, error_msg)` — caller가 fallback
- 캐싱 (메모리 LRU, 5분 TTL)
- 일일 25,000회 한도 체크 (`_quota_used`)

---

## Wave 3: Draft Integration (2 files to extend)

### Task 3.1: chain_drafter.py — Add search context injection

**Files to modify:** `chain_drafter.py`  
**Change type:** Add `use_context` parameter + context injection logic

**Changes:**

1. **Import 추가** (파일 상단):
```python
from search_retriever import NaverSearchClient, retrieve_context_for_post
```

2. **`draft_chain()` 시그니처 변경**:
```python
def draft_chain(chain_id: int, seed_keyword: str, use_context: bool = False) -> list[dict]:
```

3. **`draft_single_post()` 시그니처 변경**:
```python
def draft_single_post(
    post: dict,
    posts: list[dict],
    seed_keyword: str,
    use_context: bool = False,
) -> str:
```

4. In `draft_single_post`, **after context building** and **before `generate()` call**, add context retrieval:
```python
    # ── Search context injection (Phase 7) ──
    context_md = ""
    if use_context:
        try:
            client = NaverSearchClient()
            angle_key = {"기초": "basic", "분석": "advanced", "전문": "expert", 
                         "구매": "basic", "절약": "advanced", "금융": "expert",
                         "주제": "basic", "비교": "advanced", "비즈니스": "expert"}.get(
                post.get("angle", "")[:2], "webkr")
            ok, ctx = retrieve_context_for_post(
                seed_keyword, angle_key, client, cfg=chain_cfg,
            )
            if ok:
                context_md = ctx
                # Save to DB
                from chain_db import update_post_context
                update_post_context(post["id"], ctx)
        except Exception as e:
            print(f"  [drafter] ⚠️ Search context skipped: {e}")
    
    # ── Build final user prompt with context ──
    user_prompt = draft_user.format(...)
    if context_md:
        user_prompt += "\n\n" + context_md
```

**Angle mapping logic:**
- `angle` field in chain_posts contains strings like `"기초 개념 소개 및 중요성"`
- Extract first 2 chars → map to Naver endpoint category:
  - 기초/구매/주제 → `basic`
  - 분석/절약/비교 → `advanced`
  - 전문/금융/비즈니스 → `expert`
- Fallback: `webkr` (general web)

**Do NOT:**
- Change the original `draft_user` template
- Add search context INSIDE the format string — only APPEND at the end
- Fail if search fails — just skip context and continue

### Task 3.2: chain_publisher.py — Add --search / --no-search flag

**Files to modify:** `chain_publisher.py`  
**Change type:** Add new argparse flag + routing

**Add argparse flag** (after Phase 6 flags):
```python
parser.add_argument("--search", action="store_true",
                    help="Enable Naver search context for drafting")
parser.add_argument("--no-search", action="store_true",
                    help="Disable search context (default)")
```

**Routing in `publish_chain()` call** (where `run_chain` or `draft_chain` is called):
```python
# In the --publish / --seed routing:
use_context = args.search and not args.no_search

# Pass to run_chain():
run_chain(
    args.seed,
    ...,
    use_context=use_context,
)

# If --seed + --draft directly:
if args.draft and args.seed:
    chain = db.get_chain(chain_id)
    drafted = draft_chain(chain_id, chain['seed'], use_context=use_context)
```

**Also:** `run_chain()` in chain_publisher.py needs `use_context` param forwarded to `draft_chain()`:
```python
def run_chain(seed, ..., use_context=False):
    ...
    if not args.skip_draft:
        drafted = draft_chain(chain_id, seed, use_context=use_context)
```

**Do NOT:**
- Change existing flag behavior
- Make `--search` the default (must be opt-in)
- `--no-search` exists for explicitness but is redundant (default is no-search)

---

## .env Update (User Action Required)

Add to `mc/.env`:
```bash
# Phase 7: Naver Search API (from ~/.env.common)
NAVER_CLIENT_ID=Ss5fmY2dm6QCf9y1cIwV
NAVER_CLIENT_SECRET=HRhD8QKZim
```

Or have `search_retriever.py` read directly from `~/.env.common`:
```python
def _load_naver_creds():
    """Try ~/.env.common first, then env vars."""
    env_path = os.path.expanduser("~/.env.common")
    if os.path.exists(env_path):
        from dotenv import load_dotenv
        load_dotenv(env_path)
    return os.environ.get("NAVER_CLIENT_ID", ""), os.environ.get("NAVER_CLIENT_SECRET", "")
```

---

## Verification Criteria

| # | Criteria | Command |
|---|----------|---------|
| V1 | All files py_compile | `python -m py_compile search_retriever.py chain_db.py chain_drafter.py chain_publisher.py` |
| V2 | DB migration: context_md + search_sources columns added | `python -c "import chain_db as db; db.init_db(); db.init_search_columns(); c=db.get_conn(); print([r[1] for r in c.execute('PRAGMA table_info(chain_posts)').fetchall()])"` → shows `context_md` and `search_sources` |
| V3 | Naver Search API call succeeds | `python -c "from search_retriever import NaverSearchClient; c=NaverSearchClient(); ok,data=c.search('강아지 영양제','encyc'); print('OK' if ok else data)"` |
| V4 | Context retrieval returns markdown | `python -c "from search_retriever import NaverSearchClient, retrieve_context_for_post; c=NaverSearchClient(); ok,ctx=retrieve_context_for_post('강아지 영양제','basic',c); print(ctx[:500] if ok else ctx)"` |
| V5 | Draft with --search flag | `python chain_publisher.py --chain-id 9 --draft --search` → verify `context_md` is stored in DB |
| V6 | --search 없이 기존 동작 유지 | `python chain_publisher.py --chain-id 9 --draft` (no --search) — should work exactly as before |
| V7 | 검색 실패 시 fallback | Remove NAVER keys → `python chain_publisher.py --chain-id 9 --draft --search` — should warn and continue without context |

## Files Summary

| File | Action | Lines (est.) |
|------|--------|-------------|
| `search_retriever.py` | **NEW** | ~150 |
| `chain_db.py` | EXTEND | ~25 |
| `config/chain_config.yaml` | MODIFY | ~12 |
| `chain_drafter.py` | MODIFY | ~30 |
| `chain_publisher.py` | EXTEND | ~20 |
| `.env` | MODIFY (user) | 3 lines |
| **Total** | | **~240** |

## Do NOT

- Change `draft_chain()` existing parameters or return type
- Remove or modify existing prompt templates
- Expose search result URLs in published content
- Leave `<b>` tags in context_md
- Hardcode API credentials in source files
- Block drafting on search failure — always fall through
