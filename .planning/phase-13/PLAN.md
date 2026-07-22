---
phase: 13-content-refinement
plan: 01
type: execute
wave: 1-2
depends_on: []
files_modified:
  - image/prompt_builder.py
  - image/search_providers.py
  - chain_publisher_core.py
  - config/prompts.yaml
autonomous: true
requirements:
  - R1
  - R2
  - R3
user_setup: []
must_haves:
  truths:
    - "Pollinations images use article title + angle in prompt, not just keyword"
    - "Unsplash/Pexels body images are used when image_type=photo, not just thumbnails"
    - "Raw markdown symbols (**, *, |, -) outside table context are cleaned before Hugo build"
    - "Markdown tables render as HTML <table> in published Hugo pages, not as literal text"
    - "No leakage of literal pipe/bold/italic characters in published HTML"
    - "All 112 existing pytest tests still pass"
  artifacts:
    - path: "image/prompt_builder.py"
      provides: "build_contextual_prompt() — contextual prompt with title+angle"
      min_lines: 95
    - path: "image/search_providers.py"
      provides: "Body-image search from Unsplash/Pexels (no text overlay)"
      min_lines: 150
    - path: "chain_publisher_core.py"
      provides: "_clean_markdown_symbols() and _convert_tables_to_html() functions"
      min_lines: 980
    - path: "chain_publisher_core.py"
      provides: "Wired post-processing in _publish_hugo() and _publish_blogger()"
      pattern: "_clean_markdown_symbols|_convert_tables_to_html"
    - path: "config/prompts.yaml"
      provides: "Strengthened pipe-use rule"
      contains: "파이프"
  key_links:
    - from: "_publish_hugo() photo branch"
      to: "image/search_providers.py search_body_image()"
      via: "import and call before Pollinations fallback"
      pattern: "search_body_image|UnsplashProvider|PexelsProvider"
    - from: "_publish_hugo() post-processing"
      to: "_clean_markdown_symbols()"
      via: "called after _extract_clean_body() before index.md write"
      pattern: "_clean_markdown_symbols"
    - from: "_publish_hugo() post-processing"
      to: "_convert_tables_to_html()"
      via: "called after _clean_markdown_symbols() before index.md write"
      pattern: "_convert_tables_to_html"
---

# Phase 13 — 콘텐츠 고도화 (Content Refinement)

<objective>
Phase 1–12에서 파이프라인 안정화 완료. Phase 13은 콘텐츠 품질을 고도화한다: 이미지 관련성 개선 (contextual prompts + Unsplash/Pexels body images), 마크다운 기호 누출 제거 (_clean_markdown_symbols), 표 렌더링 깨짐 수정 (_convert_tables_to_html). 모든 변경은 기존 112개 테스트를 유지하면서 진행한다.

Purpose: 발행 품질 향상 — 이미지가 주제와 관련되고, HTML에 마크다운 기호가 보이지 않으며, 표가 정상 렌더링되도록 개선
Output: image/prompt_builder.py (contextual prompt), image/search_providers.py (new), chain_publisher_core.py (2 new functions + wiring), config/prompts.yaml (pipe rule 강화)
</objective>

## Phase Goal

**As a** blog operator running the mc pipeline, **I want to** publish posts with contextually relevant images, no leaked markdown symbols, and properly rendered tables, **so that** readers have a polished experience without manual post-editing.

## Multi-Source Coverage Audit

| Source Item | Source Type | Covered By | Notes |
|-------------|-------------|------------|-------|
| R1: Image Relevance | CONTEXT/RESEARCH | Wave 1 | Contextual prompts + search providers |
| R2: Markdown Symbol Leakage | CONTEXT/RESEARCH | Wave 2 | `_clean_markdown_symbols()` + prompts.yaml |
| R3: Table Rendering | CONTEXT/RESEARCH | Wave 2 | `_convert_tables_to_html()` |
| R4: CSS (no action) | CONTEXT | — | Noted, no work needed |
| 112 baseline maintained | CONSTRAINT | Both waves | New tests added, existing untouched |
| Do NOT modify _extract_clean_body() | CONSTRAINT | Wave 2 | New functions are post-processing |
| Do NOT touch 19/27 guard | CONSTRAINT | Both waves | Not in scope |
| Do NOT touch _ensure_featureimage | CONSTRAINT | Both waves | Not in scope |
| W1-W5 code untouched | CONSTRAINT | Both waves | Only new code added |

