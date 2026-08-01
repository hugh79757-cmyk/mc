# Roadmap: mc (Manual Chain)

**Last updated:** 2026-08-01

## 완료된 Phase

| Phase | Focus | Status |
|-------|-------|--------|
| 1 | Foundation & Config | ✅ Complete |
| 2 | AI Content Generation | ✅ Complete |
| 3 | Image, Publishing & CLI | ✅ Complete |
| 4 | Loop Chain Direction | 🔴 Deprecated (Phase 6 대체) |
| 5 | mde2 Architecture Rewrite | ✅ Complete |
| 6 | Loop Funnel (Blowfish Hub + 2-CTA) | ✅ Complete |
| 7 | Search-Augmented Drafting (Naver API) | ✅ Complete |
| 8 | Chart Generation (pillow_chart.py) | ✅ Complete |
| 9 | Publish Quality Fix | ✅ Complete |
| 10 | Phase 9 Aftermath — 회귀 방지 | ✅ Complete |
| 11 | HTML 릭 + 광고 겹침 수정 | ✅ Complete |
| 12 | mc R2 업로더 분리 | ✅ Complete |
| 13 | 콘텐츠 고도화 (markdown cleanup + contextual image) | ✅ Complete |
| **14** | **CLI `mc <keyword>` + R2 이미지 수정** | **✅ Complete** |
| **32** | **연도 오류 방지 시스템 (year_guard)** | **✅ Complete** |

## Phase 14 상세

| 작업 | 상태 | 비고 |
|------|------|------|
| W1: CLI argparse + `_run_full()` + 25 tests | ✅ | cli/mc.py |
| W2: `_resume_chain()` + 4 tests | ✅ | DB state detection |
| W3: `_run_background()` + 6 tests | ✅ | subprocess + flush logging |
| W4: `pyproject.toml` + `pip install -e .` | ✅ | which mc, mc --help |
| P1: `_ensure_frontmatter()` 정식 구현 | ✅ | patch 제거, 6 tests |
| P2: 고아 content_image_path 15/15 | ✅ | (d)3건 + (b)12건 |
| R2: published_md 컬럼 + card injection 보존 | ✅ | 3 tests |
| R2: techpawz R2 버킷 분기 | ✅ | hotissue→techpawz-images, 5 tests |

## 이미지 파이프라인 종료

| 이슈 | 수정 | 상태 |
|------|------|------|
| Phase 13 contextual image | search_providers + prompt_builder | ✅ |
| P2 고아 content_image_path | (d)3건 DB경로 + (b)12건 Pollinations | ✅ 15/15 |
| R2 card injection URL 상실 | published_md 컬럼 + inject 갱신 | ✅ |
| techpawz R2 버킷 불일치 | R2_SITE_BUCKETS 분기 | ✅ |

## 잔존 이월

| 작업 | 우선순위 | 비고 |
|------|---------|------|
| Phase 14.1: cron/launchd + dashboard + audit | 별도 milestone | 공수 큼, 무인 스케줄 자동발행 |
| (a) 43건 고아 content_image_path | 별도 milestone | 신규 발행 W6 게이트로 차단 |
| slug 고유화 + 비의도 체인 자동 감지 | P2 | |
| P3 Blowfish CSS 복구 | P3 | 라이브 3/3 기능 정상, CSS 미세 복구 |

| **15** | **informationhot → issue.techpawz 슬롯 교체** | **✅ Complete** |

## Phase 15 상세

| 작업 | 상태 | 비고 |
|------|------|------|
| Wave-0 | 현황 스냅샷 + baseline | ✅ |
| Wave-1 | issue.techpawz-hugo 사이트 준비 | ✅ |
| Wave-2 | 체인 코드 교체 | ✅ |
| Wave-3 | 애드센스 Publisher ID 통일 | ✅ |
| Wave-4 | 최종 검증 + 커밋 | ✅ |

