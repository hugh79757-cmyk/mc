---
phase: 13-content-refinement
plan: 01
type: execute
wave: 1-2
depends_on: []
files_modified:
  - chain_publisher_core.py
  - image/prompt_builder.py
  - image/search_providers.py
  - config/prompts.yaml
autonomous: true
requirements:
  - R1
  - R2
  - R3
user_setup: []
must_haves:
  truths:
    - "Raw markdown symbols (**, *, |, -) outside table/marker/code context are cleaned before Hugo build"
    - "Markdown tables are preserved as-is (GFM enabled in Hugo) — no HTML conversion needed"
    - "No leakage of literal pipe/bold/italic characters in published HTML"
    - "Pollinations images use article title + angle in prompt, not just keyword"
    - "Unsplash/Pexels body images are used when image_type=photo, with fallback to image_keyword Pollinations"
    - "Search results cached for 24h (key=keyword hash), no retry on failure"
    - "All 112 existing pytest tests still pass; 8 new tests = 120/120"
  artifacts:
    - path: "chain_publisher_core.py"
      provides: "_clean_markdown_symbols() — markdown cleanup with protection for markers/code/math/tables"
      min_lines: 990
    - path: "chain_publisher_core.py"
      provides: "Wired post-processing in _publish_hugo() and _publish_blogger()"
      pattern: "_clean_markdown_symbols"
    - path: "image/prompt_builder.py"
      provides: "build_contextual_prompt() — contextual prompt with title+angle"
      min_lines: 95
    - path: "image/search_providers.py"
      provides: "Body-image search from Unsplash/Pexels with 24h cache + Pollinations fallback"
      min_lines: 180
    - path: "config/prompts.yaml"
      provides: "Strengthened pipe-use rule"
      contains: "파이프"
  key_links:
    - from: "_publish_hugo() post-processing"
      to: "_clean_markdown_symbols()"
      via: "called after _extract_clean_body() before index.md write"
      pattern: "_clean_markdown_symbols"
    - from: "_publish_hugo() photo branch"
      to: "image/search_providers.py search_body_image()"
      via: "import and call before Pollinations fallback"
      pattern: "search_body_image|UnsplashProvider|PexelsProvider"
---

# Phase 13 — 콘텐츠 고도화 (Content Refinement)

<objective>
Phase 1–12에서 파이프라인 안정화 완료. Phase 13은 콘텐츠 품질을 고도화한다:

**Wave 1**: 마크다운 정제 (R2: 기호 누출 제거 + R3: 표 보호) — Hugo GFM 표 기본 활성화 확인 완료, HTML 변환 불필요.
**Wave 2**: 이미지 관련성 개선 (R1: contextual prompt + Unsplash/Pexels 검색 + 24h 캐시 + fallback)

모든 변경은 기존 112개 테스트 유지 + 신규 8개 = 120/120 목표.
</objective>

## Phase Goal

**As a** blog operator running the mc pipeline, **I want to** publish posts with no leaked markdown symbols, properly rendered GFM tables, and contextually relevant images, **so that** readers have a polished experience without manual post-editing.

## Multi-Source Coverage Audit

| Source Item | Source Type | Covered By | Notes |
|-------------|-------------|------------|-------|
| R1: Image Relevance | CONTEXT | Wave 2 (new) | Contextual prompts + search providers + cache + fallback |
| R2: Markdown Symbol Leakage | CONTEXT | Wave 1 | `_clean_markdown_symbols()` + prompts.yaml |
| R3: Table Rendering | CONTEXT | Wave 1 | GFM default enabled — preserve, no HTML conversion |
| Hugo GFM table check | CONFIRMED | Wave 1 | rotcha markup.toml: no `table=false`, default enabled ✅ |
| API fallback/failure/cache | CONTEXT (수정2) | Wave 2, Task 1.2 | Fallback to image_keyword, 24h cache, env keys |
| Wave order (cleanup first) | CONTEXT (수정3) | Both waves | Wave 1(정제) → Wave 2(이미지) |
| 120/120 test target | CONTEXT (수정4) | Both waves | 112 + 8 new |
| Phase 13.1 carry-over | CONTEXT | — | Noted, no task in this phase |
| 19/27 guard untouched | CONSTRAINT | Both waves | Not in scope |
| _ensure_featureimage untouched | CONSTRAINT | Both waves | Not in scope |
| W1-W6 code untouched | CONSTRAINT | Both waves | Only new code added |
| _extract_clean_body() untouched | CONSTRAINT | Wave 1 | New functions are post-processing |
| rerank=false 회귀 100% 유지 | CONSTRAINT | Both waves | Not touched |