**Status:** ✅ All items covered. No gaps.

---

## Wave Structure

| Wave | Plans | Requirement | Files |
|------|-------|-------------|-------|
| 1 | 13-01-PLAN.md (combined) | R1 (Image Relevance) | prompt_builder.py, search_providers.py (new), chain_publisher_core.py |
| 2 | 13-01-PLAN.md (combined) | R2+R3 (Markdown + Tables) | chain_publisher_core.py, prompts.yaml, test_chain_publisher_core.py |

**Rationale for wave separation:** R1 and R2+R3 both modify `chain_publisher_core.py` — R1 touches the photo-generation branch (~line 443), R2+R3 add new functions and post-processing pipeline (~line 569). Wave separation prevents merge conflicts when the executor modifies the same file.

---

## Wave 1 — Image Relevance (R1)

### Context

Current `build_full_prompt()` in `image/prompt_builder.py` uses only `image_keyword` + `blog_key` to build prompts. The image keyword from AI is often generic (e.g., "exam-preparation"). This plan adds:

1. **`build_contextual_prompt()`** — uses title + angle + seed_keyword for richer context
2. **`image/search_providers.py`** — extracts `UnsplashProvider`/`PexelsProvider` patterns from `thumbnail.py` for body-image search (landscape ratio, no text overlay)
3. **Wiring** — updates `_publish_hugo()` photo branch to use contextual prompts and try search providers before Pollinations fallback

### Runtime Interfaces

From `image/thumbnail.py` (extracted patterns):
```python
class UnsplashProvider:
    def search(self, query, per_page=5) -> list[dict]
    def download(self, photo) -> Optional[Path]

class PexelsProvider:
    def search(self, query, per_page=5) -> list[dict]
    def download(self, photo) -> Optional[Path]
```

From `image/prompt_builder.py` (existing):
```python
POLLINATIONS_STYLE_MAP = { "rotcha": "...", "informationhot": "...", "techpawz": "..." }
POLLINATIONS_NEGATIVE = "text, watermark, signature..."
get_image_style_for_blog(blog_key) -> str
build_full_prompt(image_keyword, blog_key, chain_type, step) -> str
```

From `chain_publisher_core.py` _publish_hugo photo branch (~line 443):
```python
elif _img_type == "photo":
    from image.pollinations_client import generate_image as _gen_photo
    _photo_result = _gen_photo(_img_keyword, slug=slug)
```

### Tasks

<task type="auto">
<name>Task 1.1: Add contextual image prompt builder</name>
<files>
  - image/prompt_builder.py (modified)
  - test_image_pipeline.py (add tests for contextual prompt)
</files>
<action>
Add `build_contextual_prompt()` to `image/prompt_builder.py` — new function with signature:

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

The function reuses existing `get_image_style_for_blog()` and `POLLINATIONS_NEGATIVE`. Replace the `"主題: {image_keyword}"` line with a contextual block:

```
f"Article about '{title}' focusing on {image_keyword}"
if post_angle: f" from the perspective of {post_angle}"
```

Keep all other parts of the prompt unchanged (style, step/chain context, negative).

Do NOT modify the existing `build_full_prompt()` — keep it for backward compatibility. The new function is called by the publisher wire in Task 1.3.

Add tests: write a test function (in an existing or new test file) that:
- Calls `build_contextual_prompt()` with sample title + angle + keyword
- Asserts the output contains the article title and keyword
- Asserts the output does NOT contain the raw "主題:" prefix
</action>
<verify>
<automated>cd /Users/twinssn/projects2/mc && python -m pytest test_image_pipeline.py -x -q 2>&1 | tail -3</automated>
</verify>
<done>`build_contextual_prompt()` exists, builds prompts using title+angle, existing tests pass, prompt contains article context and keyword.</done>
</task>

