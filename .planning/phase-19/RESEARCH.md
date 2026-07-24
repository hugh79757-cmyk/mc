# Phase 19 Research Report — Thumbnail Pipeline: Unsplash/Pexels + Pillow Text Overlay + R2 Integration

## 1. Current State Analysis

### 1.1 Existing Thumbnail Pipeline (`image/thumbnail.py`)

**Provider Chain (Current):**
1. **Unsplash** (Primary) - Real photos via API, requires `UNSPLASH_ACCESS_KEY`
2. **Pexels** (1st Fallback) - Real photos via API, requires `PEXELS_API_KEY`
3. **Pollinations** (2nd Fallback) - AI generated, **NO API KEY NEEDED**
4. **Krea** (3rd Fallback) - AI generated, requires API key

**Text Overlay (`add_text_overlay()` function, lines 238-339):**
- Uses Pillow (PIL) for all image manipulation
- Center-crop to 1:1 → resize to 1024×1024
- Dark gradient overlay at bottom for text readability
- Title + optional subtitle with text wrapping (CJK-aware)
- NotoSansKR font support with fallback
- Output: WEBP 85% quality, 1024×1024

**Provider Selection Logic (`generate_thumbnail()`, lines 344-439):**
- Idempotent: checks for existing `thumb_{slug}.webp` first
- `provider: auto` → tries Unsplash → fallback_chain
- Current `fallback_chain`: `["pexels", "pollinations", "krea"]`
- Returns `(Path, source_name)` tuple

### 1.2 Config (`config/chain_config.yaml`)

```yaml
thumbnail:
  provider: auto
  fallback_chain:
    - unsplash
    - pexels
    - pollinations    # ← Currently 3rd in chain
    - krea
  target_size: [1024, 1024]
  text_overlay:
    enabled: true
    font: assets/fonts/NotoSansKR-Regular.otf
    bg_alpha: 0.55

pollinations:
  enabled: true
  base_url: https://image.pollinations.ai/prompt/
  width: 1024
  height: 1024
  model: flux
  rate_limit_seconds: 15
```

### 1.3 API Keys Status

| Provider | Env Var | Status | Notes |
|----------|---------|--------|-------|
| Unsplash | `UNSPLASH_ACCESS_KEY` | ✅ Configured | Via `.env.common` → `image/search_providers.py` |
| Pexels | `PEXELS_API_KEY` | ✅ Configured | Via `.env.common` → `image/search_providers.py` |
| Pollinations | None needed | N/A | Free, rate-limited |
| Krea | `KREA_API_KEY` | ❓ Unknown | Requires paid tier |

**Evidence:** `image/search_providers.py` loads keys from `.env.common`:
```python
_UNSPLASH_KEY = os.environ.get("UNSPLASH_ACCESS_KEY", "")
_PEXELS_KEY = os.environ.get("PEXELS_API_KEY", "")
```

### 1.4 Existing Thumbnails on Disk

**`/Users/twinssn/projects2/mc/output/images/`** contains:
- `thumb_unsplash_*.webp` - Multiple files (real photos from Unsplash)
- `thumb_pexels_*.webp` - Multiple files (real photos from Pexels)
- `thumb_pollinations_*.webp` - None found
- AI-generated: `ai-트렌드-*.webp`, `ai프롬프트마켓-*.webp` (Pollinations content images)

**Conclusion:** Unsplash/Pexels thumbnails are **already working** and being produced. Pollinations fallback exists but may not have been triggered (Unsplash/Pexels success rate high).

---

## 2. Integration Points

### 2.1 Thumbnail Generation Call Sites

**Primary: `chain_publisher.py` → `generate_chain_images()` (lines 159-245)**
- Called during `--image` stage
- Loads `pollinations` config from `chain_config.yaml`
- Tries `image/` package first (local download), falls back to `generate_image_remote()` (Pollinations URL)
- Updates DB: `update_content_image()`, `update_post_image()`

**Key Flow:**
```python
# chain_publisher.py:163-166
try:
    from image import generate_image as img_gen
    from image import build_full_prompt as img_build
    from image import inject_images_into_draft as img_inject
    use_new_image = True
except ImportError:
    use_new_image = False  # Legacy Pollinations URL only

# Later (lines 204-217):
if use_new_image:
    full_prompt = img_build(...)
    image_result = img_gen(full_prompt, slug=_slug)  # Downloads via thumbnail.py chain
    if image_result and image_result.ok:
        image_path = image_result.value
        image_url = f"/images/{image_path.name}"
        db.update_content_image(post_id, str(image_path), "pollinations")
        db.update_post_image(post_id, image_url)
```

**Note:** Despite DB updates saying `"pollinations"`, the actual source is determined by `thumbnail.py` provider chain (Unsplash/Pexels/Pollinations/Krea).

### 2.2 Hugo Publishing (`publish_post()`, lines 249-278)

```python
thumbnail_url = image_url if image_url else None
result = _write_hugo_post(
    ...
    thumbnail_url=thumbnail_url if image_url else None,
)
```

