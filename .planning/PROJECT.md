# mc (Manual Chain)

## What This Is

mc (Manual Chain) is an automated blog chain pipeline that takes a single seed keyword and produces a 3-depth-stage blog series across multiple Hugo sites. It derives topics at increasing depth levels (basic → applied → advanced), generates AI-written blog posts with a custom writing prompt, creates complementary images via Pollinations.ai Flux (free, no API key), and publishes them in reverse order so each post contains bridge cards linking to the next depth layer.

## Core Value

One random keyword → 3 interconnected blog posts on 3 different domains, each going deeper than the last, with images and cross-links — fully automated.

## Requirements

### Validated

(없음 — 실발행 후 검증 필요. 기존 Phase 1~36 기능은 ROADMAP/STATE에 ✅ 기록)

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
- **M2 Active (Phase 37-40) — 정보가 3-블로그 체인 복제**:
  - **CLONE-01~05**: 복제 레포 생성 + `.env` 재생성 + DB 분리 + shared vendoring + R2 매핑 키 추가
  - **INFRA-01~04**: 정보가 3사이트 shortcode 3종(파랑) + baseURL 수정 + ads.txt + CF Pages 매핑
  - **CFG-M2-01~05**: chain_config sites/chain_blogs/chain_blog_mapping 교체 + 카드 색상 파랑
  - **VERIFY-M2-01~03**: e2e dry-run 3종 + pytest green + DoD 체크리스트

- **M3 Active (Phase 41-47) — 9-Point Quality Pipeline** (M2 완료 후 착수):
  - **QG-01, QG-02**: Phase 41 — Output Contract Definition (YAML 계약서 + contract_loader)
  - **QG-03**: Phase 42 — Title-Body Contract Checker (제목-본문 정합성)
  - **QG-04, QG-05**: Phase 43 — Pre-Publish Research Step (사전 리서치 → factsheet)
  - **QG-05, QG-06**: Phase 44 — Factuality Filter (무출처 수치/후기 차단)
  - **QG-07, QG-08**: Phase 45 — Cross-Blog Dedup & Role Enforcer (문장 중복 + 역할 강제)
  - **QG-09**: Phase 46 — HTML Render Dedup Check (제목·CTA·문단 중복 탐지)
  - **QG-10, QG-11**: Phase 47 — Quality Scorer & Gate Integration (가중합 스코어 + 게이트)

### Out of Scope

- Multi-chain parallel execution — one chain at a time
- Pollinations gen endpoint (API key required) — legacy Flux endpoint is sufficient
- Text generation via Pollinations — OpenAI/GPT handles drafting

### Formerly Out of Scope (now in scope as of Phase 5)

- **Cloudflare R2 image upload** — ✅ Phase 5: R2-first image strategy replaces local static/images/
- **Non-Hugo publishing platforms (Blogger)** — ✅ Phase 3-5: Blogger API publishing with JSON tokens, markdown→HTML conversion

## Context

The project is built on the user's existing Hugo ecosystem with 3 blogs:
- **rotcha.kr** — basic/informational depth role (R2: hotissue-images)
- **informationhot.kr** — applied/practical depth role (R2: hotissue-images)
- **techpawz.com** — advanced/analytical depth role (R2: techpawz-images)

Images use **Unsplash/Pexels** for search + **Cloudflare R2** for storage. `mc <keyword>` CLI for single-command pipeline.