| **16** | **실전 검증 파이프라인** | **✅ Complete** |

## Phase 16 상세

| 작업 | 상태 | 비고 |
|------|------|------|
| STEP-1 | dry-run 실행 및 초안 품질 검증 | ✅ |
| STEP-2 | 이미지/썸네일 생성 검증 | ✅ |
| STEP-3 | 카드 삽입 검증 | ✅ |
| STEP-4 | 글쓰기 프롬프트 품질 검증 | ✅ |
| STEP-5 | 실발행 전 종합 판단 | ✅ |

| **17** | **CTA 시나리오 설계** | **✅ 설계 완료** |

## Phase 17 상세

| 작업 | 상태 | 비고 |
|------|------|------|
| CTA 시나리오 표 | ✅ | 5개 카테고리 설계 |
| 내부이동 / 최종행동 CTA 분리 | ✅ | 플레이스홀더 {{ENTRY_LINK}}/{{FUNNEL_LINK}} |
| 주입 위치 설계 | ✅ | Step별 카드/본문 규칙 |
| 프롬프트 릭 방지 설계 | ✅ | 주입 지시 + 출력 검증 |
| 대표님 검토 및 코드 착수 | ⏳ 대기 | |

## Phase 26: 코드베이스 리팩터링

| 작업 | 상태 | 비고 |
|------|------|------|
| 코드베이스 리팩터링 | 📝 계획됨 | REFACTORING_PLAN.md 참조 |

## 현황

- **pytest:** 309/309 ✅
- **라이브:** 3/3 R2 200 ✅ (rotcha/infohot/techpawz)
- **카테고리:** 10종 (travel/real_estate/automotive/stock/customer_service/gov_finance/shopping_brand/golf_course/medicine/etc)
- **Phase 14:** complete

## 완료된 Phase (최근)

| Phase | Focus | Status |
|-------|-------|--------|
| 27 | 카테고리별 Draft 품질 검증 | ✅ Complete |
| 28 | 상품(product) 카테고리 추가 | ✅ Complete |

### Phase 28 상세

**Goal:** 갤럭시/아이폰/에어팟 등 전자기기 키워드가 product 카테고리로 분류되어 상품 특화 콘텐츠(스펙 비교, 구매 가이드) 생성

**Plans:**
- [x] 28-01-PLAN.md — config 변경 (prompts.yaml + chain_config.yaml) + 테스트 ✅

**Results:**
- product keyword_categories block (18 patterns, priority=50)
- derive_user_lateral_product prompt
- product: lateral mapping in chain_config.yaml
- conftest.py + test_chain_deriver.py updated (6 new tests)
- pytest: 315/315 ✅

## 향후 Phase

| Phase | Focus | Status |
|-------|-------|--------|
| 29 | 블로그 형식/외형 검증 | ✅ Complete |
| 30 | audit_format.py gap closure (3건 미이행 해소) | 📝 Planned |

### Phase 29 상세

**Goal:** 카테고리 11종 체계에서 생성되는 블로그 포스트의 형식/외형이 설계대로 동작하는지 자동 검증

**Plans:**
- [x] 29-01-PLAN.md — audit/audit_format.py (10개 검증 체크) + 39 tests + 베이스라인 리포트 ✅

**Results:**
- audit/audit_format.py: 10 checks (card_count, card_placement, cross_link_url, h2_structure, frontmatter, hugo_html, db_consistency, card_type, external_link_pattern, chain_card_shortcode)
- test_audit_format.py: 39 tests (all pass)
- Baseline: 8/10 checks pass (2 failures from test post #488 — expected)
- pytest: 354/354 ✅

### Phase 30 계획

**Goal:** Phase 29 self-audit에서 발견한 계약 미이행 3건 해소 (check_hugo_build, check_html_render, check_live_access)

**Plans:**
- [ ] 30-01-PLAN.md — 3개 함수 추가 + 테스트 + CLI 통합
