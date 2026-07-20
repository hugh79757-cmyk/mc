# Phase 9 Research: KREA AI Fallback

**Researched:** 2026-07-19 (inline, no subagent)
**Scope:** Image fallback only — KREA as 4th provider in thumbnail.py chain.

---

## 1. KREA API Reference

### Endpoint & Auth

- **Base URL:** `https://api.krea.ai`
- **Auth:** Bearer token — `Authorization: Bearer YOUR_API_TOKEN`
- **Token generation:** https://www.krea.ai/settings/api-tokens
- **Billing docs:** /developers/api-keys-and-billing (pay-per-use, no free tier confirmed)

### Async Job Pattern (critical)

KREA is **asynchronous**, unlike Pollinations (which returns image bytes directly in one GET).

**Step 1 — Create job:**
```
POST /generate/image/{provider}/{model}
Authorization: Bearer {token}
Content-Type: application/json

{"prompt": "...", "aspect_ratio": "1:1", "resolution": "1K"}
```
Returns immediately: `{"job_id": "...", "status": "queued"}`

**Step 2 — Poll for completion:**
```
GET /jobs/{job_id}
Authorization: Bearer {token}
```
Poll every 2 seconds until `status == "completed"`. Then `result.urls[0]` is the image URL.

**Step 3 — Download image** from `result.urls[0]` (separate HTTP GET).

### Available Image Models

| Model | Endpoint | Price | Est. Time | Notes |
|-------|----------|-------|-----------|-------|
| Krea 2 (medium) | `/generate/image/krea/krea-2/medium` | $0.030 | ~10s | Flagship, creativity control |
| Nano Banana Pro | `/generate/image/google/nano-banana-pro` | $0.15 | ~24s | Best typography |
| Seedream 4 | `/generate/image/bytedance/seedream-4` | $0.0315 | ~20s | Photorealism |
| GPT Image 2 | `/generate/image/openai/gpt-image-2` | $0.009 | ~55s | Cheapest |
| Flux 1 Dev | `/generate/image/bfl/flux-1-dev` | (check) | ~? | Same as Pollinations Flux |

**Recommendation:** Use **Krea 2 medium** ($0.03, ~10s) — cheapest Krea-native, fast, good quality. Fallback doesn't need to be the best, just reliable.

### Request Parameters (Krea 2)

```json
{
  "prompt": "English prompt here",
  "aspect_ratio": "1:1",  // "1:1" | "4:5" | "16:9" | etc.
  "resolution": "1K",     // "1K" | "2K" | "4K"
  "creativity": "medium"  // "low" | "medium" | "high"
}
```

For blog thumbnails (1024×1024), use `aspect_ratio: "1:1"`, `resolution: "1K"`.

### Pricing

- Pay-per-use, no free tier confirmed
- Krea 2 medium: $0.03/image
- 3 images per chain (1 per post) = $0.09/chain worst case (only when Unsplash + Pexels + Pollinations all fail)
- In practice, fallback rarely triggers — Unsplash/Pexels succeed 90%+ for real-photo keywords

---

## 2. Current Pollinations Integration

### How thumbnail.py works now

`image/thumbnail.py:339` — `generate_thumbnail(title, keyword, slug, subtitle)` → `tuple[Path, str] | None`

**Provider chain (already implemented):**
1. Unsplash (real photo) — `UnsplashProvider` class
2. Pexels (real photo, 1st fallback) — `PexelsProvider` class
3. Pollinations (AI, 2nd fallback) — `_pollinations_fallback()` function
4. Krea (AI, 3rd fallback) — `_krea_fallback()` **STUB** (line 187, returns None)

The fallback chain is **already wired** — `config/chain_config.yaml` has `fallback_chain: [pexels, pollinations, krea]` and the loop at line 395-427 already dispatches to each provider by name.

### Failure modes that trigger fallback

- Unsplash/Pexels: empty search results, API key missing, HTTP error, download timeout
- Pollinations: HTTP error, timeout (120s), tiny response (<1000 bytes = likely error page), URL error

### Current Pollinations client (`image/pollinations_client.py`)

- Synchronous single GET request
- 3 retries with 5-10s backoff
- Returns `Path | None`
- Saves to `output/images/{slug}_{width}x{height}.jpg`

### Gap

`_krea_fallback()` at line 187-190 is a stub that prints "not implemented" and returns None. **This is the only thing to implement.** No other file needs structural changes.

---

## 3. Fallback Design

### What to build

New file: `image/krea_client.py` — mirrors `pollinations_client.py` pattern but with KREA's async job flow.

```python
# image/krea_client.py
def generate_image(prompt: str, slug: str = "post", 
                   aspect_ratio: str = "1:1", resolution: str = "1K") -> Path | None:
    """
    KREA AI image generation (async job pattern).
    Returns: saved image Path, or None on failure.
    """
    # 1. Load KREA_API_KEY from env
    # 2. POST /generate/image/krea/krea-2/medium → job_id
    # 3. Poll GET /jobs/{job_id} every 2s until completed/failed
    # 4. Download result.urls[0] to output/images/krea_{slug}.jpg
    # 5. Return Path or None
```

### Where to wire it