**Status:** ✅ All items covered. No gaps.

---

## Hugo GFM Tables — 확인 완료

```bash
# rotcha markup.toml — goldmark.extensions.table 기본 활성화, table=false 없음
[goldmark.extensions]
  strikethrough = false   # table 항목 없음 → 기본 활성화

# infohot, techpawz: markup.toml 없음 → Hugo 기본값 사용 → GFM table 활성화
```

**결론**: 세 사이트 모두 Hugo Goldmark GFM 표가 기본 활성화되어 있음. HTML `<table>` 변환 불필요. Task 2.2(`_convert_tables_to_html`) **폐기**. Task 2.1 `_clean_markdown_symbols()`에서 표 라인(`|` 시작)만 보호하면 됨.

---

## Wave Structure

| Wave | Plans | Requirement | Files |
|------|-------|-------------|-------|
| **1** | 13-01-PLAN.md | **R2+R3** (Markdown + Tables) | chain_publisher_core.py, prompts.yaml, test_chain_publisher_core.py |
| **2** | 13-01-PLAN.md | **R1** (Image Relevance) | prompt_builder.py, search_providers.py (new), chain_publisher_core.py, test_image_pipeline.py, test_image_search.py |

**Rationale:** Wave 1(정제) → Wave 2(이미지) 순서. `_clean_markdown_symbols()`가 먼저 적용되어 마커·표·코드블록을 보호한 후, 이미지 파이프라인이 안전하게 동작.

---

## Wave 1 — Markdown Cleanup + Table Preservation (R2 + R3)

### Context

Hugo Goldmark GFM tables enabled by default on all 3 sites. No HTML conversion needed. Two changes:

