# Phase 8: Chart Generation (pillow_chart.py)

**Goal:** Add information-rich chart/table generation to the image pipeline. `image_type=chart` enables data visualization for posts containing numbers, comparisons, timelines — a strong E-E-A-T signal for rotcha.kr content.

**Prerequisite:** Phase 7 complete (thumbnail + content image pipeline operational).

## Current State (verified from live code)

| File | Phase 7 State | Phase 8 Extension Point |
|---|---|---|
| `chain_db.py:58` | `thumbnail_path`, `thumbnail_source`, `content_image_path`, `content_image_source` columns exist. No `chart_type`, `chart_data`, `image_reason`. | Add 3 columns + `update_chart()` helper |
| `chain_drafter.py:186` | `draft_single_post()` returns `draft_md` string. No image_type/chart logic. | Extend to return `(draft_md, meta_dict)`. Add `_insert_chart_marker()`. |
| `image/injector.py:15` | `_find_image_file(slug)` already searches `chart_{slug}.jpg`. `inject_images_into_draft()` only handles `<!--todo:image-->`. | Add `<!--todo:chart-->` marker replacement branch. |
| `chain_publisher_core.py:169` | `_publish_hugo()` calls `generate_thumbnail()` for cover. No content_image/chart path. | Add `image_type='chart'` branch calling `render_chart()`. |
| `config/chain_config.yaml` | No `chart:` section. | Add `chart:` config block. |

## Design Decisions

### Decision 1: GPT returns structured JSON, code renders
GPT outputs `chart_type` + `chart_data` JSON alongside draft_md. Code handles marker insertion and PIL rendering. No GPT-in-image, no code-in-prompt.

### Decision 2: `<!--todo:chart-->` marker is position-only
No data embedded in the marker. Data lives in DB `chart_data` column. Publisher reads DB, renders chart, injects figure.

### Decision 3: Font failure = exception, not warning
Chart without Korean text is meaningless. `render_chart()` raises `FileNotFoundError` if font missing. Publisher catches and falls back to `image_type='photo'`.

### Decision 4: Idempotency = content_image_path check
Same as Phase 7: if `content_image_path` is already set, skip generation. Force-regenerate requires deleting the DB value.

---

## Plan

### Task 8-1: chain_db.py — Chart Data Columns

**File:** `chain_db.py`

Add 3 columns to `chain_posts`:
```sql
ALTER TABLE chain_posts ADD COLUMN chart_type TEXT;      -- 'bar' | 'timeline' | 'comparison' | NULL
ALTER TABLE chain_posts ADD COLUMN chart_data TEXT;      -- JSON string, NULL if not chart
ALTER TABLE chain_posts ADD COLUMN image_reason TEXT;    -- LLM's 1-sentence rationale
```

Add `chart_type`/`chart_data`/`image_reason` to `MIGRATIONS_SQL`.

Add helper:
```python
def update_chart(post_id: int, chart_type: str, chart_data: str):
    """Save chart_type + chart_data (JSON string)."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    conn.execute(
        "UPDATE chain_posts SET chart_type = ?, chart_data = ?, updated_at = ? WHERE id = ?",
        (chart_type, chart_data, now, post_id),
    )
    conn.commit()
    conn.close()
```

**Verification:** `PRAGMA table_info(chain_posts)` shows `chart_type`, `chart_data`, `image_reason`.

---

### Task 8-2: pillow_chart.py (New Module)

**File:** `pillow_chart.py` (project root)

3 chart renderers + dispatcher. All return `(output_path, 'pillow_chart')`.

```python
def generate_bar_chart(data, title, slug, font_path, orientation="vertical", output_size=(1200, 630)):
    # data: {"items": [{"label": "...", "value": 78.5, "unit": "%"}, ...]}

def generate_timeline(events, title, slug, font_path, output_size=(1200, 630)):
    # events: [{"label": "...", "date": "2026-05-15"}, ...]

def generate_comparison(left, right, title, slug, font_path, output_size=(1200, 630)):
    # left/right: {"label": "...", "items": [{"key": "...", "value": "..."}]}

def render_chart(chart_type, chart_data, title, slug, font_path, output_size=(1200, 630)):
    # Dispatcher: routes to the correct renderer
```

