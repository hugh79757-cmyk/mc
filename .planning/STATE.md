# State: mc (Manual Chain)

**Last updated:** 2026-07-18

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-18)

**Core value:** One random keyword → 3 interconnected blog posts on 3 different domains, each going deeper than the last, with images and cross-links — fully automated.
**Current focus:** Phase 5 — mde2 아키텍처 기반 발행 코어 전면 재작성

## Phase Status

| Phase | Status | Plans | Progress |
|-------|--------|-------|----------|
| 1 — Foundation & Config | ✅ Complete | config/chain_config.yaml, config/prompts.yaml, chain_db.py, mc_paths.py, chain_deriver.py, chain_publisher.py | 6/6 files |
| 2 — AI Content Generation | ✅ Complete | chain_drafter.py, image/, pipeline --dry-run/--draft/--image | 8/8 tasks verified |
| 3 — Image, Publishing & CLI | ✅ Complete | 8 tasks across 3 waves | Wave 1/2/3 ✅ |
| 4 — Loop Chain Direction | ✅ Complete | loop 방향 라우팅 + 2-CTA 주입 | Committed b9a6f53 |
| 5 — mde2 Architecture Rewrite | ✅ PLAN.md Verified | chain_publisher_core.py 전면 재작성 (7 fixes) | 3 Waves, 11 Tasks |

## Active Context

- GitHub repo: https://github.com/hugh79757-cmyk/mc
- Local path: /Users/twinssn/projects2/mc
- Runtime: opencode
- Git: initialized with README.md pushed
- 5000 path: /Users/twinssn/Projects/5000 (.venv at /Users/twinssn/Projects/5000/.venv)
- HUGO paths: /Users/twinssn/Projects/{rotcha-blog, informationhot-hugo, techpawz-hugo}

## Phase 3 Deliverables

| Wave | Task | File | Status |
|------|------|------|--------|
| W1 | 3-1 DB 확장 | `chain_db.py` — published_url/card_injected/publish_method 컬럼 | ✅ |
| W1 | 3-2 Config 확장 | `config/chain_config.yaml` — 5 sites + card_cta + publish_mode | ✅ |
| W2 | 3-3 Blogger Client | `shared/publishers/blogger_client.py` — OAuth2 + publish | ✅ |
| W2 | 3-4 Publisher Core | `chain_publisher_core.py` — Hugo/Blogger/Manual 분기 | ✅ |
| W2 | 3-5 Card Injector | `chain_card_injector.py` — 하단/중간 정규화 | ✅ |
| W3 | 3-6 Scheduler | `scheduler/__init__.py`, `cron_manager.py`, `launchd_manager.py`, `task_runner.py` | ✅ |
| W3 | 3-7 CLI 확장 | `chain_publisher.py` — --publish/--inject/--schedule 플래그 | ✅ |
| W3 | 3-8 README | `README.md` — Phase 3 사용법 | ✅ |

## Phase 3 Key Decisions

- **발행 순서**: Step 3→2→1 역순 (카드에서 **next** 링크가 항상 유효하도록)
- **카드 위치**: 하단 = 마지막 H2 직전, 중간 = 2번째 H2 (조건부, H3 ≥ 3개)
- **CTA 동적**: start/path/destination/depth/lateral 순회에 따라 변경
- **Blogger OAuth2**: Google Cloud Console → Desktop app credentials

## Next Action

1. ✅ `--publish` 실전 테스트 (Phase 1/2에서 생성된 chain #3~7)
2. `--schedule --launchd` 테스트 (plist 생성 검증)
3. 전체 Git 커밋