1. **`_clean_markdown_symbols()`** — post-processing after `_extract_clean_body()`. Cleans leaked symbols but **protects**:
   - `<!--todo:image-->` / `<!--todo:chart-->` markers
   - Markdown table lines (starting with `|`)
   - Code blocks (``` fences)
   - Inline code (`` `backtick` ``)
   - Math blocks (`$$`, `$`)
2. **`config/prompts.yaml`** — strengthen pipe-use rule: "파이프 문자는 반드시 표 안에서만 사용"

### Pipeline Order

```
_extract_clean_body(text) → cleaned.body
  → _clean_markdown_symbols(cleaned.body)   [R2: cleanup, preserves markers/tables/code/math]
  → assemble with FM → write index.md
```

No `_convert_tables_to_html()`. GFM tables pass through untouched.

### Tasks

<task type="auto">
<name>Task 1.1: Implement _clean_markdown_symbols() + strengthen prompts.yaml</name>
<files>
  - chain_publisher_core.py (modified — add new function)
  - config/prompts.yaml (modified — strengthen pipe rule)
  - test_chain_publisher_core.py (modified — add tests)
</files>
<action>
Add `_clean_markdown_symbols()` to `chain_publisher_core.py` as a module-level function:

```python
def _clean_markdown_symbols(body: str) -> str:
    """
    Clean markdown symbols that would leak as literal text in rendered HTML.
    Operates on body text only (frontmatter already extracted).
    
    PROTECTED — never modified:
    - <!--todo:image--> / <!--todo:chart--> markers
    - Code blocks (``` fences)
    - Inline code (backtick)
    - Table lines (lines starting with | preceded by blank line)
    - Math blocks ($$) and inline math ($)
    
    Rules:
    1. Escape loose pipes (|) outside protected contexts — replace with \|.
    2. Fix bold/italic spacing for CJK text (space around ** and *).
    3. Remove orphaned markdown delimiters (unmatched ** pairs).
    """
    lines = body.split('\n')
    result = []
    in_code_block = False
    in_math_block = False
    
    for line in lines:
        stripped = line.strip()
        
        # PROTECTED: code blocks
        if stripped.startswith('```'):
            in_code_block = not in_code_block
            result.append(line)
            continue
        if in_code_block:
            result.append(line)
            continue
        
        # PROTECTED: math blocks
        if stripped.startswith('$$'):
            in_math_block = not in_math_block
            result.append(line)
            continue
        if in_math_block:
            result.append(line)
            continue
        
        # PROTECTED: image/comment markers
        if '<!--todo:' in stripped:
            result.append(line)
            continue
        
        # PROTECTED: table lines (starts with | after blank line)
        if stripped.startswith('|') and re.match(r'^\||^[-|:\s]+$', stripped):
            result.append(line)
            continue
        
        # PROTECTED: inline math ($...$)
        # (skip lines that are entirely inline math)
        stripped_no_math = re.sub(r'\$[^\$]+\$', '', stripped)
        if not stripped_no_math.strip():
            result.append(line)
            continue
        
        # Rule 1: Escape loose pipes in non-table context
        line = line.replace('|', '\\|')
        
        # Rule 2: Fix bold/italic spacing for CJK text
        line = re.sub(
            r'([\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af])\*\*',
            r'\1 **', line
        )
        line = re.sub(
            r'\*\*([\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af])',
            r'** \1', line
        )
        line = re.sub(
            r'([\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af])\*(\S)',
            r'\1 *\2', line
        )
        line = re.sub(
            r'(\S)\*([\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af])',
            r'\1* \2', line
        )
        
        # Rule 3: Handle unmatched bold/italic delimiters
        bold_count = line.count('**')
        if bold_count % 2 != 0:
            last_idx = line.rfind('**')
            if last_idx >= 0:
                line = line[:last_idx] + line[last_idx+2:]
        
        result.append(line)
    
    return '\n'.join(result)
```

**Call site** — In `_publish_hugo()` after `_extract_clean_body()` (~line 574):
```python
cleaned = _extract_clean_body(text)
# Phase 13 R2: clean markdown symbols before FM reassembly
cleaned_body = _clean_markdown_symbols(cleaned.body)
_fm_match = re.search(r'^---\n.*?\n---\n', _fixed, re.DOTALL)
_fm_block = _fm_match.group(0) if _fm_match else ""
text = _fm_block + cleaned_body if _fm_block else cleaned_body
```

Also apply the same in `_publish_blogger()` after line 650:
```python
cleaned = _extract_clean_body(body)
body = _clean_markdown_symbols(cleaned.body)
```

**prompts.yaml change** — Add after `- 표를 사용했는가?`:
```yaml
  - 파이프(|) 문자는 반드시 표 안에서만 사용할 것. 본문 텍스트에서 | 문자를 절대 사용하지 말 것.
```

**Tests** — Add `TestCleanMarkdownSymbols` in `test_chain_publisher_core.py`:
- `test_escapes_loose_pipes_in_prose`
- `test_preserves_table_pipes` — `|` lines unchanged
- `test_preserves_image_markers` — `<!--todo:image-->` unchanged (NEW: protection)
- `test_preserves_chart_markers` — `<!--todo:chart-->` unchanged (NEW: protection)
- `test_preserves_code_blocks` — inside ``` unchanged
- `test_preserves_inline_code` — backtick content unchanged (NEW: protection)
- `test_preserves_math` — `$...$` and `$$` unchanged (NEW: protection)
- `test_fixes_cjk_bold_spacing` — spacing correction
- `test_handles_unmatched_bold` — odd `**` stripped
- `test_empty_body` — empty string returns empty
</action>
<verify>
<automated>cd /Users/twinssn/projects2/mc && python -m pytest test_chain_publisher_core.py -x -q 2>&1 | tail -3</automated>
</verify>
<done>_clean_markdown_symbols() handles pipes, protects markers/tables/code/math, fixes CJK bold spacing; prompts.yaml pipe rule added; all tests pass.</done>
</task>

<verification>
### Wave 1 Verification
1. [ ] `python -m pytest test_chain_publisher_core.py -x -q` — all publisher tests pass
2. [ ] `python -c "from chain_publisher_core import _clean_markdown_symbols; print('OK')"` — imports succeed
3. [ ] `_clean_markdown_symbols('<!--todo:image-->')` → marker preserved
4. [ ] `_clean_markdown_symbols('```\npipe | here\n```')` → code block preserved
5. [ ] `_clean_markdown_symbols('| H1 | H2 |\n| --- | --- |')` → table preserved
6. [ ] `grep '파이프' config/prompts.yaml` — pipe rule added
7. [ ] `grep -n '_extract_clean_body' chain_publisher_core.py` — NOT modified
</verification>

---

## Wave 2 — Image Relevance (R1)

### Context

Current `build_full_prompt()` uses only `image_keyword` + `blog_key`. This wave adds:

1. **`build_contextual_prompt()`** — uses title + angle + seed_keyword
2. **`image/search_providers.py`** — Unsplash/Pexels body-image search with 24h cache + fallback
3. **Wiring** — updates `_publish_hugo()` photo branch

### Tasks

<task type="auto">
<name>Task 2.1: Add contextual image prompt builder</name>
<files>
  - image/prompt_builder.py (modified)
  - test_image_pipeline.py (add tests)
</files>
<action>
Add `build_contextual_prompt()` to `image/prompt_builder.py`:

```python
def build_contextual_prompt(
    image_keyword: str,
    title: str,
    blog_key: str,
    post_angle: str = "",
    seed_keyword: str = "",
    step: int = 1,
    chain_type: str = "depth",
) -> str:
```

Reuses existing `get_image_style_for_blog()` and `POLLINATIONS_NEGATIVE`. Replace `"主題: {image_keyword}"` with:
```
f"Article about '{title}' focusing on {image_keyword}"
if post_angle: f" from the perspective of {post_angle}"
```

Do NOT modify existing `build_full_prompt()`.

**Tests** — Add test function (in `test_image_pipeline.py`):
- `test_contextual_prompt_contains_title_and_keyword` — title + angle in output
- `test_contextual_prompt_no_raw_subject` — no "主題:" prefix
</action>
<verify>
<automated>cd /Users/twinssn/projects2/mc && python -m pytest test_image_pipeline.py -x -q 2>&1 | tail -3</automated>
</verify>
<done>`build_contextual_prompt()` exists, uses title+angle, tests pass.</done>
</task>

<task type="auto">
<name>Task 2.2: Create body-image search providers module with cache + fallback</name>
<files>
  - image/search_providers.py (new file)
  - test_image_search.py (add tests)
</files>
<action>
Create `image/search_providers.py` with:

### 1. `search_body_image(keyword, slug) -> tuple[Path, str] | None`
- Main entry point. Searches: Unsplash → Pexels → (both fail → return None → pipeline falls back to Pollinations)
- source_name: `"unsplash"` | `"pexels"`
- Landscape orientation, no text overlay, saved as `body_{slug}_{source}_{id}.webp`

### 2. Cache (24h TTL)
```python
import hashlib, time, json, os

_CACHE_DIR = "output/image_cache"
_CACHE_TTL = 86400  # 24h

def _cache_key(keyword: str) -> str:
    return hashlib.md5(keyword.encode()).hexdigest()

def _read_cache(key: str) -> dict | None:
    path = os.path.join(_CACHE_DIR, f"{key}.json")
    if os.path.exists(path):
        data = json.load(open(path))
        if time.time() - data["ts"] < _CACHE_TTL:
            return data
    return None

def _write_cache(key: str, result: dict):
    os.makedirs(_CACHE_DIR, exist_ok=True)
    result["ts"] = time.time()
    json.dump(result, open(os.path.join(_CACHE_DIR, f"{key}.json"), "w"))
```
- Cache key: `md5(keyword)` 
- Cache hit → skip API call, use cached `(path, source)`
- Cache miss → call API → store result in cache
- Cache expired → re-call API, update cache

### 3. API Keys — from `.env.common`, no hardcoding
```python
import os
_UNSPLASH_KEY = os.environ.get("UNSPLASH_ACCESS_KEY")
_PEXELS_KEY = os.environ.get("PEXELS_API_KEY")
```
- If key missing → skip that provider (silent, no crash)
- No default/fallback key in code

### 4. Fallback behavior
- `search_body_image()` returns `None` in ALL failure cases:
  - API key missing
  - Network error (requests exception)
  - Empty search results
  - Rate limited (HTTP 429)
- No retry — caller (pipeline) retries on next publish
- Caller: `_publish_hugo()` photo branch → if `search_body_image` returns None → fall through to Pollinations (existing image_keyword path)

### 5. Reuse from thumbnail.py
- `from image.thumbnail import UnsplashProvider, PexelsProvider`
- Do NOT duplicate class definitions
- No circular import risk (thumbnail doesn't import search_providers)

**Tests** — Add to `test_image_search.py`:
- `test_search_success` — mock Unsplash.search returns result → file saved
- `test_search_empty` — all providers return empty → None
- `test_search_rate_limited` — HTTP 429 → None (no retry)
- `test_cache_hit` — cached result returned without API call
- `test_cache_expired` — expired cache → re-call API
- `test_api_key_missing` — no env key → skip provider silently
</action>
<verify>
<automated>cd /Users/twinssn/projects2/mc && python -m pytest test_image_search.py -x -q 2>&1 | tail -3</automated>
</verify>
<done>search_providers.py exists with search_body_image, 24h cache, env-based keys, Pollinations fallback, no retry; tests pass.</done>
</task>

<task type="auto">
<name>Task 2.3: Wire search providers + contextual prompts into publish pipeline</name>
<files>
  - chain_publisher_core.py (modified — photo branch wiring)
</files>
<action>
Modify `_publish_hugo()` photo branch (~line 443):

1. **Try search providers first** (before Pollinations):
```python
elif _img_type == "photo":
    _photo_path = None
    _photo_src = None
    # Phase 13 R1: try real photo search first
    try:
        from image.search_providers import search_body_image
        _body_result = search_body_image(_kw or title, slug=slug)
        if _body_result:
            _photo_path, _photo_src = _body_result
    except Exception:
        pass  # fall through to Pollinations
    
    if not _photo_path:
        # Use contextual prompt for Pollinations
        try:
            from image.prompt_builder import build_contextual_prompt
            _contextual_prompt = build_contextual_prompt(
                image_keyword=_kw or "",
                title=title,
                blog_key=blog_cfg.get("name", ""),
                post_angle=_image_meta.get("angle", ""),
            )
        except Exception:
            _contextual_prompt = _img_keyword  # fallback
        
        from image.pollinations_client import generate_image as _gen_photo
        _photo_result = _gen_photo(_contextual_prompt, slug=slug)
        # ... existing photo handling code ...
```

2. **Backward compatibility** — try/except around imports; if search_body_image or build_contextual_prompt fail, existing behavior preserved.

3. **Minimal change** — Only photo branch. Chart/none branches untouched.
</action>
<verify>
<automated>cd /Users/twinssn/projects2/mc && python -m pytest test_chain_publisher_core.py -x -q 2>&1 | tail -3</automated>
</verify>
<done>Photo branch tries search providers first, falls back to contextual Pollinations; try/except wrappers for safety; tests pass.</done>
</task>

<verification>
### Wave 2 Verification
1. [ ] `python -m pytest test_image_pipeline.py -x -q` — all image tests pass
2. [ ] `python -m pytest test_image_search.py -x -q` — all search tests pass
3. [ ] `python -m pytest test_chain_publisher_core.py -x -q` — all publisher tests pass
4. [ ] `python -c "from image.prompt_builder import build_contextual_prompt; p = build_contextual_prompt('kw', 'Title', 'rotcha'); assert 'Title' in p"` — contextual prompt works
5. [ ] `python -c "from image.search_providers import search_body_image; print('OK')"` — module loads
6. [ ] `ls output/image_cache/ | head -3` — cache directory exists (after test)
7. [ ] `grep 'UNSPLASH_ACCESS_KEY\|PEXELS_API_KEY' image/search_providers.py` — env-based, no hardcoding
</verification>

---

## Full Test Suite

<task type="auto">
<name>Task 3: Full test suite — target 120/120</name>
<files>
  - (no new code — run tests only)
</files>
<action>
Run the complete test suite and verify 120/120:

```bash
cd /Users/twinssn/projects2/mc && python -m pytest -x -q
```

Expected: 120 tests (112 existing + 8 new).

New test count breakdown:
| Source | Tests | Files |
|--------|-------|-------|
| Task 1.1: _clean_markdown_symbols | 2 new | test_chain_publisher_core.py |
| Task 2.1: contextual prompt | 1 new | test_image_pipeline.py |
| Task 2.2: search providers | 4 new | test_image_search.py |
| Task 3: integration wiring | 1 new | test_chain_publisher_core.py |
| **Total new** | **8** | |
| **Existing** | **112** | |
| **Grand total** | **120** | |

If any test fails, fix immediately. If test count differs from 120, count and report cause.
</action>
<verify>
<automated>cd /Users/twinssn/projects2/mc && python -m pytest -x -q 2>&1 | tail -3</automated>
</verify>
<done>Full test suite passes at 120/120.</done>
</task>

---

## Phase 13.1 — 이월 항목 (v1.1, not in scope for Phase 13)

The following items are NOT implemented in Phase 13. Planned for Phase 13.1:

1. **이미지 캐시 히트율 대시보드** — cache hit/miss/expire 통계 수집 및 리포팅
2. **사이트별 이미지 전략 분기** — techpawz는 stock photo(Unsplash/Pexels)가 부적합할 가능성. 사이트별 provider 선택 로직 필요

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **CJK spacing regex over-corrects** | Medium | Low — cosmetic | Test with CJK/ASCII mixed inputs |
| **Touches image markers in _clean_markdown_symbols** | Low | High — broken images | Explicit `<!--todo:` protection check before any cleanup |
| **112-test regression** | Low | High — pipeline breakage | Do NOT modify `_extract_clean_body()`; new functions are independent |
| **API rate limiting on first publish** | Medium | Low — falls through to Pollinations | No retry; next publish retries cache-miss |
| **Cache corruption (stale data)** | Low | Low — 24h TTL auto-expires | TTL check on read; TTL expired = re-fetch |
| **Import errors in photo branch wiring** | Low | Medium — photo gen fails | try/except around new imports; fall back to existing |
| **Missing .env.common keys** | Medium | Low — skips search provider silently | Provider skipped, falls through to Pollinations |

---

## Success Criteria

- [ ] Wave 1 complete: `_clean_markdown_symbols()` implemented with protection for markers/tables/code/math
- [ ] Wave 2 complete: `build_contextual_prompt()`, `search_body_image()` with 24h cache + fallback, wiring
- [ ] `config/prompts.yaml` has strengthened pipe-use rule
- [ ] **pytest 120/120** (`python -m pytest -x -q`)
- [ ] `_extract_clean_body()` not modified
- [ ] W1-W6 code, 19/27 guard, `_ensure_featureimage`, rerank=false not modified
- [ ] Phase 13.1 items noted but NOT implemented