Design specs:
- Background: `#FFFFFF` or `#F8F9FA`
- Title: top-center, NotoSansKR, 42pt
- Brand colors from config (`chart.colors.primary/secondary/tertiary`)
- Labels: Korean, 28pt, `#1F2937`
- Values: beside label or at bar end, 24pt
- Output: JPEG quality 92 (consistent with thumb_*.jpg)
- Margins: 80px left/right, 60px top/bottom
- Font missing → raise `FileNotFoundError` (not a warning)

**Verification:**
```python
python3 -c "
from pillow_chart import render_chart
data = {'items': [{'label': '합격률', 'value': 78.5, 'unit': '%'}, {'label': '불합격', 'value': 21.5, 'unit': '%'}]}
path, src = render_chart('bar', data, '테스트 차트', 'test-chart', 'assets/fonts/NotoSansKR-Regular.otf')
print(f'Created: {path}, source: {src}')
"
```

---

### Task 8-3: chain_drafter.py — GPT Chart Recognition

**File:** `chain_drafter.py`

**Modify `draft_single_post()`**: Change return from `str` to `tuple[str, dict]` where dict contains `image_type`, `image_keyword`, `image_reason`, `chart_type`, `chart_data`.

**GPT prompt addition** (to `prompts.yaml` `draft_user` template):

After the draft body, GPT must return a JSON block:
```json
{
  "image_type": "photo" | "chart" | "none",
  "image_keyword": "english keyword (photo only)",
  "image_reason": "1-sentence rationale",
  "chart_type": "bar" | "timeline" | "comparison" | null,
  "chart_data": {...} | null
}
```

Selection criteria:
- `chart`: numbers, comparisons, statistics, amounts, rates, dates, A vs B
- `photo`: concrete objects, situations, places, machines, food, animals, documents
- `none`: abstract/philosophical/strategic content where neither helps

chart_data schemas:
- bar: `{"items": [{"label": "...", "value": 숫자, "unit": "..."}], "orientation": "vertical"|"horizontal"}`
- timeline: `{"events": [{"label": "...", "date": "YYYY-MM-DD"}]}`
- comparison: `{"left": {"label": "...", "items": [{"key": "...", "value": "..."}]}, "right": {...}}`

**Modify `draft_chain()`**: Parse GPT output, validate schema, store in DB, insert markers.

```python
draft_md, meta = draft_single_post(...)

image_type = meta.get('image_type', 'none')
if image_type == 'chart':
    if not meta.get('chart_type') or not meta.get('chart_data'):
        logger.warning("image_type=chart but chart_type/chart_data missing. Fallback to photo.")
        image_type = 'photo'

# DB storage
db.update_post_image(post["id"], meta.get('image_keyword', ''))
if image_type == 'chart':
    db.update_chart(post["id"], meta['chart_type'], json.dumps(meta['chart_data'], ensure_ascii=False))
db.update_post_context(post["id"], meta.get('image_reason', ''))  # reuse context_md or add image_reason column

# Marker insertion (code-controlled)
if image_type == 'photo':
    draft_md = _insert_body_image_marker(draft_md)
elif image_type == 'chart':
    draft_md = _insert_chart_marker(draft_md)
# 'none' → no marker
```

Add `_insert_chart_marker(draft_md)`:
```python
def _insert_chart_marker(draft_md: str) -> str:
    """Insert <!--todo:chart--> before first ## heading."""
    h2_pattern = re.compile(r"^## ", re.MULTILINE)
    m = h2_pattern.search(draft_md)
    if m:
        pos = m.start()
        return draft_md[:pos].rstrip() + "\n\n<!--todo:chart-->\n\n" + draft_md[pos:]
    return draft_md
```

**Verification:** New chain with `--search --draft` → GPT returns `image_type=chart`, DB has `chart_type`, `chart_data` (Korean JSON).

---

### Task 8-4: image/injector.py — `<!--todo:chart-->` Marker Support

**File:** `image/injector.py`

