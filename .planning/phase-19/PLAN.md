# Phase 19 Plan — Thumbnail Pipeline: Unsplash/Pexels + Pillow Overlay + R2 Integration

## Phase Objective
Replace Pollinations fallback in thumbnail generation with Unsplash/Pexels only, ensure Pillow text overlay on real photos, upload thumbnails to R2, and integrate into `--image → --publish` pipeline.

---

## Hard Constraints
- **No new external dependencies** — Use existing Pillow, requests, boto3
- **API keys via `.env.common`** — UNSPLASH_ACCESS_KEY, PEXELS_API_KEY already loaded
- **R2 credentials via env** — R2_ENDPOINT, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET
- **Idempotency preserved** — Existing `thumb_{slug}.webp` check must work
- **Config-driven provider chain** — No hardcoded provider order in code

---

## Task Breakdown

### T1: Config Update — Remove Pollinations/Krea from Fallback Chain
**File:** `config/chain_config.yaml`

| Change | Before | After |
|--------|--------|-------|
| `thumbnail.fallback_chain` | `["unsplash", "pexels", "pollinations", "krea"]` | `["unsplash", "pexels"]` |
| `pollinations.enabled` | `true` | `false` (or remove section) |
| `krea.enabled` | `true` | `false` (or remove section) |

**Verification:**
```bash
grep -A5 "fallback_chain:" config/chain_config.yaml
# Should show only unsplash, pexels
```

---

### T2: Ensure R2 Upload of Thumbnail in Pipeline
**File:** `chain_publisher.py` → `generate_chain_images()`

**Current Flow:**
1. `img_gen()` downloads thumbnail via `image/` package → local file
2. `db.update_content_image(post_id, path, "pollinations")` — records local path
3. `db.update_post_image(post_id, "/images/{filename}")` — sets local-relative URL

**Required Addition:**
After successful local thumbnail generation, upload to R2 and update URL to R2 public URL.

**Implementation:**
```python
# In generate_chain_images(), after line ~220 (after img_gen succeeds)
if use_new_image and image_result and image_result.ok:
    image_path = image_result.value  # local Path
    
    # NEW: Upload thumbnail to R2
    from shared.image_handler import get_r2_client
    import os
    
    r2_client = get_r2_client()
    bucket = os.getenv("R2_BUCKET", "hotissue-images")
    key = f"thumbnails/{image_path.name}"
    
    with open(image_path, "rb") as f:
        r2_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=f.read(),
            ContentType="image/webp"
        )
    
    r2_url = f"{os.getenv('R2_PUBLIC_URL')}/{key}"
    
    # Update DB with R2 URL (replaces local-relative URL)
    db.update_post_image(post_id, r2_url)
    # Also update image_meta with R2 info
    meta = json.loads(post.get("image_meta", "{}"))
    meta["thumbnail_r2_url"] = r2_url
    meta["thumbnail_source"] = source  # "unsplash" | "pexels"
    db.update_post_image_meta(post_id, json.dumps(meta))
```

**Dependencies:**
- `shared.image_handler.get_r2_client()` exists and works
- R2 env vars: `R2_ENDPOINT`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`, `R2_PUBLIC_URL`

---

### T3: Verify Thumbnail Generation (Config + Code)
**Files:** `image/thumbnail.py` (verify config-driven), `config/chain_config.yaml`

**Verification Steps:**
1. Confirm `fallback_chain` default in `generate_thumbnail()` reads from config
2. Confirm Pollinations/Krea imports removed from fallback logic (they're in `_pollinations_fallback()` and `_krea_fallback()` but only called if in `fallback_chain`)
3. No code changes needed in `thumbnail.py` — it's already config-driven

**Verification:**
```bash
python3 -c "
from image.thumbnail import generate_thumbnail
from mc_paths import load_config
config = load_config()
print('fallback_chain:', config.get('thumbnail', {}).get('fallback_chain'))
r = generate_thumbnail('Test Title', '제주도 해수욕장', slug='test-thumb')
print('Result:', r)
"
# Should return (Path, 'unsplash' or 'pexels')
```

---

### T4: End-to-End Dry-Run (Search + Draft + Image)
**Command:**
```bash
python3 chain_publisher.py --seed "해운대 해수욕장" --search --draft --image
```

**Success Criteria:**
- Chain derived (travel → lateral)
- 3 posts drafted
- Search context injected
- 3 thumbnails generated (Unsplash/Pexels)
- Local files in `output/images/thumb_*.webp`
- DB `image_meta.thumbnail_r2_url` populated with R2 URLs
- No Pollinations calls (check logs)

---

### T5: Full Publish Test
**Command:**
```bash
python3 chain_publisher.py --seed "해운대 해수욕장" --search --draft --image --publish
```

**Success Criteria:**
- 3 posts published to 3 sites (rotcha.kr, issue.techpawz.com, techpawz.com)
- Live pages have thumbnail in HTML frontmatter/Open Graph
- Thumbnail URL is R2 public URL (`https://R2_DOMAIN/thumbnails/...`)
- Thumbnail displays title text overlay (visual check)
- CTA card ("더 알아보기 →") renders correctly (Phase 17 CTA changes)

