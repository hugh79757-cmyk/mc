# State: mc (Manual Chain)

**Last updated:** 2026-07-28

## Project Reference

See: .planning/PROJECT.md

**Core value:** One random keyword → 3 interconnected blog posts on 3 different domains, each going deeper than the last, with images and cross-links — fully automated.
**Current focus:** 카테고리 10종 체계 구축 + _parse_derivation 안정성 개선. Phase 26 리팩토링 계획 수립 완료.

## Phase Status

| Phase | Status | Progress |
|-------|--------|----------|
| 1 — Foundation & Config | ✅ Complete | config, DB, paths |
| 2 — AI Content Generation | ✅ Complete | drafter, image pipeline |
| 3 — Image, Publishing & CLI | ✅ Complete | Pollinations, publisher, card injector |
| 4 — Loop Chain Direction | ✅ Deprecated | Phase 6이 대체 |
| 5 — mde2 Architecture Rewrite | ✅ Complete | R2-first, Wrangler deploy |
| 6 — Loop Funnel | ✅ Complete | Hub + dual-CTA spokes |
| 7 — Search-Augmented Drafting | ✅ Complete | Naver API context |
| 8 — Chart Generation | ✅ Complete | pillow_chart.py + GPT recognition |
| 9 — Publish Quality Fix | ✅ Complete | 프롬프트 릭·이미지·썸네일 |
| 10 — Phase 9 Aftermath | ✅ Complete | 회귀 방지 + CSS/SRI |
| 11 — HTML 릭 + 광고 겹침 | ✅ Complete | 10 tasks, 5 waves |
| 12 — mc R2 업로더 분리 | ✅ Complete | R2 독립 모듈 |
| 13 — 콘텐츠 고도화 | ✅ Complete | markdown cleanup + contextual image |
| **14 — CLI `mc <keyword>`** | **✅ Complete** | **W1~W4 + P1 frontmatter + P2 backfill + R2 published_md + techpawz bucket** |
| **15 — informationhot → issue.techpawz 슬롯 교체** | **✅ Complete** | **Wave 0~4: config/code/prompts 교체 + pub ID 통일 + 검증** |
| **17 — CTA 시나리오 설계** | **✅ Complete** | **CTA-SCENARIO.md 작성, 대표님 검토 대기** |
| **20 — 검색 상시화 + GROUNDING 확장** | **✅ Complete** | **--search global default + STOCK & AUTOMOTIVE GROUNDING block** |
| **24~25 — 카테고리 10종 확장** | **✅ Complete** | **customer_service/gov_finance/shopping_brand/golf_course/medicine lateral 프롬프트 + step_sections** |
| **26 — 코드베이스 리팩토링** | **🔲 Planning** | **3-wave 계획 수립 완료, 미착수** |

## Current Metrics

- **pytest:** 309/309 ✅
- **카테고리:** 10종 (travel/real_estate/automotive/stock/customer_service/gov_finance/shopping_brand/golf_course/medicine/etc)
- **라이브:** 3/3 R2 200 ✅ (rotcha/infohot/techpawz)
- **`mc` 전역 명령:** ✅ `/Users/twinssn/.kaggle-env/bin/mc`
- **파서 안정성:** BOM/제로폭/코드펜스/텍스트 전후 대응 + 테스트 12건

## Active Context

- GitHub repo: https://github.com/hugh79757-cmyk/mc
- Local path: /Users/twinssn/projects2/mc
- Runtime: opencode
- 5000 path: /Users/twinssn/Projects/5000
- Hugo paths: /Users/twinssn/Projects/{rotcha-blog, issue-techpawz-hugo, techpawz-hugo}
- Chain DB: /Users/twinssn/Projects/5000/data/mc_chains.db
- Shared themes: /Users/twinssn/Projects/shared-themes
- Branch: `feat/keyword-category-template`

## Next Action

1. **운영 계속** — 카테고리 10종 체계 가동 중. 새 키워드 → `mc "키워드"` 실행
2. **(a) 40건 고아 이미지** — 재발행 전까지 이미지 없음
3. **Automotive 검색 개선** — search_retriever에 automotive-specific search template 필요

