# State: mc (Manual Chain)

**Last updated:** 2026-07-22

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-18)

**Core value:** One random keyword → 3 interconnected blog posts on 3 different domains, each going deeper than the last, with images and cross-links — fully automated.
**Current focus:** Phase 12 준비 — 다음 요구사항 분석

## Phase Status

| Phase | Status | Plans | Progress |
|-------|--------|-------|----------|
| 1 — Foundation & Config | ✅ Complete | config/chain_config.yaml, config/prompts.yaml, chain_db.py, mc_paths.py, chain_deriver.py, chain_publisher.py | 6/6 files |
| 2 — AI Content Generation | ✅ Complete | chain_drafter.py, image/, pipeline --dry-run/--draft/--image | 8/8 tasks verified |
| 3 — Image, Publishing & CLI | ✅ Complete | 8 tasks across 3 waves | Wave 1/2/3 ✅ |
| 4 — Loop Chain Direction | ✅ Complete | loop 방향 라우팅 + 2-CTA 주입 | Committed b9a6f53 |
| 5 — mde2 Architecture Rewrite | ✅ Complete | chain_publisher_core.py 전면 재작성 (7 fixes) | 3 Waves, 11 Tasks |
| 6 — Loop Funnel | ✅ Complete | Hub page + dual-CTA spoke injection | Phase 6 |
| 7 — Image Pipeline Integration | ✅ Complete | Thumbnail + content image pipeline | 7 tasks |
| 8 — Chart Generation | ✅ Complete | pillow_chart.py + GPT chart recognition | 7 tasks, 3 waves |
| 9 — Publish Quality Fix | ✅ Complete | 프롬프트 릭·이미지 미삽입·썸네일 가독성 | 8 tasks, 4 waves |
| 10 — Phase 9 Aftermath | ✅ Complete | 회귀 방지 + 잔여 이슈 | 5 tasks |
| 11 — HTML 릭 + 광고 겹침 수정 | ✅ Complete | _extract_clean_body 필터링·프롬프트·검증·CSS·card_injector | 10 tasks, 5 waves |
| 12 — 다음 요구사항 | ○ Pending | 미구현 요구사항 분석 | TBD |

## Active Context

- GitHub repo: https://github.com/hugh79757-cmyk/mc
- Local path: /Users/twinssn/projects2/mc
- Runtime: opencode
- Git: initialized with README.md pushed
- 5000 path: /Users/twinssn/Projects/5000 (.venv at /Users/twinssn/Projects/5000/.venv)
- HUGO paths: /Users/twinssn/Projects/{rotcha-blog, informationhot-hugo, techpawz-hugo}

## Phase 8 Deliverables

| Wave | Task | File | Status |
|------|------|------|--------|
| W1 | 8-1 DB 확장 | `chain_db.py` — chart_type/chart_data/image_reason 컬럼 + update_chart() | ✅ |
| W1 | 8-2 차트 모듈 | `pillow_chart.py` — bar/timeline/comparison 렌더러 + dispatcher | ✅ |
| W1 | 8-6 Config | `config/chain_config.yaml` — chart: 섹션 추가 | ✅ |
| W1 | 8-7 Preflight | `chain_publisher.py` — 차트 폰트 사전 확인 | ✅ |
| W2 | 8-3 Drafter | `chain_drafter.py` — GPT chart 인식 + (draft_md, meta) 반환 | ✅ |
| W2 | 8-4 Injector | `image/injector.py` — <!--todo:chart--> 마커 지원 | ✅ |
| W3 | 8-5 Publisher | `chain_publisher_core.py` — chart 생성 분기 + font resolver | ✅ |

## Phase 8 Key Decisions

- GPT returns structured JSON (chart_type + chart_data), code renders charts
- `<!--todo:chart-->` marker is position-only, data lives in DB
- Font missing → exception → fallback to photo (not warning)
- `ensure_ascii=False` for Korean JSON in chart_data
- Idempotent: content_image_path check skips regeneration

## Phase 11 Deliverables

| Wave | Task | File | Status |
|------|------|------|--------|
| W1 | 11-1 re.match→re.search | `chain_publisher_core.py:112` — HTML_TAG_RE.search() | ✅ Committed ee844b2 |
| W1 | 11-2 태그 목록 확대 | `chain_publisher_core.py` — 8개 태그 필터링 | ✅ Committed ab87a2c |
| W2 | 11-3 prompts.yaml HTML 금지 | `config/prompts.yaml:248-259` — HTML 전면 금지 규칙 | ✅ Committed ee844b2 |
| W4 | 11-4 HTML 태그 검증 추가 | `chain_publisher_core.py:179` — WARNING 레벨 | ✅ Committed 3ef912c |
| W4 | 11-5 정규식 통일 | `chain_publisher_core.py:37` — HTML_TAG_RE 상수 | ✅ Committed f0b018f |
| W5 | 11-6 rotcha CSS broadened | `rotcha-blog/assets/css/extended/custom.css:58-61` | ✅ Committed ee844b2 |
| W5 | 11-7 3개 사이트 전파 | informationhot/techpawz custom.css 업데이트 | ✅ |
| W3 | 11-8~10 shortcode 전환 | chain_card_injector.py — shortcode 이스케이프 | ✅ Committed a72a89b |

## Phase 11 Key Decisions

- `HTML_TAG_RE` constant unified across `_extract_clean_body()` and `_verify_before_deploy()`
- `_verify_before_deploy()` HTML tag check runs at WARNING level until W3 card_injector fully migrated
- Blowfish Hugo shortcode requires `{{{{< ... >}}}}` escaping in markdown source
- All 3 Hugo sites have shortcode templates (chain-card, chain-official-card, dual-cta)

## Next Action

1. Hugo 빌드 + 배포: 3개 사이트 모두 `hugo --gc --minify` → `wrangler pages deploy`
2. Phase 12 요구사항 분석: ROADMAP.md의 PL-v2-01 (Parallel Chains), PL-v2-02 (Auto-approval), PL-v2-03 (Scheduled Execution)
