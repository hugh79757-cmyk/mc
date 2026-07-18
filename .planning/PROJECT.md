# mc (Manual Chain)

## What This Is

mc (Manual Chain) is an automated blog chain pipeline that takes a single seed keyword and produces a 3-depth-stage blog series across multiple Hugo sites. It derives topics at increasing depth levels (basic → applied → advanced), generates AI-written blog posts with a custom writing prompt, creates complementary images via Pollinations.ai Flux (free, no API key), and publishes them in reverse order so each post contains bridge cards linking to the next depth layer.

## Core Value

One random keyword → 3 interconnected blog posts on 3 different domains, each going deeper than the last, with images and cross-links — fully automated.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- **DERV-01**: chain_deriver can take a seed keyword and derive 3 depth-stage topics (basic/applied/advanced) with title, angle, category_guess, and bridge_logic
- **DERV-02**: Derivation prompt supports keyword-type routing (game/IT → automation, travel → investment, health → insurance)
- **DRAFT-01**: chain_drafter can generate a complete Hugo blog post MD from a topic using the user's writing prompt + chain context injection
- **DRAFT-02**: Chain context block is dynamically inserted into the writing prompt (step number, previous/next article context)
- **CFG-01**: chain_config.yaml defines 3 depth stages with domain, hugo_root, images_root, depth_role, available_categories per step
- **CFG-02**: prompts.yaml stores derive/draft/image system prompts with template variables
- **DB-01**: chain_db tracks chain state: seed, step details, publish URLs, status per step
- **IMG-01**: pollinations_client generates Flux images (thumbnail 1200×630 + content 800×500) with rate-limit awareness (16s delay)
- **IMG-02**: prompt_builder uses GPT to convert Korean topics into English image prompts
- **IMG-03**: image_injector inserts thumbnail into frontmatter and content image after first H2 section
- **PUB-01**: chain_publisher_core writes Hugo drafts to correct domain path with proper frontmatter
- **PUB-02**: Publishing order is reverse (step 3 → step 2 → step 1) so bridge cards can be inserted
- **CARD-01**: chain_card_injector adds cross-reference bridge cards pointing to adjacent depth-stage posts
- **CLI-01**: chain_publisher.py CLI accepts `--seed "keyword"` and orchestrates the full pipeline
- **CLI-02**: CLI includes operator review checkpoints after derive and draft stages

### Out of Scope

- Multi-chain parallel execution — one chain at a time
- Cloudflare R2 image upload — local Hugo static/images/ only
- Pollinations gen endpoint (API key required) — legacy Flux endpoint is sufficient
- Non-Hugo publishing platforms — Hugo-only v1
- Text generation via Pollinations — OpenAI/GPT handles drafting

## Context

The project is built on the user's existing Hugo ecosystem with 3 blogs:
- **rotcha.kr** — basic/informational depth role
- **informationhot.kr** — applied/practical depth role
- **techpawz.com** — advanced/analytical depth role

Images use **Pollinations.ai Flux** which is fully free without API key as of 2026. Rate limit: ~1 req/15 sec anonymous. 6 images per chain = ~90 sec wait. English prompts produce significantly better Flux results.

The writing prompt is the user's existing SEO-optimized Hugo blog prompt with strict frontmatter rules, content structure, and formatting rules.

Previous 5000 project's hugo_writer.py is referenced for publishing logic reuse.

## Constraints

- **Rate Limit**: Pollinations anonymous rate limit ~1 req/15s — must build in 16s delays
- **Image Format**: Flux returns PNG — stored locally, served via Hugo static/
- **API Key**: OpenAI API key required for GPT drafting + image prompt generation
- **Domain Config**: 3 fixed Hugo domains with known local paths

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Depth-stage model over angle-split model | Random keywords don't fit fixed categories; depth stages (basic→applied→advanced) work universally | — Pending |
| Reverse publish order (3→2→1) | Ensures bridge cards have target URLs before insertion | — Pending |
| Pollinations Flux legacy endpoint | Fully free, no API key, sufficient quality for blog thumbnails | — Pending |
| English image prompts via GPT | Flux quality is dramatically better with English prompts | — Pending |
| Local static/images/ storage | Hugo serves directly, no external storage dependency | — Pending |

---

*Last updated: 2026-07-18 after initialization*

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state
