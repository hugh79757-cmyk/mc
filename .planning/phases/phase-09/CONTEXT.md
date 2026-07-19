# Phase 9 Context: KREA AI Fallback

## Goal

Implement KREA AI as the 4th image provider in `thumbnail.py`'s fallback chain. When Unsplash → Pexels → Pollinations all fail, KREA generates the thumbnail image.

## Locked Scope

- **In:** KREA async job client, stub replacement, config, env var
- **Out:** Provider abstraction, WebP, Pollinations API key, chart fallback, content images

## Key Constraint

`thumbnail.py` already has the dispatch loop and `_krea_fallback()` stub (line 187). **No structural changes** — just fill the stub with a real KREA client call.

## API Summary

- Base: `https://api.krea.ai`
- Auth: `Bearer KREA_API_KEY`
- Model: `krea/krea-2/medium` ($0.03, ~10s)
- Pattern: POST create job → GET poll every 2s → download result URL
- Returns: `Path | None` (same as pollinations_client.py)

## Files

- NEW: `image/krea_client.py` (~80 lines)
- MODIFY: `image/thumbnail.py:187-190` (stub → real call)
- MODIFY: `config/chain_config.yaml` (add `krea:` section)
- MODIFY: `.env.example` (add `KREA_API_KEY=`)
