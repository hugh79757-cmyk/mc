# Phase 9: KREA AI Fallback

**Goal:** KREA AI as 4th image provider in thumbnail.py fallback chain. When Unsplash → Pexels → Pollinations all fail, KREA generates the thumbnail.

**Prerequisite:** Phase 7 complete (thumbnail pipeline operational). Phase 8 chart generation complete.

**Scope (locked):** Image fallback only. No provider abstraction, no WebP, no chart fallback.

**Reference:**
- `RESEARCH.md` — KREA API research, async job pattern, config schema
- `CONTEXT.md` — scope summary and key constraints

---

## Architecture

```
generate_thumbnail(title, keyword, slug)
  ├── 1. Unsplash.search() → download → add_text_overlay() → return (path, "unsplash")
  ├── 2. Pexels.search() → download → add_text_overlay() → return (path, "pexels")
  ├── 3. Pollinations (GET image.pollinations.ai) → add_text_overlay() → return (path, "pollinations")
  └── 4. KREA (POST /generate/image/krea/krea-2/medium → poll GET /jobs/{id} → download)           → add_text_overlay() → return (path, "krea")
```

No structural changes. `generate_thumbnail()` loop already dispatches by `fallback_name`. Just need to replace the `_krea_fallback()` stub.

---

## Wave 1: KREA Client + Wiring (2 files)

### Task 9-1: `image/krea_client.py` — New async job client

**Responsibility:** Create generation job → poll → download image. Parallels `pollinations_client.py` but uses async job pattern instead of synchronous GET.

**Signature:** `generate_image(prompt, slug="post", aspect_ratio="1:1", resolution="1K") -> Path | None`

**Flow:**
1. Load `KREA_API_KEY` from env
2. `POST https://api.krea.ai/generate/image/krea/krea-2/medium` with prompt, aspect_ratio="1:1", resolution="1K"
3. Extract `job_id` from response
4. Poll `GET https://api.krea.ai/jobs/{job_id}` every 2s, max 90s timeout (45 polls)
5. On `completed`: extract `result.urls[0]`, download to `output/images/krea_{slug}.jpg`
6. Return `Path | None`

**Status field handling:**
- `completed` → download and return
- `failed` / `cancelled` → return None immediately
- `queued` / `processing` → continue polling
- HTTP error / timeout → return None

### Task 9-2: `image/thumbnail.py` — Replace `_krea_fallback()` stub

**File:** `image/thumbnail.py:187-190`

**Current (stub):**
```python
def _krea_fallback(prompt: str, slug: str) -> Optional[Path]:
    print(" [thumbnail] Krea fallback not implemented, returning None")
    return None
```

**Change:**
```python
def _krea_fallback(prompt: str, slug: str) -> Optional[Path]:
    try:
        from image.krea_client import generate_image
        return generate_image(prompt, slug=slug)
    except Exception as e:
        print(f" [thumbnail] Krea fallback error: {e}")
        return None
```

No other changes to thumbnail.py. The dispatch loop at line 420-427 already handles the result.

---

## Wave 2: Config + Env (2 files)

### Task 9-3: `config/chain_config.yaml` — Add `krea:` section

**Location:** After `pollinations:` section (around line 128).

**Add:**
```yaml
krea:
  enabled: true
  api_base: https://api.krea.ai
  model: krea/krea-2/medium
  aspect_ratio: "1:1"
  resolution: "1K"
  creativity: medium
  poll_interval_seconds: 2
  poll_timeout_seconds: 90
```

**Note:** `thumbnail.fallback_chain` already includes `"krea"` (line 375). When Pollinations fails, loop dispatches to `_krea_fallback()`.

### Task 9-4: `.env.example` — Document API key

**Add at end:**
```bash
# KREA AI (Phase 9 fallback)
# Get token at https://www.krea.ai/settings/api-tokens
KREA_API_KEY=your-token-here
```

User's actual `.env` (`.env.common`) must have `KREA_API_KEY=...` added manually.

---

## Wave 3: Verification (1 file: manual)

### Task 9-5: E2E smoke test

1. Ensure `.env.common` has `KREA_API_KEY=...` (user provides)
2. Force Pollinations failure (e.g., set `pollinations.enabled: false` in config)
3. Run: `python -c "from image.thumbnail import generate_thumbnail; print(generate_thumbnail('test', 'test', 'test-9'))"`
4. Expect: image saved to `output/images/krea_test-9.jpg`, source=`krea`, `add_text_overlay()` produces `thumb_test-9.jpg`
5. Restore config

**Verification criteria:**
| # | Criterion | Check |
|---|-----------|-------|
| V1 | KREA stub replaced | `_krea_fallback()` calls `generate_image()` — no "not implemented" print |
| V2 | Async job creates, polls, downloads | 2-3 HTTP calls per thumbnail, final file in `output/images/krea_*.jpg` |
| V3 | Text overlay works | `thumb_*.jpg` exists after `add_text_overlay()` |
| V4 | Config loadable | `config/chain_config.yaml` + new `krea:` section parseable |
| V5 | Env var loads | `KREA_API_KEY` from `.env.common` or system env |
| V6 | Graceful failure | Missing API key → None, no crash |
| V7 | Pipeline end-to-end | `python chain_publisher.py --chain-id 9 --image --publish` → thumbnail uses Pollinations normally (no change needed for happy path) |

---

## File Summary

| File | Action | Lines (est.) |
|------|--------|-------------|
| `image/krea_client.py` | **NEW** | ~80 |
| `image/thumbnail.py` | MODIFY (stub replacement) | ~5 |
| `config/chain_config.yaml` | ADD section | ~10 |
| `.env.example` | ADD line | 1 |

**Total:** ~100 lines of new code.