- `thumbnail_url` passed to Hugo frontmatter
- Hugo theme (Blowfish) uses this for Open Graph / Twitter cards

### 2.3 R2 Upload (`image_handler.py`, `image/thumbnail.py`)

**R2 Upload Path:** `shared/image_handler.py` → `process_and_upload()`
- Used by `image/` package for local file → R2 upload
- Returns public R2 URL

**Current Gap:** Thumbnail generation saves to local `output/images/` but **R2 upload of thumbnails is not explicitly confirmed** in the pipeline. The `generate_image_remote()` in `chain_publisher.py` returns Pollinations URL directly, not R2 URL.

---

## 3. Requirements from User

### 3.1 Explicit Requirements
1. **Remove Pollinations from thumbnail fallback** - Only Unsplash → Pexels
2. **Keep Pillow text overlay** - Title on real photos (already works)
3. **R2 upload + link** - Thumbnail uploaded to R2, URL in Hugo frontmatter
4. **Integrate into current pipeline** - Connect to `--image` → `--publish` flow

### 3.2 Implicit Requirements
- Config change: `fallback_chain: ["unsplash", "pexels"]` (remove pollinations, krea)
- Ensure R2 upload of thumbnail happens in `--image` stage
- Thumbnail URL in Hugo frontmatter must be R2 public URL
- Maintain idempotency (existing `thumb_{slug}.webp` check)
- Keep API key loading from `.env.common`

---

## 4. Technical Approach

### 4.1 Config Changes (`config/chain_config.yaml`)

```yaml
thumbnail:
  provider: auto
  fallback_chain:
    - unsplash
    - pexels      # Only these two
  # pollinations removed
  # krea removed
  target_size: [1024, 1024]
  text_overlay:
    enabled: true
    font: assets/fonts/NotoSansKR-Regular.otf
    bg_alpha: 0.55
```

### 4.2 Code Changes

**File: `image/thumbnail.py`**
- Update `fallback_chain` default in `generate_thumbnail()` (line 384)
- No logic changes needed - provider chain is config-driven

**File: `config/chain_config.yaml`**
- Update `thumbnail.fallback_chain` as above

**File: `chain_publisher.py`**
- Verify R2 upload of thumbnail happens
- May need to add explicit thumbnail R2 upload after local generation
- Ensure `thumbnail_url` passed to Hugo is R2 public URL

**File: `image/thumbnail.py`**
- Verify `generate_thumbnail()` returns local path
- Ensure R2 upload integration point exists or add one

### 4.3 R2 Integration Design

**Option A: Extend `generate_chain_images()` to upload thumbnail to R2**
```python
# After img_gen() returns local path
if use_new_image and image_result.ok:
    image_path = image_result.value
    # Upload thumbnail to R2
    from image.r2_uploader import upload_thumbnail
    r2_url = upload_thumbnail(image_path, slug)
    db.update_post_image(post_id, r2_url)  # This becomes thumbnail_url
```

**Option B: Modify `image/thumbnail.py` to auto-upload to R2**
- Add optional `upload_to_r2=True` parameter
- Requires R2 credentials in env

**Recommendation:** Option A - explicit in pipeline, easier to debug.

---

## 5. Verification Criteria

| Check | Method | Pass Condition |
|-------|--------|----------------|
| Config updated | `grep -A5 "fallback_chain" config/chain_config.yaml` | Only unsplash, pexels |
| Pollinations removed | `grep -r "pollinations" image/thumbnail.py` | Only in comments/history |
| Thumbnail generation | `python -c "from image.thumbnail import generate_thumbnail; r=generate_thumbnail('Test','제주도'); print(r)"` | Returns (Path, 'unsplash'\|'pexels') |
| R2 upload | Check DB `image_meta.thumbnail_path` after `--image` | R2 URL present |
| Hugo frontmatter | Check published post frontmatter | `thumbnail: https://R2_URL` |
| Text overlay | Visual inspection of generated thumbnail | Title text on photo |
| Pipeline integration | `mc keyword --search --draft --image --publish` | End-to-end success |

---

## 6. Residual Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Unsplash/Pexels API rate limits | Medium | Thumbnail generation fails | Configurable retry/backoff; Pollinations as emergency manual fallback |
| API keys missing in deployment env | Low | Silent failure | Validate keys at startup; fail fast |
| R2 credentials missing | Low | Thumbnail not on CDN | Validate R2 env vars at startup |
| Font file missing (`NotoSansKR`) | Low | Text overlay fails | Bundle font in repo; fallback to default |
| Unsplash/Pexels both fail | Low | No thumbnail | Log warning; continue without thumbnail (graceful degradation) |
| Existing Pollinations thumbnails in DB | N/A | Legacy data | No migration needed; new posts use new chain |

---

## 7. Implementation Order

1. **Config**: Update `config/chain_config.yaml` `fallback_chain`
2. **Pipeline**: Ensure R2 upload of thumbnail in `generate_chain_images()`
3. **Verify**: Dry-run with `--search --draft --image` on test keyword
4. **Publish**: Full `--publish` on test keyword, verify live thumbnail
5. **Tests**: Update/add tests for new fallback chain