<task type="auto">
<name>Task 1.2: Create body-image search providers module</name>
<files>
  - image/search_providers.py (new file)
  - test_image_search.py (add tests for search providers)
</files>
<action>
Create `image/search_providers.py` that provides body-image search from Unsplash and Pexels (no text overlay, landscape/16:9 aspect ratio suited for inline body images).

Structure:

1. **`search_body_image(keyword: str, slug: str = "") -> tuple[Path, str] | None`**
   - Main entry point. Searches Unsplash → Pexels → Pollinations fallback.
   - Returns `(path, source_name)` or `None` if all providers fail.
   - source_name: `"unsplash"` | `"pexels"` | `"pollinations"`

2. **Reuse `UnsplashProvider` and `PexelsProvider` from `image/thumbnail.py`**
   - Import the classes directly: `from image.thumbnail import UnsplashProvider, PexelsProvider`
   - Do NOT duplicate the class definitions — this avoids maintenance burden.
   - Use `_load_env()` from `thumbnail.py` for API keys (or re-implement env loading locally).

3. **Search parameters for body images:**
   - Unsplash: `orientation="landscape"` (not "squarish" like thumbnail)
   - Pexels: `orientation="landscape"` (not "square")
   - Download at larger resolution: `&w=1600&h=900&fit=crop` for Unsplash

4. **No text overlay** — unlike thumbnails which call `add_text_overlay()`, body images are raw downloads saved as `body_{slug}_{source}_{id}.webp` in `output/images/`.

5. **Pollinations fallback** — if both Unsplash and Pexels return no results, import and call `image.pollinations_client.generate_image(prompt, slug=slug)` using a contextual prompt.

Add tests:
- Mock UnsplashProvider.search to return a result → assert download is called and file saved
- Mock all providers to return empty → assert None returned
- Verify image is saved as .webp (not .jpg)

**Key constraint:** Do NOT import or create a circular dependency — `thumbnail.py` imports from `image.pollinations_client` as a fallback; `search_providers.py` should also handle its own fallback chain but avoid importing `thumbnail.py` circularly. Use direct class imports from `thumbnail` (safe since thumbnail has no `search_providers` import).
</action>
<verify>
<automated>cd /Users/twinssn/projects2/mc && python -m pytest test_image_pipeline.py test_image_search.py -x -q 2>&1 | tail -3</automated>
</verify>
<done>`image/search_providers.py` exists with `search_body_image()` function, imports providers from thumbnail.py, searches Unsplash/Pexels with landscape orientation, falls back to Pollinations, tests pass.</done>
</task>

<task type="auto">
<name>Task 1.3: Wire search providers + contextual prompts into publish pipeline</name>
<files>
  - chain_publisher_core.py (modified)
</files>
<action>
Modify the `_publish_hugo()` photo generation branch (~line 443) to:

1. **Use contextual prompt** — Before calling `pollinations_client.generate_image()`, construct the prompt using:
   ```python
   from image.prompt_builder import build_contextual_prompt
   _contextual_prompt = build_contextual_prompt(
       image_keyword=_kw or "",
       title=title,
       blog_key=blog_cfg.get("name", ""),  # or determine blog_key from context
       post_angle=_image_meta.get("angle", ""),
       seed_keyword=_image_meta.get("seed_keyword", ""),
       step=_image_meta.get("step", 1),
       chain_type=_image_meta.get("chain_type", "depth"),
   )
   ```
   Then pass `_contextual_prompt` instead of just `_img_keyword` to Pollinations.

   **Important:** Determine `blog_key` from context — the method receives `blog_cfg` dict which may have a `name` or `blog_id` field. Use `blog_cfg.get("blog_id", "").replace("manual_", "")` as blog_key, or fall back to extracting from the site config.

2. **Add search providers before Pollinations** — When `_img_type == "photo"`, before falling back to Pollinations:
   ```python
   # Try real photo search first (body-image providers)
   try:
       from image.search_providers import search_body_image
       _body_result = search_body_image(_kw or title, slug=slug)
       if _body_result:
           _photo_path, _photo_src = _body_result
           # same DB update + assets copy as existing photo code
   except Exception:
       pass  # fall through to Pollinations
   ```

   Structure the flow as: try search providers → if None or error, use Pollinations with contextual prompt.

