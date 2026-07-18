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

## Phase 4: Loop Chain Direction (Historical)

**Goal:** ~~"loop" 체인 방향 추가~~ → 실질 구현은 Phase 6으로 이관

**Status:** 🔴 Deprecated — 실제 구현 없음. Phase 6이 대체

---

## Phase 5: mde2 Architecture Publish Rewrite

**Goal:** chain_publisher_core.py를 5000 패턴에서 mde2 아키텍처로 전면 재작성 (7 fixes).

**Status:** ✅ Complete (verified with Chain #9: 3/3 posts published to live Hugo sites)

**7 Core Fixes:**
1. **R2-first 이미지** — 로컬 static/images/ 제거, 전 이미지 R2 업로드
2. **Hugo 로컬 빌드 + Wrangler 배포** — git push 폐기
3. **테마별 frontmatter 분기** — PaperMod cover.image, Blowfish featureimage
4. **slug 기반 URL** — filename 기반 URL 생성 버그 수정
5. **Blogger JSON 토큰** — pickle → JSON, markdown→HTML 변환, thumb 프리픽스
6. **4-layer dedup** — fcntl lock + DB UNIQUE + API title 검색 + ghost 복구
7. **카드 주입 별도 스텝** — Hugo path에서 제거, --inject-card 플래그

---

## Phase 6: Loop Funnel (Blowfish Hub + 2-CTA Spokes)

**Goal:** Spoke(3 posts) → Hub(1 page at rotcha.kr/hub/{slug}/) → dual CTA (info + conversion) injection.

**Status:** ✅ Complete. All 3 waves implemented and verified (hub page generation + publish, dual-CTA injection, CLI --hub/--spoke/--loop flags).

**Plan file:** `.planning/phases/phase-06/PLAN.md`

**Key deliverables:**
1. `draft_hub_page.py` — hub index.md generator (Blowfish cardView)
2. `draft_loop_spoke.py` — spoke loop role marker
3. `chain_db.py` — loop_chains table + loop_role migration
4. `chain_card_injector.py` — DualCTAInjector class
5. `chain_publisher_core.py` — publish_hub_page() method
6. `chain_publisher.py` — --loop, --hub, --spoke CLI flags
7. `config/chain_config.yaml` — loop section + rotcha theme fix (PaperMod→Blowfish)
8. `rotcha-blog/config/_default/params.toml` — mainSections에 "hub" 추가

---

## Summary

| Phase | Focus | Plans | Status |
|-------|-------|-------|--------|
| 1 | Foundation & Config | 3 | ✅ Complete |
| 2 | AI Content Generation | 2 | ✅ Complete |
| 3 | Image, Publishing & CLI | 6 | ✅ Complete |
| 4 | Loop Chain Direction (Hist.) | — | 🔴 Deprecated |
| 5 | mde2 Architecture Publish Rewrite | — | ✅ Complete |
| 6 | Loop Funnel (Blowfish Hub + 2-CTA) | 8 | ✅ Complete |
| 7 | Search-Augmented Drafting (Naver API) | 7 | ✅ Complete |
| **Total** | | **26** | |

---

*Last updated: 2026-07-18 — Phase 6 complete, Phase 7 complete*
