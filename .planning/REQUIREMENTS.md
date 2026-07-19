# Requirements: mc (Manual Chain)

**Defined:** 2026-07-18
**Core Value:** One random keyword → 3 interconnected blog posts on 3 different domains, each going deeper than the last, with images and cross-links — fully automated.

## v1 Requirements

### Config & Foundation

- [ ] **CFG-01**: chain_config.yaml defines 3 depth stages (basic/applied/advanced) with domain, hugo_root, images_root, depth_role, and available_categories per step
- [ ] **CFG-02**: prompts.yaml stores derive/draft/image system prompts with `{{seed_keyword}}` template variable support
- [ ] **DB-01**: chain_db.py creates/manages SQLite DB tracking chain state: seed, step details, publish URLs, status per step

### Topic Derivation

- [ ] **DERV-01**: chain_deriver takes a seed keyword and AI-derives 3 depth-stage topics with title, angle, category_guess, and bridge_logic
- [ ] **DERV-02**: Derivation prompt routes keyword types (game/IT → automation, travel → investment, health → insurance) for natural step-3 expansion
- [ ] **DERV-03**: Output is structured JSON parseable for downstream consumption

### Content Drafting

- [ ] **DRAFT-01**: chain_drafter generates complete Hugo blog post MD using the user's writing prompt
- [ ] **DRAFT-02**: Chain context block (step number, previous/next article context, bridge requirement) is dynamically injected into the writing prompt
- [ ] **DRAFT-03**: Output matches Hugo frontmatter rules (title, description, tags, categories in one-line array format, draft: true)

### Image Generation

- [ ] **IMG-01**: pollinations_client generates Flux images via `image.pollinations.ai/prompt/{prompt}?model=flux&nologo=true` with 16s rate-limit delay
- [ ] **IMG-02**: Thumbnail images at 1200×630 and content images at 800×500
- [ ] **IMG-03**: prompt_builder converts Korean blog topics into English image prompts via GPT for better Flux quality
- [ ] **IMG-04**: image_injector inserts thumbnail path into frontmatter `image:` field and content image after first H2 section
- [ ] **IMG-05**: All images stored at `static/images/{slug}/` for Hugo auto-serving

### Publishing & Bridge Cards

- [ ] **PUB-01**: chain_publisher_core writes Hugo draft MD files to correct domain path
- [ ] **PUB-02**: Publishing order is reverse (step 3 → step 2 → step 1) so bridge card URLs are available
- [ ] **CARD-01**: chain_card_injector adds cross-reference bridge card to each post pointing to adjacent depth-stage post

### CLI Orchestration

- [ ] **CLI-01**: `chain_publisher.py --seed "keyword"` orchestrates full pipeline: derive → draft → image → publish
- [ ] **CLI-02**: Operator review checkpoints after topic derivation (y/n/edit) and after draft generation
- [ ] **CLI-03**: Progress indication and error handling for each stage

### Project Scaffolding

- [ ] **SCF-01**: .gitignore excludes `__pycache__/`, `.env`, `data/*.db`, `output/`
- [ ] **SCF-02**: requirements.txt includes openai, requests, pyyaml, click, beautifulsoup4, python-slugify
- [ ] **SCF-03**: .env.example documents all required env vars (OPENAI_API_KEY, Hugo roots)

## v2 Requirements

### Image Enhancement

- **IMG-v2-01**: Cloudflare R2 image upload instead of local static/
- **IMG-v2-02**: WebP conversion on save for smaller file sizes
- **IMG-v2-03**: Pollinations gen endpoint with API key for higher quality models

### Pipeline

- **PL-v2-01**: Parallel chain execution (multiple seeds at once)
- **PL-v2-02**: Draft auto-approval mode (no operator checkpoint)
- **PL-v2-03**: Scheduled/routine chain execution (cron)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Non-Hugo platforms | All 3 blogs are Hugo; v1 is Hugo-only |
| Text gen via Pollinations | Pollen credits required; OpenAI handles drafting |
| Multi-account Pollinations | Single anonymous tier sufficient for blog scale |
| Image alt-text generation | Static alt text sufficient for v1 |
| Social media auto-posting | Out of scope for core chain pipeline |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| SCF-01 | Phase 1 | ✅ Validated |
| SCF-02 | Phase 1 | ✅ Validated |
| SCF-03 | Phase 1 | ✅ Validated |
| CFG-01 | Phase 1 | ✅ Validated |
| CFG-02 | Phase 1 | ✅ Validated |
| DB-01 | Phase 1 | ✅ Validated |
| DERV-01 | Phase 2 | ✅ Validated |
| DERV-02 | Phase 2 | ✅ Validated |
| DERV-03 | Phase 2 | ✅ Validated |
| DRAFT-01 | Phase 2 | ✅ Validated |
| DRAFT-02 | Phase 2 | ✅ Validated |
| DRAFT-03 | Phase 2 | ✅ Validated |
| IMG-01 | Phase 3 | ✅ Validated |
| IMG-02 | Phase 3 | ✅ Validated (1200×630 thumbnail) |
| IMG-03 | Phase 3 | ✅ Validated |
| IMG-04 | Phase 3 | ✅ Validated (Phase 7: featureimage field) |
| IMG-05 | Phase 3 | 🔴 Deprecated → IMG-v2-01 (R2) |
| PUB-01 | Phase 3 | ✅ Validated |
| PUB-02 | Phase 3 | ✅ Validated |
| CARD-01 | Phase 3 | ✅ Validated (Phase 6: DualCTA) |
| CLI-01 | Phase 3 | ✅ Validated |
| CLI-02 | Phase 3 | ✅ Validated |
| CLI-03 | Phase 3 | ✅ Validated |

### Phase 5-8 Additions (retroactively mapped)

| Requirement | Phase | Status |
|-------------|-------|--------|
| IMG-v2-01 (R2 upload) | Phase 5 | ✅ Validated |
| IMG-v2-02 (WebP) | Phase 5 | ○ Pending (low priority) |
| PUB-v2-01 (mde2 rewrite, 7 fixes) | Phase 5 | ✅ Validated |
| LOOP-01 (Hub + spoke funnel) | Phase 6 | ✅ Validated |
| LOOP-02 (DualCTA injection) | Phase 6 | ✅ Validated |
| SEARCH-01 (Naver API context) | Phase 7 | ✅ Validated |
| IMG-v3-01 (Unsplash/Pexels thumbnail) | Phase 7 | ✅ Validated |
| IMG-v3-02 (Content image pipeline) | Phase 7 | ✅ Validated |
| CHART-01 (GPT chart recognition) | Phase 8 | ✅ Validated |
| CHART-02 (Pillow chart rendering) | Phase 8 | ✅ Validated |
| CHART-03 (Korean font support) | Phase 8 | ✅ Validated |

**Coverage:**
- v1 requirements: 23 total, 22 validated, 1 deprecated (IMG-05 → R2)
- v2/v3 additions: 11 mapped to Phase 5-8
- Unmapped: 0 ✓

---
*Requirements defined: 2026-07-18*
*Last updated: 2026-07-19 — Phase 8 transition, traceability sync*
