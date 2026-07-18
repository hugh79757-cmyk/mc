# PLAN — Phase 5: mde2 Architecture Publish Rewrite

**Phase:** 5  
**Status:** Verified ✓  
**Mode:** Standard  
**Dependencies:** Phase 1-4 complete (chain_deriver, chain_drafter, chain_publisher_core, chain_card_injector, chain_db, scheduler, loop)

---

## Goal

Rewrite `chain_publisher_core.py` from 5000 project patterns to mde2 project architecture. 7 core fixes transform the publish pipeline: R2-first images, Hugo local build + Wrangler deploy, theme-aware frontmatter, slug-based URLs, Blogger JSON tokens, 4-layer dedup, and card injection as a separate step.

---

## Files to Modify

| # | File | Action | Risk |
|---|------|--------|------|
| 1 | `.env` | Add R2 env vars (5 vars from mde2) | Low |
| 2 | `mc_paths.py` | Add `PATH_MDE2`, `ensure_mde2_on_path()` | Low |
| 3 | `config/chain_config.yaml` | Add theme, cf_pages_project, permalink_pattern, token_path per blog | Medium |
| 4 | `chain_db.py` | Add `publish_log` table + CRUD methods | Medium |
| 5 | `chain_publisher_core.py` | FULL REWRITE (mde2 pattern, 7 fixes) | **High** |
| 6 | `chain_card_injector.py` | Remove Hugo HTML injection path | Medium |
| 7 | `chain_publisher.py` | Add `--inject-card`, `--theme-override`, `--cf-pages-project` | Medium |
| 8 | `requirements.txt` | Add `python-frontmatter` | Low |

---

## Implementation Waves

### Wave 1: Infrastructure & Config (Tasks 1-4)

**Task 1.1 — R2 env vars**
- File: `.env`
- Copy 5 vars from mde2 `.env`:
  ```
  R2_ENDPOINT_URL=https://fac9808c757df31d797190c529aaa71a.r2.cloudflarestorage.com
  R2_ACCESS_KEY_ID=4e304a32cbf84b3e9999fff5fdcc85af
  R2_SECRET_ACCESS_KEY=7d23b84eea5d05e62186a9641878e2a167fc4678cceff7ea416b2f1d8f7043cf
  R2_BUCKET_NAME=md-editor
  R2_PUBLIC_URL=https://img.aikorea24.kr
  ```
- **Verification**: `grep -c R2_ .env` → 5

**Task 1.2 — mde2 path**
- File: `mc_paths.py`
- Add `PATH_MDE2 = "/Users/twinssn/Projects/mde2"`
- Add `ensure_mde2_on_path()` (same pattern as `ensure_5000_on_path()`)
- Call `ensure_mde2_on_path()` at module load
- **Verification**: `python -c "from mc_paths import PATH_MDE2; print(PATH_MDE2)"` succeeds

**Task 1.3 — Config update**
- File: `config/chain_config.yaml`
- Add per-site fields:
  - Hugo sites: `theme`, `cf_pages_project`, `permalink_pattern`
  - Blogger sites: `token_path`
- Techpawz: theme=Blowfish, cf_pages_project=techpawz, permalink="/:slug/"
- Rotcha: theme=PaperMod, cf_pages_project=rotcha-blog, permalink="/posts/:slug/"
- Informationhot: theme=PaperMod, cf_pages_project=informationhot-hugo, permalink="/posts/:slug/"
- 2_techpawz: token_path=config/blogger_token_2techpawz.json
- **Verification**: `python -c "import yaml; c=yaml.safe_load(open('config/chain_config.yaml')); assert c['sites']['techpawz']['theme'] == 'Blowfish'"`

**Task 1.4 — publish_log table**
- File: `chain_db.py`
- Add new table:
  ```sql
  CREATE TABLE IF NOT EXISTS publish_log (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      blog_id TEXT NOT NULL,
      slug TEXT NOT NULL,
      published_url TEXT,
      publish_method TEXT,
      published_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(blog_id, slug)
  );
  ```
- Add methods:
  - `log_publish(blog_id, slug, url, method)`
  - `check_duplicate(blog_id, slug) → bool`
  - `get_publish_log(chain_id) → list[dict]`
- Add migration for existing DBs
- **Verification**: `python -c "from chain_db import init_db; init_db(); print('OK')"`

### Wave 2: Core Pubisher Rewrite (Task 5) — HIGH RISK

**Task 2.1 — PublisherCore class skeleton**
- File: `chain_publisher_core.py` (full rewrite)
- Class with `publish_post()` entry point returning `(bool, str, str|None)`
- File lock mechanism (`_acquire_lock`/`_release_lock` using fcntl)
- `_detect_theme()` reads `hugo.toml` or `config/_default/hugo.toml` via `tomllib`
- **Verification**: `python -c "from chain_publisher_core import PublisherCore; pc=PublisherCore({}); print(type(pc))"`

