# Phase 7: Search-Augmented Drafting — Image Pipeline Integration

**Goal:** Wire `image/thumbnail.py` into the chain publisher pipeline end-to-end. Close the 6 broken connections identified during Phase 7 implementation.

## Current State (as of this plan)

| File | Function | Gap |
|---|---|---|
| `image/thumbnail.py:328` | `generate_thumbnail(title, keyword, slug, subtitle)` | Works in isolation, returns `Path`. Uncalled from pipeline. |
| `image/injector.py:47` | `inject_images_into_draft(draft_md, slug, blog_key, step, title)` | `_find_image_file()` only searches `output/images/{slug}_*.jpg` — misses `thumb_*.jpg` |
| `chain_drafter.py:171` | `draft_chain()` | Saves draft_md + image_prompt/image_keyword to DB. No placeholder insertion. |
| `chain_publisher_core.py:153` | `_publish_hugo()` | Hardcodes `thumbnail.webp`/`cover.webp` for R2 frontmatter replace (lines 207–245). |
| `chain_db.py:58` | `chain_posts` schema | No `thumbnail_path`, `thumbnail_source`, `content_image_path`, `content_image_source` columns. |
| `config/chain_config.yaml:156` | `thumbnail:` block | Exists but `pollinations:` block (line 123) also active — no clear precedence. |

---

## Design Decisions (갭 결정사항)

### Gap 1: 썸네일 플레이스홀더 방식 — Option B

drafter는 `<!--todo:thumbnail-->` 마커를 넣지 않는다. 대신 frontmatter `featureimage:` 필드를 빈칸으로 둔다.

```yaml
---
title: "..."
date: "..."
slug: "..."
featureimage: ""  # ← 빈칸. publisher가 채움
---
```

publisher 동작: `_publish_hugo()`가 frontmatter 파싱 시 `featureimage` 값이 빈 문자열이면 `generate_thumbnail()` 호출 → 생성된 R2 URL로 `featureimage:` 채우기. 마커 파싱 로직 불필요.

**Task 7-4 수정:** drafter는 `<!--todo:thumbnail-->` 삽입 로직 제거. 대신 frontmatter에 `featureimage: ""` 빈 필드를 항상 포함하도록 GPT 프롬프트 수정. `<!--todo:image-->` 본문 마커는 유지.

### Gap 2: injector 자동 삽입 분기 제거

`inject_images_into_draft()`의 "첫 H2 전 자동 삽입" 분기 제거. 마커 교체만 수행.

**제거 대상:**
```python
# if no <!--todo:image--> marker found, auto-insert before first H2
```

**새 로직:**
```python
if '<!--todo:image-->' in draft_md:
    # figure로 교체
else:
    pass  # image_type=none인 경우, 정상
```

이유: drafter가 삽입 여부를 결정하므로, injector가 다시 자동 삽입하면 이중 삽입 리스크.

**Task 7-3 수정:** `_find_image_file()` 멀티패스 검색 확장은 유지, 자동 삽입 분기 제거.

### Gap 3: chain_id 9 멱등성 보장

재발행 시 기존 데이터/파일을 안전하게 덮어쓰도록 3곳 처리:

- **DB**: `thumbnail_path`/`content_image_path`가 이미 채워져 있으면 재생성 스킵
- **Hugo content**: `open(..., 'w')`로 무조건 덮어쓰기 (기존 파일 존재 체크 로직 제거)
- **R2**: `put_object()`는 동일 key 덮어쓰기가 기본 → 추가 처리 불필요. 업로드 전 파일 없으면 스킵(로그만)

**Task 7-5 수정:** `_publish_hugo()`에 3가지 멱등성 조건 반영.

### Gap 4: image_url 컬럼 — 사용 중단 주석만

`image_url` 컬럼은 신규 로직에서 건드리지 않음. 스키마 정의에 deprecated 주석만 추가. 기존 데이터 보존, 이동/복사 없음.