3. **Minimal change** — Only modify the photo branch. Do NOT touch chart, none, or other branches. Do NOT touch W1-W5 code or 19/27 guard.

4. **Backward compatibility** — If `build_contextual_prompt` import fails or `search_body_image` import fails, fall back to the existing behavior without crashing. Use try/except around the import and call.

No new tests needed for this task since the wiring is thin glue code; existing _publish_hugo integration tests (mocked) should still pass.
</action>
<verify>
<automated>cd /Users/twinssn/projects2/mc && python -m pytest test_chain_publisher_core.py -x -q 2>&1 | tail -3</automated>
</verify>
<done>Photo branch uses contextual prompts and tries search providers before Pollinations; all 112+ tests pass.</done>
</task>

<verification>
### Wave 1 Verification
1. [ ] `python -m pytest test_image_pipeline.py -x -q` — all image tests pass
2. [ ] `python -m pytest test_chain_publisher_core.py -x -q` — all publisher tests pass
3. [ ] `python -c "from image.prompt_builder import build_contextual_prompt; p = build_contextual_prompt('test', 'Title', 'rotcha', angle='angle'); assert 'Title' in p; assert 'test' in p"` — contextual prompt works
4. [ ] `python -c "from image.search_providers import search_body_image; print('Module loaded')"` — module loads without error
5. [ ] Total test count >= 112
</verification>

---

## Wave 2 — Markdown Cleanup + Table Rendering (R2 + R3)

### Context

Two independent post-processing functions are added to `chain_publisher_core.py`. Both are called in `_publish_hugo()` and `_publish_blogger()` after `_extract_clean_body()` runs:

```
_extract_clean_body(text) → cleaned.body
  → _clean_markdown_symbols(cleaned.body)    [R2: markdown cleanup first — preserves table | lines]
  → _convert_tables_to_html(result)          [R3: then convert preserved tables to <table> HTML]
  → assemble with FM → write index.md
```

### Runtime Interfaces

From `chain_publisher_core.py` (existing post-processing at ~line 569):
```python
cleaned = _extract_clean_body(text)
_fm_match = re.search(r'^---\n.*?\n---\n', _fixed, re.DOTALL)
_fm_block = _fm_match.group(0) if _fm_match else ""
text = _fm_block + cleaned.body if _fm_block else cleaned.body
index_md.write_text(text, encoding="utf-8")
```

### Tasks

<task type="auto">
<name>Task 2.1: Implement _clean_markdown_symbols() + strengthen prompts.yaml</name>
<files>
  - chain_publisher_core.py (modified — add new function)
  - config/prompts.yaml (modified — strengthen pipe rule)
  - test_chain_publisher_core.py (modified — add tests)
</files>
<action>
Add `_clean_markdown_symbols()` to `chain_publisher_core.py` as a module-level function (not a method of PublisherCore):

