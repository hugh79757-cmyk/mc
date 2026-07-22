# State: mc (Manual Chain)

**Last updated:** 2026-07-23

## Project Reference

See: .planning/PROJECT.md

**Core value:** One random keyword → 3 interconnected blog posts on 3 different domains, each going deeper than the last, with images and cross-links — fully automated.
**Current focus:** 이미지 파이프라인 전체 종료 — Phase 14.1 대기

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

## Current Metrics

- **pytest:** 179/179 ✅
- **라이브:** 3/3 R2 200 ✅ (rotcha/infohot/techpawz)
- **이미지 파이프라인:** 전체 종료
- **`mc` 전역 명령:** ✅ `/Users/twinssn/.kaggle-env/bin/mc`

## Active Context

- GitHub repo: https://github.com/hugh79757-cmyk/mc
- Local path: /Users/twinssn/projects2/mc
- Runtime: opencode
- 5000 path: /Users/twinssn/Projects/5000
- Hugo paths: /Users/twinssn/Projects/{rotcha-blog, informationhot-hugo, techpawz-hugo}
- Chain DB: /Users/twinssn/Projects/5000/data/mc_chains.db
- Shared themes: /Users/twinssn/Projects/shared-themes

## Phase 14 Deliverables

| Wave | Task | Status |
|------|------|--------|
| W1 | `cli/mc.py` argparse + `_run_full()` + 25 tests | ✅ |
| W2 | `_resume_chain()` DB state detection + 4 tests | ✅ |
| W3 | `_run_background()` subprocess + flush logging + 6 tests | ✅ |
| W4 | `pyproject.toml` console_scripts + `pip install -e .` | ✅ |
| P1 | `_ensure_frontmatter()` 정식 구현 + cli/mc.py patch 제거 + 6 tests | ✅ |
| P2 | 고아 content_image_path 15/15 백필 | ✅ |
| R2 | published_md 컬럼 + card injection R2 보존 + 3 tests | ✅ |
| R2 | techpawz R2 버킷 분기 + 5 tests | ✅ |

## Next Action

1. **Phase 14.1** — cron/launchd 스케줄링, dashboard CLI, `audit_chain.py` 통합 (별도 milestone, 공수 큼)
2. **(a) 43건 고아** — 신규 발행 W6 게이트로 차단, 기존 43건은 재발행 전까지 이미지 없음
3. **P3 Blowfish CSS** — 라이브 3/3 기능 정상, CSS 미세 복구 영역