**Task 2.2 — R2 image upload integration**
- Method: `_upload_images_to_r2(draft_md_path, slug) → (bool, str, dict)`
- Import from mde2: `from app.services.r2_uploader import upload_all_images, get_r2_config`
- Scan `output/images/{slug}/` for images
- Upload all to R2 with prefix `images/{slug}/`
- Return `url_map: {local_name: r2_url}`
- On failure: return `(False, error_msg, {})`
- **Verification**: mock test with a test image file

**Task 2.3 — Hugo publish (mde2 pattern)**
- Method: `_publish_hugo(blog_cfg, draft_md_path, slug, title, url_map) → (bool, str, str)`
- Steps:
  1. `_process_md()` — load frontmatter, set draft=false, date, slug, theme cover/featureimage
  2. Replace body image refs with R2 URLs from url_map
  3. Write to `hugo_root/content/posts/{slug}/index.md` (leaf bundle)
  4. `hugo --gc --minify` (cwd=hugo_root) — capture stderr on failure
  5. `wrangler pages deploy public --project-name {cf_pages_project}` (cwd=hugo_root)
  6. `_build_hugo_url()` — slug-based, theme-aware permalink
  7. `log_publish()` to DB
- On any failure: return `(False, error_msg, None)`
- **Verification**: deploy a test post to rotcha.kr → URL accessible

**Task 2.4 — process_md pipeline**
- Method: `_process_md(draft_md_path, slug, title, theme, url_map) → str`
- Load via `python-frontmatter` library
- Set: `draft: false`, `date: <now>`, `slug: <slug>`
- Theme branch:
  - PaperMod: `cover: {image: <r2_thumb_url>, alt: <title>}`
  - Blowfish: `featureimage: <r2_thumb_url>`
- Replace body `![alt](/images/slug/name)` → `![alt](<r2_url>)`
- Replace body `{{< figure src="/images/slug/name" >}}` → `![name](<r2_url>)`
- Strip any remaining `/images/` refs not in url_map
- **Verification**: output valid YAML frontmatter + Hugo-compatible body

**Task 2.5 — Blogger publish (mde2 pattern)**
- Method: `_publish_blogger(blog_cfg, draft_md_path, slug, title, labels, url_map) → (bool, str, str)`
- Steps:
  1. `check_duplicate(blog_id, slug)` → skip if exists
  2. Load draft_md, extract body
  3. `_replace_image_refs_for_blogger()` — replace `/images/` refs with R2 URLs
  4. Strip failed refs (not in url_map)
  5. `markdown.markdown(body, ["tables", "fenced_code"])`
  6. Prepend `<img src="{r2_thumb_url}" ...>` if thumbnail in url_map
  7. Initialize BloggerClient with JSON token path
  8. API dedup: `search_by_title(blog_id, title)` → skip if exists
  9. `client.publish_post(blog_id, title, html, labels)`
  10. `log_publish()` to DB
- **Verification**: publish to 2.techpawz.com → URL accessible

**Task 2.6 — Manual publish & URL builder**
- `_publish_manual()` — HTML to clipboard, prompt for URL
- `_build_hugo_url()` — `{base_url}/{permalink_pattern}` with slug
- `update_post_for_card()` — separate step entry for card injection
- **Verification**: manual mode saves HTML file and copies to clipboard

### Wave 3: Card Injection Separation & CLI (Tasks 6-7)

**Task 3.1 — Card injector refactor**
- File: `chain_card_injector.py`
- Remove `_inject_to_hugo_html()` method (previously injected into `public/posts/slug/index.html`)
- Keep `inject_cards()` for content string manipulation
- Add `inject_card_to_draft(draft_md_path, card_html) → str` that inserts into original draft markdown
- Card injector no longer calls git push or modifies Hugo build output directly
- **Verification**: `inject_card_to_draft()` returns modified markdown with card HTML

**Task 3.2 — CLI flags**
- File: `chain_publisher.py`
- Add `--inject-card` flag: separate step, calls `update_post_for_card()`
- Add `--theme-override THEME`: forces theme for Hugo publish
- Add `--cf-pages-project NAME`: overrides Cloudflare Pages project name
- Existing `--publish` flag now uses new PublisherCore (mde2 pattern)
- **Verification**: `python chain_publisher.py --help` shows new flags

**Task 3.3 — Requirements update**
- File: `requirements.txt`
- Add: `python-frontmatter>=4.0`
- Note: `tomllib` is built-in for Python 3.11+ (mc uses Python 3.x)
- Note: `boto3` may be needed if mde2's r2_uploader uses it (check mde2 requirements)
- **Verification**: `pip install -r requirements.txt` succeeds

---

## Verification Plan

### V1: R2 Upload
1. Create test image at `output/images/test-slug/test.webp`
2. Run `_upload_images_to_r2()` → url_map contains `{"test.webp": "https://img.aikorea24.kr/images/test-slug/test.webp"}`
3. Verify file exists in R2 bucket via `aws s3 ls`

