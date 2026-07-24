# State: mc (Manual Chain)

**Last updated:** 2026-07-24 14:50

## Project Reference

See: .planning/PROJECT.md

**Core value:** One random keyword → 3 interconnected blog posts on 3 different domains, each going deeper than the last, with images and cross-links — fully automated.
**Current focus:** Phase 20 완료 — --search global default + STOCK & AUTOMOTIVE GROUNDING block. 검증 완료.

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
| **17 — CTA 시나리오 설계** | **✅ 설계 완료** | **CTA-SCENARIO.md 작성, 대표님 검토 대기** |
| **20 — 검색 상시화 + GROUNDING 확장** | **✅ Complete** | **--search global default (--no-search to disable). STOCK & AUTOMOTIVE GROUNDING block. pytest 246/246.** |

## Current Metrics

- **pytest:** 246/246 ✅
- **라이브:** 3/3 R2 200 ✅ (rotcha/infohot/techpawz)
- **이미지 파이프라인:** 전체 종료
- **`mc` 전역 명령:** ✅ `/Users/twinssn/.kaggle-env/bin/mc`

## Active Context

- GitHub repo: https://github.com/hugh79757-cmyk/mc
- Local path: /Users/twinssn/projects2/mc
- Runtime: opencode
- 5000 path: /Users/twinssn/Projects/5000
- Hugo paths: /Users/twinssn/Projects/{rotcha-blog, issue-techpawz-hugo, techpawz-hugo}
  - (Legacy: informationhot-hugo는 체인 슬롯에서 제거됨)
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

## Phase 15 Deliverables

| Wave | Task | Status |
|------|------|--------|
| W0 | 현황 스냅샷 + baseline | ✅ |
| W1 | issue.techpawz-hugo 사이트 준비 | ✅ |
| W2 | 체인 코드 교체 (config/prompts/core) | ✅ |
| W3 | 애드센스 Publisher ID 통일 (모두 ca-pub-8772) | ✅ |
| W4 | 최종 검증 (Hugo 빌드 3/3 + dry-run + pytest 231/231) + 커밋 | ✅ |

## Phase 17 Deliverables

| Task | Status |
|------|--------|
| CTA 시나리오 표 | ✅ |
| 내부이동 CTA / 최종행동 CTA 분리 | ✅ |
| 플레이스홀더 명칭 정리 | ✅ |
| 프롬프트 릭 방지 설계 | ✅ |
| mc 주입 구조 설계 | ✅ |
| 설계안 저장 | ✅ |
| 대표님 검토 및 확정 | ⏳ 대기 |

## Phase 20 Deliverables

| 수정 | 상태 | 근거 |
|------|------|------|
| `--search` global default (True) | [검증됨] | `chain_publisher.py` use_context = not args.no_search + `chain_drafter.py` default True. `--help` text updated. |
| STOCK & AUTOMOTIVE GROUNDING block | [검증됨] | 5 rules inserted after TRAVEL GROUNDING in draft_user. YAML parse OK. |
| Test fix: issue-techpawz bucket | [검증됨] | `test_r2_uploader.py` expectation updated: hotissue-images → issue-techpawz. |
| pytest | [검증됨] | 246/246 passed. |
| **Stock 검증** | [검증됨] 발행 가능 ✅ | Chain 113: `₩372`, `₩1,695`, `2.51%`, `5/29`, `11/19` 모두 Naver 검색 자료(Investing.com)에서 직접 가져옴. 가짜출처 0건. |
| **Automotive 검증** | [검증됨] 조건부 발행 가능 🟡 | Chain 112: 가짜출처 0건 ✅. `예상/추정` 면책 표현 충실 ✅. 단, 검색 자료가 제품 스펙을 반환하지 못함 → AI가 모든 스펙 지어냄. search_retriever 개선 과제로 이월. |
| **Travel S2 구체성 검증** | [검증됨] 개선 확인 ✅ | Chain 114: `--search` 적용 후 실제 펜션명 4개(`토담`, `스테이쉼온`, `피플애견`, `더스테이하루`) 등장. 구체적 거리/리뷰 수/특징 포함. 예약정보 허언 0건. |

## Next Action

1. **[단기] 발행 재개** — stock/automotive/travel 모두 조건 충족. 대표님 판정에 따라 Chain 112~114 발행.
2. **[즉시 해소 가능] Shortcode git add** — rotcha + techpawz `layouts/shortcodes/` git 추적 (2개 repo, 3개 파일, 추정 1분)
3. **Phase 17 대표님 검토** — CTA-SCENARIO.md 확정 후 `config/prompts.yaml` `cta_phrases` 코드 착수
4. **발행 파이프라인 CTA 텍스트 필터** — Phase 17 확정 후 `get_cta_by_category()`, `keyword_categories.cta_phrases` 주입, 플레이스홀더 치환 시스템
5. **search_retriever 개선** — automotive 전용 검색 템플릿 or Naver API 키워드 조합 최적화 (현재 기업 일반 정보만 반환)
6. **릭 방어 패턴 상수 통합** — `config/leak_defense.yaml` (또는 독립 모듈)로 방어 로직 집약
7. **P2 설계** — 글자수 측정 기준 + travel 비교 대상 사이트 구체화
8. **Persona 어조 설계** — site/depth별 tone 설정
9. **Phase 14.1** — cron/launchd 스케줄링, dashboard CLI, `audit_chain.py` 통합 (별도 milestone, 공수 큼)