---

### T6: Update Tests
**Files:**
- `test_image_pipeline.py` — Update fallback chain assertions
- `conftest.py` — Update `sample_prompts` thumbnail config

**Specific Changes:**
```python
# test_image_pipeline.py
# test_generate_thumbnail_fallback_to_pollinations → REMOVE or rename
# Add test_generate_thumbnail_unsplash_then_pexels

# conftest.py sample_prompts["thumbnail"]["fallback_chain"] = ["unsplash", "pexels"]
```

---

### T7: Pytest Full Suite
```bash
python3 -m pytest /Users/twinssn/projects2/mc -x -v
# Target: 246/246 passed
```

---

## Dependencies & Prerequisites

| Dependency | Status | Notes |
|------------|--------|-------|
| `UNSPLASH_ACCESS_KEY` in `.env.common` | ✅ Verified | Loaded by `search_providers.py` |
| `PEXELS_API_KEY` in `.env.common` | ✅ Verified | Loaded by `search_providers.py` |
| `R2_ENDPOINT`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`, `R2_PUBLIC_URL` | ❓ Verify | Must be set in deployment env |
| `NotoSansKR-Regular.otf` at `assets/fonts/` | ✅ Exists | Used by `add_text_overlay()` |
| `shared.image_handler.get_r2_client()` | ✅ Exists | Returns boto3 S3 client for R2 |

---

## Verification Protocol

### Automated (pytest)
- All 246 tests pass
- New thumbnail tests cover unsplash→pexels chain

### Manual Verification Checklist
| Step | Command / Action | Expected |
|------|------------------|----------|
| 1. Config | `grep -A3 "fallback_chain" config/chain_config.yaml` | Only unsplash, pexels |
| 2. Dry-run | `mc "해운대 해수욕장" --search --draft --image` | 3 thumbs, R2 URLs in DB |
| 3. Publish | `mc "해운대 해수욕장" --search --draft --image --publish` | 3 live posts with R2 thumbnails |
| 4. Visual | Open live URLs in browser | Thumbnail shows photo + title text |
| 5. CTA | Check live post | Red "더 알아보기 →" card at bottom |

---

## Rollback Plan
If issues arise:
1. Revert `config/chain_config.yaml` `fallback_chain` to include `pollinations`
2. Revert `chain_publisher.py` R2 upload addition
3. Re-run tests → confirm 246 pass

---

## Timeline Estimate

| Task | Estimate |
|------|----------|
| T1: Config update | 5 min |
| T2: R2 upload in pipeline | 30 min |
| T3: Verification | 15 min |
| T4: Dry-run test | 10 min |
| T5: Full publish test | 15 min |
| T6: Test updates | 20 min |
| T7: Full pytest | 5 min |
| **Total** | **~1.5 hours** |

---

## Success Criteria (Definition of Done)
- [ ] `config/chain_config.yaml` `fallback_chain` = `["unsplash", "pexels"]`
- [ ] Pollinations/Krea removed from thumbnail fallback
- [ ] Thumbnail generation uses Unsplash → Pexels only
- [ ] Pillow text overlay works on real photos
- [ ] Thumbnails uploaded to R2 during `--image` stage
- [ ] R2 public URL in Hugo frontmatter `thumbnail` field
- [ ] Live posts show thumbnail with title overlay
- [ ] All 246 tests pass
- [ ] No regression in existing functionality