### Gap 5: 사전 확인 3종 — E2E 실행 전 필수 체크

`--publish` 시 자동 실행되는 `_preflight_check()`:

| 항목 | 역할 | 레벨 | 이유 |
|---|---|---|---|
| `UNSPLASH_ACCESS_KEY` | Primary provider | ERROR (중단) | 없으면 썸네일 생성 불가 |
| `PEXELS_API_KEY` | Fallback 1 | WARN (계속) | Unsplash 실패 시에만 필요 |
| Pollinations | Fallback 2 | 체크 제외 | 키 불필요, 무료 엔드포인트 |
| 한글 폰트 | PIL 오버레이 | WARN (계속) | 없으면 텍스트 없는 이미지 반환 |
| `output/images/` | 출력 디렉토리 | 자동 생성 | 없으면 `os.makedirs()` |

---

## Plan

### Task 7-1: DB Schema Migration

**File:** `chain_db.py`

Add 4 columns to `chain_posts`:
```sql
ALTER TABLE chain_posts ADD COLUMN thumbnail_path TEXT;
ALTER TABLE chain_posts ADD COLUMN thumbnail_source TEXT;  -- 'unsplash'|'pexels'|'pollinations'
ALTER TABLE chain_posts ADD COLUMN content_image_path TEXT;
ALTER TABLE chain_posts ADD COLUMN content_image_source TEXT;
```

Mark `image_url` as deprecated in schema comment:
```sql
image_url TEXT,  -- DEPRECATED: Phase 7 이전 Pollinations URL 저장용. 신규 로직은 thumbnail_path 사용.
```

Add helper methods: `update_thumbnail(post_id, path, source)` and `update_content_image(post_id, path, source)`. Existing method signatures unchanged.

**Idempotency (Gap 3):** In `_publish_hugo()` flow, before calling `generate_thumbnail()`: check if DB `thumbnail_path` is already non-NULL → skip generation.

**Verification:**
```bash
sqlite3 data/mc_chains.db "PRAGMA table_info(chain_posts)" | grep -E "thumbnail_path|thumbnail_source|content_image"
# 4 new columns visible
```

---

### Task 7-2: thumbnail.py — Return Tuple, Unified Output Path

**File:** `image/thumbnail.py`

1. Change return type of `generate_thumbnail()` from `Optional[Path]` to `Optional[tuple[Path, str]]` returning `(path, source_name)`.
2. Output path: **`output/images/thumb_{safe_slug}.jpg`** (unify with injector/hugo search path).
3. Backwards-compat: callers use `path, _ = generate_thumbnail(...)`.
4. `generate_thumbnail()` must not overwrite existing file unless forced (idempotency: check if file exists at target path → return existing path + source).

**Verification:**
```bash
python3 -c "from image import generate_thumbnail; r = generate_thumbnail('Test', '서울', slug='t1'); print(r)"
# Expected: (PosixPath('output/images/thumb_t1.jpg'), 'unsplash'|'pexels'|'pollinations')
```

---

### Task 7-3: injector.py — Multi-Path Discovery, No Auto-Insert

**File:** `image/injector.py`

**Modify `_find_image_file(slug)`** to search in order:
1. `output/images/thumb_{slug}.jpg` ← thumbnail.py (Phase 7)
2. `output/images/thumb_{slug}.jpg` ← pollinations_client legacy
3. `output/images/{slug}_*.jpg` ← pollinations_client
4. `output/images/chart_{slug}.jpg` ← pillow_chart.py (Phase 8)

**Remove auto-insert fallback (Gap 2):** Delete the block that inserts a figure before the first H2 when no `<!--todo:image-->` marker is found. Only marker replacement. If marker absent, return draft unchanged.

Signature unchanged: `inject_images_into_draft(draft_md, slug, blog_key, step, title)`.

