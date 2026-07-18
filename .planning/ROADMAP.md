# Roadmap: mc (Manual Chain)

**Created:** 2026-07-18
**Granularity:** Coarse (3 phases)

## Phase 1: Foundation & Config

**Goal:** Project scaffold, config system, and chain state database operational.

**Plans:**
1. **Project Scaffold** — Create directory structure, .gitignore, requirements.txt, .env.example, README.md
2. **Config System** — chain_config.yaml (3 depth stages with domain/hugo_root/images_root/categories), prompts.yaml (derive/draft/image prompts with template vars)
3. **Chain Database** — chain_db.py with SQLite schema for chain state tracking

**Requirements covered:** SCF-01, SCF-02, SCF-03, CFG-01, CFG-02, DB-01

**Verification criteria:**
- `python -c "from chain_db import ChainDB; db = ChainDB('data/test.db'); db.create_chain('test', {}); print('OK')"` succeeds
- chain_config.yaml loads as valid YAML with all 3 steps
- prompts.yaml contains derive, draft, and image prompt sections

---

## Phase 2: AI Content Generation

**Goal:** Topic derivation AI and blog post drafting with chain context injection.

**Plans:**
1. **Topic Deriver** — chain_deriver.py: takes seed keyword, calls GPT with derive prompt, returns structured JSON (3 topics with title/angle/category_guess/bridge_logic)
2. **Blog Drafter** — chain_drafter.py: takes derived topic + chain context, injects chain context block into writing prompt, generates Hugo MD draft

**Requirements covered:** DERV-01, DERV-02, DERV-03, DRAFT-01, DRAFT-02, DRAFT-03

**Verification criteria:**
- `chain_deriver.derive("츄니토리")` returns valid JSON with 3 steps and bridge_logic
- `chain_drafter.draft(step=2, topic={...}, chain_context={...})` returns valid Hugo MD with frontmatter
- Generated frontmatter passes the user's output checklist (one-line arrays, draft: true, no colon in title)

---

## Phase 3: Image, Publishing & CLI

**Goal:** Image generation pipeline, reverse-order publishing, bridge cards, and unified CLI.

**Plans:**
1. **Pollinations Client** — image/pollinations_client.py: Flux image generation with rate-limit handling
2. **Image Prompt Builder** — image/prompt_builder.py: GPT converts Korean topics → English image prompts
3. **Image Injector** — image/image_injector.py: insert thumbnail into frontmatter, content image after first H2
4. **Publisher Core** — chain_publisher_core.py: writes Hugo draft MD to correct domain path
5. **Card Injector** — chain_card_injector.py: adds cross-reference bridge cards
6. **CLI Orchestrator** — chain_publisher.py: `--seed` entry point orchestrating full pipeline with checkpoints

**Requirements covered:** IMG-01, IMG-02, IMG-03, IMG-04, IMG-05, PUB-01, PUB-02, CARD-01, CLI-01, CLI-02, CLI-03

**Verification criteria:**
- `python chain_publisher.py --seed "츄니토리"` completes full pipeline end-to-end
- 3 Hugo draft MD files created across rotcha/informationhot/techpawz with correct frontmatter
- 6 images generated (2 per post) and referenced in MD files
- Step 3 bridge card present in Step 2 article, Step 2 bridge card in Step 1 article

---

## Summary

| Phase | Focus | Plans | Requirements |
|-------|-------|-------|-------------|
| 1 | Foundation & Config | 3 | 6 |
| 2 | AI Content Generation | 2 | 6 |
| 3 | Image, Publishing & CLI | 6 | 11 |
| **Total** | | **11** | **23** |

---
*Last updated: 2026-07-18 after initial definition*