### V2: Hugo Publish (PaperMod — rotcha.kr)
1. Run `chain_publisher.py --chain-id N --publish` (where chain N has rotcha as step 1)
2. Verify `hugo --gc --minify` succeeds (exit code 0)
3. Verify `wrangler pages deploy` succeeds
4. Verify URL `https://rotcha.kr/posts/{slug}/` returns 200
5. Verify frontmatter has `cover.image = https://img.aikorea24.kr/...`

### V3: Hugo Publish (Blowfish — techpawz.com)
1. Same as V2 but for techpawz
2. Verify URL `https://techpawz.com/{slug}/` (no `/posts/` prefix)
3. Verify frontmatter has `featureimage = https://img.aikorea24.kr/...`

### V4: Slug-Based URL
1. Verify URL does NOT contain date prefix (no `2026-07-18-` in path)
2. Compare with old pattern: old=`/posts/2026-07-18-slug/`, new=`/posts/slug/`

### V5: Blogger Publish (2.techpawz.com)
1. Run with `--blog-step2 2_techpawz`
2. Verify JSON token file created at `config/blogger_token_2techpawz.json`
3. Verify `markdown.markdown()` produces valid HTML with R2 image URLs
4. Verify `<img>` thumbnail appears before body
5. Verify published URL returns 200

### V6: 4-Layer Dedup
1. **Layer 1**: Run two `--publish` simultaneously with same slug → second gets fcntl lock error
2. **Layer 2**: Run `--publish` with already-published slug → `check_duplicate()` returns True → skip
3. **Layer 3** (Blogger only): Publish with same title as existing → `search_by_title()` returns True → skip
4. **Layer 4**: Simulate crash mid-publish → rerun → resume from last logged state

### V7: Card Injection (--inject-card)
1. Run `--inject-card --chain-id N`
2. Verify Hugo card: content/posts/{slug}/index.md contains card HTML
3. Verify `hugo --gc --minify` still succeeds after injection
4. Verify Blogger card: API `get_post` response contains card HTML

### V8: Error Handling
1. Disconnect network → run `--publish` → returns `(False, "Hugo 빌드 실패: ...")`
2. Remove `hugo` binary → run `--publish` → returns `(False, "Hugo 빌드 실패: ...")`
3. Invalid Blogger token → run `--publish` → returns `(False, "Blogger 에러: ...")`
4. No chain continues — single post failure doesn't abort multi-post publish loop

### V9: Loop Chain Compatibility (Phase 4)
1. Run loop chain with `--chain-type loop` → verify spoke posts + hub post all use new PublisherCore
2. Run `--inject-card` on loop chain → 2-CTAs injected via `update_post_for_card()`

---

## Removed Code (from old chain_publisher_core.py)

| Code | Reason | Replacement |
|------|--------|-------------|
| `_git_push()` | Hugo deploy via git push → Cloudflare Pages auto-build | `hugo --gc --minify` + `wrangler pages deploy` |
| `_save_image_static()` | Local static/images/ storage removed | R2 upload via `mde2.r2_uploader.upload_all_images()` |
| BS4 Hugo HTML parsing in card injection | Card injection removed from Hugo build path | `inject_card_to_draft()` operates on markdown source |
| `pickle` token storage | Pickle is opaque and fragile | JSON token file |
| `category="일반"` hardcode | Blowfish/PaperMod use different frontmatter keys | Dynamic from blog_cfg or hugo.toml auto-detect |
| `filename.replace(".md", "")` URL | Produces `/posts/2026-07-18-slug/` instead of `/posts/slug/` | `slug` parameter used directly |

---

## Dependencies

```
python-frontmatter>=4.0
boto3>=1.28  # if mde2's r2_uploader uses it
```

Python 3.11+ has `tomllib` built-in (no `tomli` dependency needed).

---

## Execution Order

```
Wave 1 (Infra):
  Task 1.1 ──▶ Task 1.2 ──▶ Task 1.3 ──▶ Task 1.4
                                        │
Wave 2 (Core):                          ▼
  Task 2.1 ──▶ Task 2.2 ──▶ Task 2.3 ──▶ Task 2.5
                  │           │              │
                  ▼           ▼              ▼
              Task 2.4 ──▶ (used by 2.3 & 2.5)
                              
              Task 2.6 (manual publish, can run in parallel)

Wave 3 (Card + CLI):
  Task 3.1 ──▶ Task 3.2 ──▶ Task 3.3
```

Tasks in Wave 2 can be partially parallelized:
- Task 2.2 (R2) and Task 2.6 (manual) are independent
- Task 2.4 (process_md) must complete before Task 2.3 (Hugo) and Task 2.5 (Blogger)
- Task 2.3 and 2.5 can be written in parallel (same class, different methods)

---

## Rollback Plan

If Phase 5 deploy fails:
1. `git checkout b9a6f53 -- chain_publisher_core.py chain_publisher.py chain_card_injector.py chain_db.py` restores Phase 4 state
2. `git checkout b9a6f53 -- config/chain_config.yaml` restores config
3. Remove added R2 env vars from `.env`
4. `pip uninstall python-frontmatter` to clean dependencies

Previous git push + Cloudflare Pages auto-build still works as fallback.