**Verification:**
```bash
python3 -c "
from image.injector import inject_images_into_draft
md = open('output/drafts/9/step-1-xxx.md').read()
out = inject_images_into_draft(md, 'xxx', 'rotcha', 1, 'Test')
assert '{{< figure' in out
print('injector OK')
"
```

---

### Task 7-4: chain_drafter.py — Empty featureimage Field + Body Marker

**File:** `chain_drafter.py`, function `draft_chain()` (line 171)

**Remove:** `<!--todo:thumbnail-->` insertion logic (Gap 1).

**Add:** After `draft_md = draft_single_post(...)`, ensure frontmatter has `featureimage: ""` (empty string, not omitted). If GPT output already includes `featureimage: ""` → no change needed. If missing → append before closing `---`.

**Keep:** Insert `<!--todo:image-->` before the first `## ` heading in the body.

**GPT Prompt change:** Add instruction to `prompts.yaml` `draft_user` template:
```
featureimage: ""  # 빈칸으로 둘 것. publisher가 썸네일 생성 후 채움.
```

Store `image_type='photo'` in DB (default, drafter doesn't set it).

**Verification:** Inspect draft MD — `featureimage: ""` in frontmatter, `<!--todo:image-->` before first H2.

---

### Task 7-5: chain_publisher_core.py — DB Lookup, No Hardcoding, Idempotency

**File:** `chain_publisher_core.py`, `_publish_hugo()` method

**Replace** hardcoded `thumbnail.webp`/`cover.webp`/`thumbnail.png` logic (lines 207–245):

```python
# 1. Load post from DB: thumbnail_path, thumbnail_source, image_keyword
# 2. thumbnail_path is NULL → call generate_thumbnail(title, keyword, slug)
#    → update DB with (path, source)
# 3. Build absolute path from thumbnail_path
# 4. upload_all_images(temp_dir, slug, r2_prefix, r2_domain)
#    → all files under temp_dir/assets/ are included automatically
# 5. frontmatter replace: use R2 URL returned from upload_all_images
#    for featureimage/cover.image — NO hardcoded filename
```

**Idempotency (Gap 3):**
- DB: if `thumbnail_path` already set → log "thumbnail already set, skipping", do not call `generate_thumbnail()`
- Hugo file: use `open(path, 'w')` → always overwrite (remove `if target_dir.exists(): shutil.rmtree()` guard for the file itself)
- R2: `upload_all_images()` overwrites existing objects by key — no extra handling needed

**Signature preserved:** `_publish_hugo(self, blog_cfg, draft_md, slug, title, labels=None)` — same.

**Verification:**
```bash
python chain_publisher.py --chain-id 9 --publish --dry-run
# Log: "[Hugo] cover.image → R2 URL: https://img.aikorea24.kr/..."
```

---

### Task 7-6: config/chain_config.yaml — Precedence Clarification

**File:** `config/chain_config.yaml`

Reorder so `thumbnail:` block comes first, add deprecation comment to `pollinations:` block:

```yaml
# thumbnail: primary image config (Phase 7)
thumbnail:
  provider: auto
  fallback_chain: [unsplash, pexels, pollinations, pillow_chart]
  target_size: [1024, 1024]

# pollinations: DEPRECATED — only used as fallback inside thumbnail.py
# 독립 호출 금지 (chain_publisher --image 직접 Pollinations 경로 제거)
pollinations:
  enabled: true
  width: 1024
  height: 1024
```

**Verification:** `python3 -c "from mc_paths import load_config; print(load_config()['thumbnail']['provider'])"` → `auto`.

---

### Task 7-7: Preflight Check + End-to-End Verification

**File:** `chain_publisher.py` — add `_preflight_check()` function + `--preflight` flag (also auto-runs before `--publish`).

**Preflight logic:**
```python
def _preflight_check() -> bool:
    # 1. Unsplash (Primary) — ERROR
    if not os.environ.get('UNSPLASH_ACCESS_KEY'):
        print("ERROR: UNSPLASH_ACCESS_KEY not set in .env")
        print("발급: https://unsplash.com/developers")
        return False

    # 2. Pexels (Fallback 1) — WARN
    if not os.environ.get('PEXELS_API_KEY'):
        print("WARN: PEXELS_API_KEY not set. Fallback: Unsplash→Pollinations.")
        print("발급(선택): https://www.pexels.com/api/")

    # 3. Pollinations (Fallback 2) — 키 불필요, 체크 제외

    # 4. 한글 폰트 — WARN
    font_candidates = [
        "assets/fonts/NotoSansKR-Regular.otf",
        "/System/Library/Fonts/PingFang.ttc",
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    if not any(os.path.exists(p) for p in font_candidates):
        print("WARN: No Korean font. PIL overlay renders as squares.")
        print("설치: https://fonts.google.com/noto/specimen/Noto+Sans+KR")

    # 5. output/images/ — 자동 생성
    Path("output/images").mkdir(parents=True, exist_ok=True)
    return True
```

**E2E verification sequence:**
```bash
# 1. Preflight
python chain_publisher.py --preflight

# 2. DB 마이그레이션 (one-time)
sqlite3 data/mc_chains.db "ALTER TABLE chain_posts ADD COLUMN thumbnail_path TEXT;"
sqlite3 data/mc_chains.db "ALTER TABLE chain_posts ADD COLUMN thumbnail_source TEXT;"
sqlite3 data/mc_chains.db "ALTER TABLE chain_posts ADD COLUMN content_image_path TEXT;"
sqlite3 data/mc_chains.db "ALTER TABLE chain_posts ADD COLUMN content_image_source TEXT;"

# 3. Draft (verify placeholders)
python chain_publisher.py --chain-id 9 --draft

# 4. Full publish
python chain_publisher.py --chain-id 9 --image --publish

# 5. DB 검증
sqlite3 data/mc_chains.db \
  "SELECT slug, thumbnail_path, thumbnail_source FROM chain_posts WHERE chain_id=9;"

# 6. R2 검증
curl -sI "https://img.aikorea24.kr/images/{slug}/thumb_{slug}.jpg" | head -1  # 200

# 7. 라이브 URL 검증
curl -sI "https://rotcha.kr/posts/{slug}/" | head -1  # 200

# 8. 멱등성 검증 (Gap 3)
python chain_publisher.py --chain-id 9 --image --publish
# 기대: "thumbnail already set, skipping" + 에러 없음
```

---

## Definition of Done

- `--preflight` → passes with UNSPLASH_ACCESS_KEY present; PEXELS_API_KEY missing gives WARN but continues
- `--chain-id 9 --draft` → `featureimage: ""` in frontmatter, `<!--todo:image-->` before first H2
- `--chain-id 9 --image --publish` → succeeds without errors
- DB: `thumbnail_path` = `output/images/thumb_{slug}.jpg`, `thumbnail_source` = `'unsplash'|'pexels'|'pollinations'`
- R2: `thumb_{slug}.jpg` uploaded, `curl -sI` returns 200
- Published frontmatter: `featureimage: https://img.aikorea24.kr/.../thumb_{slug}.jpg`
- Published body: `<figure>` before first H2 (or no insertion if image_type=none)
- Re-run `--publish` on same chain_id → no regeneration, no errors (idempotent)
- `image_url` column untouched, no writes to it from new code

---

## Constraints

- **No new modules** except `image/pillow_chart.py` (Phase 8, image_type=chart).
- **No signature changes** to `generate_thumbnail()`, `inject_images_into_draft()`, `_publish_hugo()`. Internal return type of `generate_thumbnail()` expands to `tuple[Path, str]` but callers just destructure.
- `image_url` column: do not delete, do not write to it. Deprecated comment only.
- Existing `static/images/thumb_*.jpg` test files remain as-is (not canonical path going forward; output/images/ is canonical).
