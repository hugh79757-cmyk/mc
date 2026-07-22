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
| 8 | Chart Generation (pillow_chart.py) | 7 | ✅ Complete |
| 9 | Publish Quality Fix | 8 | ◆ Planning |
| 10 | Phase 9 Aftermath — 회귀 방지 + 잔여 이슈 | 5 | ○ Pending |
| 11 | HTML 릭 + 광고 겹침 수정 | 10 | ✅ Complete |
| 12 | mc R2 업로더 분리 | — | ✅ Complete |
| **13** | **콘텐츠 고도화 (Content Refinement)** | **1** | **◆ Planning** |
| **Total** | | **~64** | |

---

---

## Phase 9: Publish Quality Fix

**Goal:** 발행 품질 3대 결함(프롬프트 릭, 이미지 미삽입, 썸네일 가독성)을 일괄 수정한다.

**Plans:**
1. **프롬프트 릭 필터 재작성** — `_strip_prompt_leak()`를 frontmatter 이후에도 동작하도록 재작성, 들여쓰기 수정
2. **이미지 치환 순서 수정** — `_sanitize_markdown_body()`의 마커 제거 regex를 치환 코드 이후로 이동
3. **썸네일 개선** — 폰트 크기 48→64px, elif 버그 수정, 위치/그림자 조정, CJK 줄바꿈 개선
4. **프롬프트 마커 지시문 수정** — GPT에게 `<!-- thumbnail/image -->` 삽입 지시 제거

**Requirements covered:** 품질 (프롬프트 릭, 이미지 삽입, 썸네일 가독성)

**Verification criteria:**
- 새 체인 생성 시 프롬프트 헤더가 본문에 없음
- `<!--todo:image-->`가 R2 URL로 교체되어 발행
- 썸네일에서 제목 텍스트가 선명하게 보임
- E2E 발행: `python chain_publisher.py --seed "테스트" --draft --image --publish` → 3개 사이트 깔끔 발행

**Plan file:** `.planning/phases/phase-09/PLAN.md`

---

## Phase 10: Phase 9 Aftermath — 회귀 방지 및 잔여 이슈 해결

**Goal:** Phase 9에서 발견·수정된 모든 fix의 회귀를 방지하고, 3개 사이트에 CSS/SRI 수정을 전파하며, R2 썸네일 업로드 실패의 근본 원인을 수정한다.

**Plans:**
1. **R2 썸네일 업로드 실패 수정** — `get_r2_client()` credentials 누락 원인 규명 및 수정, `upload_all_images()` 호출 체인 검증
2. **3개 사이트 CSS/SRI 일괄 적용** — informationhot, techpawz에도 `head.html` + `fixed-fill-blur.html` SRI/CORS 수정 전파
3. **회귀 방지 audit 체계** — `audit_posts.py` 전수검사 (프롬프트 릭, 이미지 마커, CTA 블록, CSS 렌더링)
4. **E2E 검증 + 3사이트 재배포** — Hugo 빌드 + CF Pages 배포, HTTP 200 확인

**Requirements covered:** 품질 (회귀 방지, R2 업로드, CSS/SRI 일괄 적용)

**Verification criteria:**
- 신규 체인 생성 → 모든 썸네일이 R2에 정상 업로드됨
- 3개 사이트 모두 CSS SRI/CORS 경고 없이 렌더링
- `audit/audit_chain.py` 전수검사 0건 (프롬프트 릭, 미해소 마커, CTA 블록 0)
- `python chain_publisher.py --chain-id N --publish` E2E 통과

**Plan file:** `.planning/phases/phase-10/PLAN.md`

---

*Last updated: 2026-07-22 — Phase 13: 콘텐츠 고도화*

## Phase 13: 콘텐츠 고도화 (Content Refinement)

**Goal:** 콘텐츠 품질 3대 문제(이미지 관련성 부족, 마크다운 기호 누출, 표 렌더링 깨짐)를 수정한다.

**Plans:**
1. **이미지 관련성 개선** — Contextual prompt engineering (title+angle), Unsplash/Pexels 본문 이미지 확장
2. **마크다운 기호 제거 + 표 렌더링** — `_clean_markdown_symbols()`, `_convert_tables_to_html()`, prompts.yaml 강화

**Requirements covered:** R1 (Image Relevance), R2 (Markdown Symbol Leakage), R3 (Table Rendering)

**Plan file:** `.planning/phase-13/PLAN.md`

---

| Phase 1-12 core pipeline 완료. 남은 후보 항목:

| Candidate | Requirement | Value | Effort |
|-----------|-------------|-------|--------|
| Phase 14: Auto-approval | PL-v2-02 | operator checkpoint 없이 자동 발행 | Low |
| Phase 15: Scheduled Execution | PL-v2-03 | cron 기반 정기 체인 실행 | Medium |
| Phase 16: Parallel Chains | PL-v2-01 | 다중 seed 동시 실행 | High |