`_find_image_file()` already searches `chart_{slug}.jpg` (confirmed). Add chart marker replacement branch:

```python
def inject_images_into_draft(draft_md, slug, blog_key, step, title):
    image_path = _find_image_file(slug)

    if not image_path:
        print(f"  [injector] ⚠️ slug '{slug}' 이미지 없음")
        return draft_md

    rel_path = _image_relative_path(image_path)
    figure = _hugo_figure(rel_path, alt=title, caption=title)

    # Phase 7: <!--todo:image--> replacement
    if "<!--todo:image-->" in draft_md:
        injected = draft_md.replace("<!--todo:image-->", figure)
        print(f"  [injector] ✅ 이미지 삽입: {rel_path}")
        return injected

    # Phase 8: <!--todo:chart--> replacement
    if "<!--todo:chart-->" in draft_md:
        injected = draft_md.replace("<!--todo:chart-->", figure)
        print(f"  [injector] ✅ 차트 삽입: {rel_path}")
        return injected

    # No marker → pass through
    print(f"  [injector] ⏭️ 마커 없음, 삽입 건너뜀")
    return draft_md
```

Signature unchanged: `inject_images_into_draft(draft_md, slug, blog_key, step, title)`.

**Verification:** Draft with `<!--todo:chart-->` + `chart_{slug}.jpg` exists → figure injected.

---

### Task 8-5: chain_publisher_core.py — Chart Generation Branch

**File:** `chain_publisher_core.py`, `_publish_hugo()` method

After thumbnail generation (Phase 7 code), add content_image branch:

```python
# Phase 8: content_image (chart or photo)
if not _post.get("content_image_path"):  # idempotency
    image_type = _post.get("image_type", "none")
    if image_type == "chart":
        try:
            from pillow_chart import render_chart
            chart_data = json.loads(_post.get("chart_data", "{}"))
            chart_type = _post.get("chart_type", "bar")
            font_path = _resolve_font_path()
            img_path, img_src = render_chart(
                chart_type=chart_type,
                chart_data=chart_data,
                title=title,
                slug=slug,
                font_path=font_path,
            )
            # Update DB
            _conn2 = get_conn()
            _conn2.execute(
                "UPDATE chain_posts SET content_image_path=?, content_image_source=? WHERE id=?",
                (str(img_path), img_src, _post_id),
            )
            _conn2.commit()
            _conn2.close()
            # Copy to assets for R2 upload
            shutil.copy2(img_path, assets_dir / Path(img_path).name)
        except FileNotFoundError as e:
            logger.error(f"Chart font missing: {e}. Fallback to photo.")
            # fallback to photo generation (Phase 7 logic)
        except Exception as e:
            logger.error(f"Chart generation failed: {e}. Fallback to photo.")
    elif image_type == "photo":
        # Phase 7 existing logic (already in place)
        pass
```

Add `_resolve_font_path()` helper:
```python
def _resolve_font_path() -> str:
    """Resolve Korean font path from config or system fallback."""
    cfg = load_config()
    chart_font = cfg.get("chart", {}).get("font", "")
    if chart_font and os.path.exists(chart_font):
        return chart_font
    fallbacks = [
        "assets/fonts/NotoSansKR-Regular.otf",
        "/System/Library/Fonts/PingFang.ttc",
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    ]
    for p in fallbacks:
        if os.path.exists(p):
            return p
    raise FileNotFoundError("No Korean font found for chart rendering")
```

R2 upload: `upload_all_images()` handles all files in `assets_dir/` regardless of name. `chart_*.jpg` uploads just like `thumb_*.jpg`.

**Verification:** Chain with `image_type=chart` → `chart_{slug}.jpg` created, uploaded to R2, figure in published page.

---

### Task 8-6: config/chain_config.yaml — Chart Section

**File:** `config/chain_config.yaml`

Add `chart:` block (after `thumbnail:` section):