```python
def _clean_markdown_symbols(body: str) -> str:
    """
    Clean markdown symbols that would leak as literal text in rendered HTML.
    Operates on body text only (frontmatter already extracted).
    
    Rules:
    1. Escape loose pipes (|) outside table context — replace with &vert; or remove.
    2. Fix bold/italic spacing for CJK text (ensure space around ** and *).
    3. Remove orphaned markdown delimiters (unmatched ** or * pairs).
    """
    lines = body.split('\n')
    result = []
    in_code_block = False
    
    for line in lines:
        stripped = line.strip()
        
        # Skip code blocks entirely
        if stripped.startswith('```'):
            in_code_block = not in_code_block
            result.append(line)
            continue
        if in_code_block:
            result.append(line)
            continue
        
        # Skip table lines (will be handled by _convert_tables_to_html)
        if stripped.startswith('|') and re.match(r'^\||^[-|:\s]+$', stripped):
            result.append(line)
            continue
        
        # Rule 1: Escape loose pipes in non-table context
        # Replace | with HTML entity only when it appears in prose paragraphs
        # that are NOT part of a table (tables caught by check above)
        line = line.replace('|', '\\|')
        
        # Rule 2: Fix bold/italic spacing for CJK text
        # Ensure there's a space before ** when preceded by a CJK character
        # and a space after ** when followed by a CJK character
        # Pattern: (CJK)**text  →  (CJK) **text  (add space before)
        line = re.sub(
            r'([\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af])\*\*',
            r'\1 **', line
        )
        # Pattern: **text(CJK)  →  **text (CJK)  (add space after closing)
        line = re.sub(
            r'\*\*([\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af])',
            r'** \1', line
        )
        
        # Same for single * (italic)
        line = re.sub(
            r'([\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af])\*(\S)',
            r'\1 *\2', line
        )
        line = re.sub(
            r'(\S)\*([\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af])',
            r'\1* \2', line
        )
        
        # Rule 3: Handle unmatched bold/italic delimiters
        # Count ** pairs — if odd number, remove the last lone **
        bold_count = line.count('**')
        if bold_count % 2 != 0:
            # Remove the last ** occurrence
            last_idx = line.rfind('**')
            if last_idx >= 0:
                line = line[:last_idx] + line[last_idx+2:]
        
        result.append(line)
    
    return '\n'.join(result)
```

**Call site** — In `_publish_hugo()` after `_extract_clean_body()` and before FM reassembly (around line 574):

```python
cleaned = _extract_clean_body(text)
# Phase 13 R2: clean markdown symbols before FM reassembly
cleaned_body = _clean_markdown_symbols(cleaned.body)
# Phase 13 R3: convert markdown tables to HTML
cleaned_body = _convert_tables_to_html(cleaned_body)
_fm_match = re.search(r'^---\n.*?\n---\n', _fixed, re.DOTALL)
_fm_block = _fm_match.group(0) if _fm_match else ""
text = _fm_block + cleaned_body if _fm_block else cleaned_body
```

Also apply the same in `_publish_blogger()` after line 650:
```python
cleaned = _extract_clean_body(body)
cleaned_body = _clean_markdown_symbols(cleaned.body)
cleaned_body = _convert_tables_to_html(cleaned_body)
body = cleaned_body
```

**prompts.yaml change** — In the draft user prompt section, around line 288 (the checklist), find the line `- 표를 사용했는가?` and add a new rule after it:
```yaml
  - 표를 사용했는가?
  - 파이프(|) 문자는 반드시 표 안에서만 사용할 것. 본문 텍스트에서 | 문자를 절대 사용하지 말 것.
```

**Tests** — Add a new test class `TestCleanMarkdownSymbols` in `test_chain_publisher_core.py` with:
- `test_escapes_loose_pipes_in_prose` — prose paragraph with `|` should have it escaped
- `test_preserves_table_pipes` — line starting with `|` in table context should preserve `|`
- `test_fixes_cjk_bold_spacing` — `한글**텍스트` → `한글 **텍스트`
- `test_handles_unmatched_bold` — odd number of `**` stripped correctly
- `test_preserves_code_blocks` — content inside ``` fences not modified
- `test_empty_body` — empty string returns empty string
</action>
<verify>
<automated>cd /Users/twinssn/projects2/mc && python -m pytest test_chain_publisher_core.py -x -q 2>&1 | tail -3</automated>
</verify>
<done>_clean_markdown_symbols() handles pipes, CJK bold spacing, unmatched delimiters, code blocks; prompts.yaml has stronger pipe rule; all tests pass.</done>
</task>

<task type="auto">
<name>Task 2.2: Implement _convert_tables_to_html() + helpers</name>
<files>
  - chain_publisher_core.py (modified — add new functions)
  - test_chain_publisher_core.py (modified — add tests)
</files>
<action>
Add three new module-level functions to `chain_publisher_core.py` (after `_clean_markdown_symbols`):

