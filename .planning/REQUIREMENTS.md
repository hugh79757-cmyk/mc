# Requirements: mc (Manual Chain)

**Defined:** 2026-07-18
**Last updated:** 2026-07-23 — Phase 14 + R2 이미지 수정 완료
**Core Value:** One random keyword → 3 interconnected blog posts on 3 different domains, each going deeper than the last, with images and cross-links — fully automated.

## v1 Requirements

| Requirement | Phase | Status |
|-------------|-------|--------|
| SCF-01: .gitignore | Phase 1 | ✅ Validated |
| SCF-02: requirements.txt | Phase 1 | ✅ Validated |
| SCF-03: .env.example | Phase 1 | ✅ Validated |
| CFG-01: chain_config.yaml | Phase 1 | ✅ Validated |
| CFG-02: prompts.yaml | Phase 1 | ✅ Validated |
| DB-01: chain_db.py | Phase 1 | ✅ Validated |
| DERV-01: chain_deriver 3 topics | Phase 2 | ✅ Validated |
| DERV-02: keyword routing | Phase 2 | ✅ Validated |
| DERV-03: structured JSON | Phase 2 | ✅ Validated |
| DRAFT-01: Hugo MD generation | Phase 2 | ✅ Validated |
| DRAFT-02: chain context injection | Phase 2 | ✅ Validated |
| DRAFT-03: Hugo frontmatter rules | Phase 2 | ✅ Validated |
| IMG-01: Pollinations Flux | Phase 3 | ✅ Validated |
| IMG-02: thumbnail 1200×630 | Phase 3 | ✅ Validated |
| IMG-03: GPT image prompts | Phase 3 | ✅ Validated |
| IMG-04: image_injector | Phase 3 | ✅ Validated (Phase 7: featureimage) |
| IMG-05: static/images/ | Phase 3 | 🔴 Deprecated → IMG-v2-01 (R2) |
| PUB-01: Hugo draft MD | Phase 3 | ✅ Validated |
| PUB-02: reverse publish order | Phase 3 | ✅ Validated |
| CARD-01: bridge cards | Phase 3 | ✅ Validated (Phase 6: DualCTA) |
| CLI-01: chain_publisher.py CLI | Phase 3 | ✅ Validated |
| CLI-02: operator checkpoints | Phase 3 | ✅ Validated |
| CLI-03: progress/error handling | Phase 3 | ✅ Validated |

## v2/v3 Additions (Phase 5-8)

| Requirement | Phase | Status |
|-------------|-------|--------|
| IMG-v2-01 (R2 upload) | Phase 5 | ✅ Validated |
| IMG-v2-02 (WebP) | Phase 5 | ○ Pending (low priority) |
| PUB-v2-01 (mde2 rewrite) | Phase 5 | ✅ Validated |
| LOOP-01 (Hub + spoke) | Phase 6 | ✅ Validated |
| LOOP-02 (DualCTA) | Phase 6 | ✅ Validated |
| SEARCH-01 (Naver API) | Phase 7 | ✅ Validated |
| IMG-v3-01 (Unsplash/Pexels) | Phase 7 | ✅ Validated |
| IMG-v3-02 (Content image pipeline) | Phase 7 | ✅ Validated |
| CHART-01 (GPT chart recognition) | Phase 8 | ✅ Validated |
| CHART-02 (Pillow chart rendering) | Phase 8 | ✅ Validated |
| CHART-03 (Korean font support) | Phase 8 | ✅ Validated |

## Phase 14 Additions

| Requirement | Phase | Status |
|-------------|-------|--------|
| CLI-v2-01: `mc <keyword>` single entry point | Phase 14 | ✅ Validated |
| CLI-v2-02: `--resume` interrupted chain | Phase 14 | ✅ Validated |
| CLI-v2-03: `--background` detached process | Phase 14 | ✅ Validated |
| CLI-v2-04: `pip install -e .` global `mc` command | Phase 14 | ✅ Validated |
| CLI-v2-05: `_ensure_frontmatter()` FM preservation | Phase 14 P1 | ✅ Validated |
| IMG-v4-01: published_md for card injection R2 preservation | Phase 14 R2 | ✅ Validated |
| IMG-v4-02: techpawz R2 bucket branching (techpawz-images) | Phase 14 R2 | ✅ Validated |
| IMG-v4-03: content_image_path backfill (15/15) | Phase 14 P2 | ✅ Validated |

## Coverage

- v1 requirements: 23 total, 22 validated, 1 deprecated (IMG-05 → R2)
- v2/v3 additions: 11 mapped to Phase 5-8
- Phase 14 additions: 8 mapped
- Unmapped: 0 ✓

---

## Out of Scope

| Feature | Reason |
|---------|--------|
| Non-Hugo platforms | All 3 blogs are Hugo; v1 is Hugo-only |
| Text gen via Pollinations | Pollen credits required; OpenAI handles drafting |
| Multi-account Pollinations | Single anonymous tier sufficient for blog scale |
| Image alt-text generation | Static alt text sufficient for v1 |
| Social media auto-posting | Out of scope for core chain pipeline |

## Traceability

**Total:** 42 requirements (23 v1 + 11 v2/v3 + 8 Phase 14) — 41 validated, 1 deprecated, 0 unmapped