```yaml
# === 차트 이미지 생성 (Phase 8) ===
chart:
  enabled: true
  output_dir: output/images
  filename_pattern: "chart_{slug}.jpg"
  font: assets/fonts/NotoSansKR-Regular.otf
  colors:
    primary: "#2563EB"
    secondary: "#DC2626"
    tertiary: "#16A34A"
  background: "#FFFFFF"
  text_color: "#1F2937"
  title_font_size: 42
  label_font_size: 28
  output_size: [1200, 630]
  jpeg_quality: 92
```

**Verification:** `yaml.safe_load(open('config/chain_config.yaml'))['chart']['font']` returns the path.

---

### Task 8-7: chain_publisher.py — Preflight Chart Font Check

**File:** `chain_publisher.py`, `_preflight_check()` function

Add chart font check after existing font check:

```python
# Chart font (Phase 8)
chart_font = load_config().get("chart", {}).get("font", "")
if chart_font and not os.path.exists(chart_font):
    system_fonts = [
        "/System/Library/Fonts/PingFang.ttc",
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    if not any(os.path.exists(p) for p in system_fonts):
        print("WARN: No Korean font for chart. image_type=chart will fallback to photo.")
```

**Verification:** `python chain_publisher.py --preflight` shows chart font status.

---

## Gap Analysis

| Gap | Resolution |
|---|---|
| 1: image_type=chart with no image_keyword | `image_keyword` NULL allowed (no NOT NULL constraint). Chart skips photo search. |
| 2: Korean JSON in chart_data | `json.dumps(..., ensure_ascii=False)`. SQLite TEXT handles UTF-8. |
| 3: Chart alt text | `f"{title} {chart_type} 차트"` in injector. Accessibility + SEO. |
| 4: Chart regeneration (photo→chart change) | Delete old `content_image_path` file before re-rendering. `update_content_image()` overwrites. |
| 5: Invalid chart_data from LLM | Validate: bar items 2-10, timeline events 2-8, comparison items 1-6. Invalid → `logger.warning()` + fallback to photo. |

## E2E Verification

```bash
# 1. DB migration
sqlite3 /Users/twinssn/Projects/5000/data/mc_chains.db \
  "ALTER TABLE chain_posts ADD COLUMN chart_type TEXT;
   ALTER TABLE chain_posts ADD COLUMN chart_data TEXT;
   ALTER TABLE chain_posts ADD COLUMN image_reason TEXT;"

# 2. Preflight
python chain_publisher.py --preflight

# 3. New chain with chart
python chain_publisher.py --seed "근로장려금 신청기간" --search --draft
# Expect: GPT returns image_type=chart, chart_type=timeline

# 4. Publish
python chain_publisher.py --chain-id <new> --image --publish

# 5. DB check
sqlite3 /Users/twinssn/Projects/5000/data/mc_chains.db \
  "SELECT slug, image_type, chart_type, content_image_path, content_image_source FROM chain_posts WHERE image_type='chart';"

# 6. Image check
ls -la output/images/chart_*.jpg

# 7. R2 check
curl -sI "https://img.aikorea24.kr/{slug}/chart_{slug}.jpg" | head -1  # 200

# 8. Live page
curl -s "https://rotcha.kr/{slug}/" | grep -o '<figure.*</figure>'

# 9. Idempotency
python chain_publisher.py --chain-id <new> --image --publish  # skip, no error
```

## Definition of Done

- `python chain_publisher.py --preflight` passes with chart font status
- New chain GPT returns `image_type=chart` with valid `chart_type`/`chart_data`
- DB has `chart_type`, `chart_data` (Korean JSON), `image_reason`
- `output/images/chart_{slug}.jpg` exists with Korean labels rendering correctly
- R2 has `chart_{slug}.jpg`, `curl -sI` returns 200
- Published body has `<figure>` with chart image
- Idempotent: re-run skips chart generation, no errors
- Font-missing environment: `image_type=chart` falls back to photo, no crash

## Constraints

- **New module:** `pillow_chart.py` only
- **No signature changes** to `inject_images_into_draft()`, `draft_chain()`, `_publish_hugo()`
- `image_type` existing values (`'photo'`, `'none'`) preserved; `'chart'` added
- `chart_data` stored with `ensure_ascii=False` for Korean