`image/thumbnail.py:187-190` — replace stub:

```python
def _krea_fallback(prompt: str, slug: str) -> Optional[Path]:
    """Krea AI fallback (async job pattern)."""
    try:
        from image.krea_client import generate_image
        return generate_image(prompt, slug=slug)
    except Exception as e:
        print(f"  [thumbnail] Krea fallback error: {e}")
        return None
```

**No other changes to thumbnail.py.** The dispatch loop at line 420-427 already calls `_krea_fallback()` and handles the return.

### Retry policy

- **No retry inside KREA client** — the async job itself has internal retries on KREA's side
- If job status is `failed` or `cancelled`, return None immediately
- Polling timeout: 90 seconds max (45 polls × 2s), then return None
- KREA's estimated time for Krea 2 medium is ~10s, so 90s is generous

### Return contract

`generate_image()` in krea_client.py returns `Path | None` — same as pollinations_client.py. The `_krea_fallback()` wrapper returns `Optional[Path]` — same as `_pollinations_fallback()`. The outer `generate_thumbnail()` already handles both.

### Image saving

Save to `output/images/krea_{slug}.jpg` — consistent with `pollinations_client.py` pattern (`{slug}_{width}x{height}.jpg`). The `add_text_overlay()` function in thumbnail.py will then process this file and output `thumb_{slug}.jpg`.

---

## 4. Config Schema

Add to `config/chain_config.yaml` (after `pollinations:` section):

```yaml
# === KREA AI (Phase 9 — Pollinations fallback) ===
krea:
  enabled: true
  api_base: https://api.krea.ai
  model: krea/krea-2/medium        # provider/model format for endpoint
  aspect_ratio: "1:1"
  resolution: "1K"
  creativity: medium
  poll_interval_seconds: 2
  poll_timeout_seconds: 90
```

API key goes in `.env`:
```
KREA_API_KEY=your-token-here
```

Loading pattern: `os.getenv("KREA_API_KEY")` — same as `UNSPLASH_ACCESS_KEY` in `_load_env()`.

---

## 5. File Touchpoints

| File | Change | Lines |
|------|--------|-------|
| `image/krea_client.py` | **NEW** — async job client | ~80 lines |
| `image/thumbnail.py` | Replace `_krea_fallback()` stub (line 187-190) | ~5 lines changed |
| `config/chain_config.yaml` | Add `krea:` section after `pollinations:` | ~10 lines added |
| `.env.example` | Add `KREA_API_KEY=` line | 1 line |
| `.env.common` (user's, not committed) | Add actual KREA_API_KEY | 1 line |

**No changes to:**
- `chain_publisher_core.py` — calls `generate_thumbnail()`, unaffected
- `chain_db.py` — no schema change (thumbnail_path/source already exist)
- `pillow_chart.py` — chart uses Pillow, no external API
- `image/injector.py` — operates on already-generated files
- `image/pollinations_client.py` — untouched, KREA is parallel not replacement

---

## 6. Pitfalls

| Pitfall | Mitigation |
|---------|------------|
| KREA async = slower than Pollinations sync | Acceptable — fallback only triggers when Pollinations fails. ~10s gen + 2s polls = ~15s total. |
| KREA returns URL, not bytes | Extra HTTP GET to download. One more failure point (download could fail). Wrap in try/except. |
| Korean text in prompt | KREA expects English prompts (same as Pollinations). `prompt_builder.py` already produces English. No change needed. |
| KREA API key missing | `_krea_fallback()` returns None gracefully → "All providers failed" message. No crash. |
| Polling infinite loop | Hard timeout: 90s (45 polls). Return None after. |
| KREA billing — no free tier | Fallback triggers rarely. Worst case $0.09/chain. Document in config comment. |
| NSFW filter differences | KREA may reject prompts Pollinations accepts (or vice versa). If KREA job status is `failed`, return None — next provider (none, end of chain) or "all failed". |
| Job status `cancelled` | Treat same as `failed` — return None. |
| Rate limits | KREA rate limits unknown. If 429, return None. Don't retry — fallback chain ends here. |

---

## 7. Recommendation

**Proceed with KREA fallback.** Rationale:

1. **Infrastructure ready** — `thumbnail.py` already has the dispatch loop and stub. Just need to fill in the stub.
2. **Small scope** — 1 new file (~80 lines), 5-line stub replacement, config addition. No architectural changes.
3. **Krea 2 medium** is cheap ($0.03) and fast (~10s). Good enough for fallback.
4. **Pay-per-use** is acceptable since fallback triggers rarely (Unsplash/Pexels cover most real-photo needs).
5. **No provider abstraction needed** — try/except in `_krea_fallback()` is sufficient. If we add a 5th provider later, then consider abstraction.

**Alternative considered:** Add Unsplash API as "always-on" with more permissive search. Rejected — Unsplash is already the primary provider. KREA adds AI generation capability that Unsplash/Pexels (real photos) can't provide for abstract/illustrative keywords.

**Do NOT use:**
- KREA SDK (`@krea-ai/sdk` is Node.js only, no Python SDK)
- Webhooks (overkill for single-image fallback)
- KREA video models (out of scope)