1. **`_convert_tables_to_html(body: str) -> str`** — Main entry point.
   - Splits body into lines, detects table blocks (lines starting with `|` preceded by blank line or start of body)
   - Within each table block, collects all consecutive `|` lines
   - Passes them to `_parse_table_to_html()`
   - Replaces the table block with the resulting HTML
   - Preserves all non-table content unchanged

2. **`_parse_table_to_html(table_lines: list) -> str`** — Core converter.
   - Expects at least 2 lines (header + separator)
   - Extracts header cells via `_split_table_row()`
   - Parses alignment from separator row via `_parse_alignment()`
   - Builds `<table><thead><tr><th>...</th></tr></thead><tbody><tr><td>...</td></tr></tbody></table>`
   - Pads or truncates body rows to match header column count
   - Uses `text-align: {align}` inline style for alignment
   - Escapes `|` in cell content (replace remaining `|` with `&#124;`)

3. **`_split_table_row(row: str) -> list[str]`** — Cell splitter.
   - Strips leading/trailing `|`
   - Handles escaped pipes (`\|` → literal `|` during parse, NOT a separator)
   - Returns list of cell content strings

4. **`_parse_alignment(sep_row: str) -> list[str]`** — Alignment detector.
   - `:---:` → `"center"`
   - `---:` → `"right"`
   - `:---` → `"left"`
   - `----` → `""` (default)

These functions are already spec'd in the RESEARCH.md code examples. Use those as the reference implementation. Key behaviors to implement:

- **Inconsistent column counts:** Pad missing cells with empty string, truncate extra cells
- **Escaped pipes:** `\|` in cell content treated as literal `|`, not column separator
- **Minimal table lines (1):** Return the raw line(s) unchanged (not a table without separator)
- **HTML safety:** No user-controlled attributes in `<table>`, `<th>`, `<td>` tags — only the `text-align` style from alignment

**Tests** — Add a new test class `TestConvertTablesToHtml` in `test_chain_publisher_core.py` with:
- `test_converts_simple_table` — basic table with header + 2 rows → valid `<table>` HTML
- `test_handles_inconsistent_columns` — extra cell in body row → padded/truncated
- `test_handles_alignment` — `:---`, `:---:`, `---:` → correct `text-align` styles
- `test_handles_escaped_pipes` — `\|` in cell → not treated as separator
- `test_preserves_non_table_content` — headings, paragraphs, lists unchanged
- `test_single_line_not_table` — one `|` line with no separator → passed through unchanged
- `test_empty_body` — returns empty string
- `test_handles_missing_separator` — 1+ `|` row without separator row → pass through unchanged (must have 2+ lines to be a table)

**Important:** These tests must NOT modify or depend on `_extract_clean_body()`. They test the table converter functions in isolation.
</action>
<verify>
<automated>cd /Users/twinssn/projects2/mc && python -m pytest test_chain_publisher_core.py -x -q 2>&1 | tail -3</automated>
</verify>
<done>_convert_tables_to_html() and helper functions handle standard tables, alignment, inconsistent columns, escaped pipes; all tests pass.</done>
</task>

<task type="auto">
<name>Task 2.3: Wire both functions into publish pipeline + full test run</name>
<files>
  - chain_publisher_core.py (modified — integration wiring already done in Task 2.1)
  - test_chain_publisher_core.py (modified — integration tests)
</files>
<action>
**This task validates the wiring done in Task 2.1's call site changes and ensures end-to-end correctness.**

Add integration tests that verify the pipeline wiring works correctly:

1. **`test_clean_markdown_wired_in_publish_hugo`** in `TestPublishHugoIntegration`:
   - Mock the full _publish_hugo flow (same pattern as existing test_publish_hugo_full_flow)
   - Include draft_md with problematic markdown (loose `|`, CJK bold without spacing)
   - Assert that the final `index_md.write_text()` call receives cleaned content
   - Use `unittest.mock.patch` on `_clean_markdown_symbols` to verify it was called

2. **`test_tables_converted_in_publish_hugo`**:
   - Similar mock setup
   - Include draft_md with GFM table
   - Assert that final `index_md.write_text()` call contains `<table>` and no raw `|` from table