**M2 (2026-08-02) — 정보가 3-블로그 체인 복제:** 기존 mc를 복제해 `informationhot.kr / kuta.informationhot.kr / 5.informationhot.kr` 3-블로그 체인을 **독립 레포**로 운영. 조사(읽기 전용) 결과 필수 분리 지점 확정:
- **DB**: `config/chain_config.yaml:204` `db_path`가 5000 레포 공유 절대경로 → 복제 레포 내 경로로 분리 (미분리 시 크로스 발행)
- **shared**: `mc_paths.py:27` PATH_5000 하드코딩 → vendoring (ai_writer.py + env_loader.py + models.yaml) 후 제거
- **R2**: `image/r2_uploader.py` HUGO_R2_DOMAINS — kuta 키만 존재, informationhot/5 키 부재 → 추가 필요
- **git**: origin 단일 (hugh79757-cmyk/mc.git) → 복제 레포 별도 원격
- **인프라 실측**: CF Pages 3개 존재 + HTTPS 3/3 200 + AdSense 6677 일치. 미비: shortcode 3종 전부 부재, 5.informationhot-hugo baseURL `example.org` 플레이스홀더, ads.txt(kuta/5) 부재
- **대표 결정**: shared=vendoring, 카드 색상=체인 카드만 파랑(#2563eb)

The writing prompt is the user's existing SEO-optimized Hugo blog prompt with strict frontmatter rules, content structure, and formatting rules.

**CLI:** `mc <keyword>` → derive → draft → image → publish (3/3 sites). `--resume`, `--background`, `--site`, `--dry-run` flags available.

## Constraints

- **Rate Limit**: Pollinations anonymous rate limit ~1 req/15s — must build in 16s delays
- **Image Format**: Flux returns PNG — stored locally, served via Hugo static/
- **API Key**: OpenAI API key required for GPT drafting + image prompt generation
- **Domain Config**: 3 fixed Hugo domains with known local paths

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Depth-stage model over angle-split model | Random keywords don't fit fixed categories; depth stages (basic→applied→advanced) work universally | ✅ Phase 1-4 validated |
| Reverse publish order (3→2→1) | Ensures bridge cards have target URLs before insertion | ✅ Phase 3 validated |
| Pollinations Flux legacy endpoint | Fully free, no API key, sufficient quality for blog thumbnails | ✅ Phase 3 validated |
| English image prompts via GPT | Flux quality is dramatically better with English prompts | ✅ Phase 3 validated |
| Local static/images/ storage → R2-first (Phase 5) | Hugo serves directly, no external storage dependency → R2 enables cross-platform image sharing | ✅ Phase 5: R2-first |
| git push deploy → Hugo local build + Wrangler (Phase 5) | Cloudflare Pages auto-build is unreliable; local build + wrangler deploy is deterministic | ✅ Phase 5: Wrangler |
| Blogger pickle token → JSON token (Phase 5) | JSON is portable, debuggable, and aligns with mde2's proven pattern | ✅ Phase 5: JSON |
| `_ensure_frontmatter()` in chain_drafter.py (Phase 14 P1) | draft_md에 FM 없으면 생성, 있으면 보존. cli/mc.py patch 완전 제거 | ✅ Phase 14 P1 |
| published_md 컬럼 분리 (Phase 14 R2) | card injection이 R2 URL을 덮어쓰지 않도록 원본 draft_md 보존 + R2 교체 결과 분리 | ✅ Phase 14 R2 |
| techpawz R2 버킷 분기 (Phase 14 R2) | img.techpawz.com → techpawz-images, rotcha/infohot → hotissue-images | ✅ Phase 14 R2 |
| 정보가 3-블로그 체인 독립 레포 복제 (M2, 2026-08-02) | 3-체인 형식을 정보가 계열에서도 운영. 조사에서 DB/shared/R2 분리 지점 확정 | — Pending (Phase 37~40) |
| shared 의존성 vendoring (M2) | ai_writer.py + env_loader.py + models.yaml 복사, PATH_5000 제거 — 독립 레포 취지 | — Pending |
| 정보가 카드 색상 = 체인 카드만 파랑 (M2) | shortcode #2563eb 신규, html_renderer.py external 카드 구조 유지 | — Pending |
| M3 품질 계약서 = YAML per blog (Phase 41) | site×step별 필수 섹션·금지 섹션·제목 패턴·출처 규칙을 YAML로 정의. JSON-Schema 대신 관대한 YAML 선택 (config/schema.yaml 관례 준수) | — Pending |
| M3 source_tag 강제 (Phase 43) | AI 생성 콘텐츠에 출처 명시 강제. "확인된 사실"↔"AI 추론" 구분. 기존 _strip_prompt_leak() 패턴 활용 | — Pending |
| M3 사전 리서치 = Naver API + GPT 요약 (Phase 46) | 기존 search_retriever(Naver API) 재사용 + GPT 요약. 발행 전 사실 기반 데이터 수집 → 프롬프트 주입 | — Pending |
| M3 품질 점수 = 가중합 (Phase 47) | 계약 충족(40%) + 사실성(25%) + 역할 분리(20%) + 시각 품질(15%). 기준: 7.0미만 = 재생성, 9.0+ = 자동 승인 | — Pending |

---

*Last updated: 2026-08-18 — M3 (9점 품질 달성) GSD 정식 등록 (Requirements 40건)*

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