3. **`test_blogger_post_processing_wired`**:
   - Similar mock for _publish_blogger
   - Verify `_clean_markdown_symbols` and `_convert_tables_to_html` are called

Run the full test suite to confirm 112+ test baseline is maintained:

```bash
cd /Users/twinssn/projects2/mc && python -m pytest -x -q 2>&1
```

Count tests:
```python
import subprocess; result = subprocess.run(['python', '-m', 'pytest', '--collect-only', '-q'], capture_output=True, text=True); print(result.stderr.split()[-2])
```
</action>
<verify>
<automated>cd /Users/twinssn/projects2/mc && python -m pytest -x -q 2>&1 | tail -5</automated>
</verify>
<done>Full test suite passes with >= 112 tests; _clean_markdown_symbols and _convert_tables_to_html are called in both _publish_hugo() and _publish_blogger() post-processing.</done>
</task>

<verification>
### Wave 2 Verification
1. [ ] `python -c "from chain_publisher_core import _clean_markdown_symbols, _convert_tables_to_html; print('Functions imported')"` — imports succeed
2. [ ] `_clean_markdown_symbols('한글**테스트**')` → fixes CJK bold spacing
3. [ ] `_convert_tables_to_html('| H1 | H2 |\n| --- | --- |\n| C1 | C2 |')` → contains `<table>`
4. [ ] `grep '파이프' config/prompts.yaml` — pipe rule strengthened
5. [ ] Full `pytest -x -q` passes with >= 112 tests
6. [ ] `grep -n '_extract_clean_body' chain_publisher_core.py` — NOT modified (check git diff)
</verification>

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **CJK spacing regex over-corrects** | Medium | Low — cosmetic issue | Test with CJK-only and mixed CJK/ASCII inputs; use Unicode range filtering |
| **Table converter breaks on edge cases** | Medium | Medium — broken tables | Build test cases from actual AI output; fallback: pass through raw markdown if parse fails |
| **112-test regression** | Low | High — pipeline breakage | Do NOT modify `_extract_clean_body()`; new functions are independent; run full test suite after each task |
| **`_clean_markdown_symbols` removes intentional `\|`** | Medium | Medium — content loss | Only escape pipes in prose paragraphs, not in code blocks or tables; use `\\|` escape, not deletion |
| **Import errors in photo branch wiring** | Low | Medium — photo generation fails | Wrap imports in try/except; fall back to existing behavior |
| **Missing article context in `image_meta`** | Low | Low — uses empty defaults | All new params default to `""` or `1`; backward compatible |

---

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| image/search_providers.py → Unsplash/Pexels API | Untrusted external image downloads cross this boundary |
| Table HTML output | Generated HTML injected into Hugo markdown |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-13-01 | Tampering | `_convert_tables_to_html()` | mitigate | Use fixed HTML template — no user-controlled attributes in `<table>/<th>/<td>` tags. Only `text-align` style from alignment parse |
| T-13-02 | Spoofing | `search_body_image()` → URL | mitigate | URLs come from verified provider APIs (Unsplash/Pexels), not user input. Image bytes validated by requests library |
| T-13-03 | Spoofing | `_clean_markdown_symbols()` output | accept | Operates on already-sanitized body after `_extract_clean_body()` whitelist. No new injection vector |
| T-13-SC | Tampering | pip installs | mitigate | No new packages required per Package Legitimacy Audit |
</threat_model>

---

## Success Criteria

- [ ] Wave 1 complete: contextual prompt + search providers + wiring implemented and tested
- [ ] Wave 2 complete: `_clean_markdown_symbols()` and `_convert_tables_to_html()` implemented and wired
- [ ] `config/prompts.yaml` has strengthened pipe-use rule
- [ ] All 112+ tests pass (`python -m pytest -x -q`)
- [ ] `_extract_clean_body()` not modified (verified via `git diff`)
- [ ] W1-W5 code, 19/27 guard, `_ensure_featureimage` not modified
- [ ] Each function has standalone unit tests independent of the pipeline mocking

---

## Output

When executed, this phase produces:
- `.planning/phases/13-content-refinement/13-01-SUMMARY.md` (after execution)
