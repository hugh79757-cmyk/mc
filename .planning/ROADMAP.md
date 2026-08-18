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

---

# 새 마일스톤: 정보가 3-블로그 체인 복제 (M2)

**등록:** 2026-08-02
**근거:** mc 복제 방식 타당성 조사 (읽기 전용) 결과 — 정보가.kr / kuta.informationhot.kr / 5.informationhot.kr 3개 사이트에 mc 체인(depth 0/1/2)을 독립 레포로 복제해 3-체인 발행을 가능하게 함.
**종료 상태 (DoD):** 복제 레포 생성 + 필수 분리(DB/shared/R2) + 정보가 3사이트 Hugo 셋업 + chain_config 교체 + dry-run 발행 검증. 실발행은 검증 통과 후 대표 승인 시 별도 진행.
**대표 확정 결정 (2026-08-02):**
- shared 의존성: **vendoring 복사** (ai_writer.py + env_loader.py + models.yaml, mc_paths.py PATH_5000 제거)
- 카드 색상: **체인 카드만 파랑** (#2563eb 계열 shortcode 신규, html_renderer.py external 카드 구조 유지)
- R2 prefix/도메인 네이밍은 셋업 중 결정 (미확정 해소)

## Phase 37: 복제 레포 생성 + 필수 분리

| 작업 | 상태 | 비고 |
|------|------|------|
| git clone + 새 원격 교체 | ○ | 기존 origin(mc.git)과 분리, 새 GitHub 레포 |
| `.env` 재생성 | ○ | git 미추적 → 수동 복사 (R2/KREA 키) |
| **DB 분리** | ○ | chain_config.yaml `db_path` → 복제 레포 내 (5000/data/mc_chains.db 공유 해제) |
| **shared vendoring** | ○ | ai_writer.py + env_loader.py + __init__.py + config/models.yaml 복사, PATH_5000 제거 |
| R2 매핑 키 추가 | ○ | informationhot / 5.informationhot 엔트리 (kuta는 기존 존재) |

## Phase 38: 정보가 3사이트 Hugo 인프라 셋업

| 작업 | 상태 | 비고 |
|------|------|------|
| shortcode 3종 (파랑) | ○ | chain-card / chain-official-card / dual-cta — #2563eb 계열로 신규 생성 (현재 3사이트 전부 부재) |
| 5.informationhot-hugo baseURL | ○ | `https://example.org/` 플레이스홀더 → `https://5.informationhot.kr` |
| ads.txt 추가 | ○ | kuta / 5 사이트 부재 |
| CF Pages 배포 확인 | ○ | 프로젝트 3개 존재 확인됨 (informationhot-hugo/kuta-hugo/5-informationhot) |

## Phase 39: chain_config 교체 + 카드 색상 분기

| 작업 | 상태 | 비고 |
|------|------|------|
| sites 정의 교체 | ○ | informationhot / kuta / 5_informationhot Hugo 3개로 |
| chain_blogs / chain_blog_mapping | ○ | depth 0/1/2 → 정보가 3개 순서 |
| 기존 사이트 정의 정리 | ○ | rotcha/issue.techpawz/techpawz/2_techpawz/65_informationhot 처리 결정 |
| 카드 색상 파랑 적용 | ○ | shortcode 파랑 + 테스트 |

## Phase 40: dry-run 발행 검증

| 작업 | 상태 | 비고 |
|------|------|------|
| e2e dry-run 3종 통과 | ○ | e2e_derive_dryrun / e2e_draft_only / e2e_publish_dryrun |
| pytest green 유지 | ○ | 기존 851건 + 신규 테스트 |
| DoD 체크리스트 | ○ | 실발행은 미포함 (별도 승인 게이트) |

---

## Milestone 3: 9-Point Quality Pipeline

Goal: 발행 전 자동 검증으로 3개 블로그 글 품질 9/10 이상 보장
Success Criteria: 테스트 키워드 3개 × 3블로그 = 9편 모두 자동 게이트 통과 + 수동 평가 9.0+

### Phase 41 — Output Contract Definition
Goal: 블로그별 산출물 계약서 YAML 정의 + 로더 + 기본 검증 함수
Requirements: QG-01, QG-02
Status: Not Started

### Phase 42 — Title-Body Contract Checker
Goal: 제목이 약속한 토픽이 본문에 실질적으로 다뤄졌는지 자동 검증
Requirements: QG-03
Status: Not Started

### Phase 43 — Pre-Publish Research Step
Goal: derive 후 draft 전에 웹 리서치를 삽입하여 팩트시트 기반 글 생성
Requirements: QG-04, QG-05
Status: ✅ Complete — quality/pre_researcher.py (Factsheet/Fact + NaverSearchClient + graceful degradation + prompt injection). 16 tests.

### Phase 44 — Factuality Filter
Goal: 출처 없는 수치·후기·통계 문장을 발행 전 자동 차단
Requirements: QG-05, QG-06
Status: Not Started

### Phase 45 — Cross-Blog Dedup & Role Enforcer
Goal: 동일 chain 3편의 문장 중복 해소 + 블로그별 역할 필수 요소 강제
Requirements: QG-07, QG-08
Status: Not Started

### Phase 46 — HTML Render Dedup Check
Goal: Hugo 빌드 후 최종 HTML에서 제목·CTA·문단 중복 자동 탐지
Requirements: QG-09
Status: Not Started

### Phase 47 — Quality Scorer & Gate Integration
Goal: 가중합 스코어링 + 7.0 미만 차단 / 9.0+ 자동 승인 게이트 통합
Requirements: QG-10, QG-11
Status: Not Started

### Execution Order (Wave Structure)

```
Wave 1 (병렬):  Phase 41 + Phase 46
                 ↓
Wave 2 (병렬):  Phase 42 + Phase 43 + Phase 45  (모두 41에 의존)
                 ↓
Wave 3:         Phase 44  (43에 의존)
                 ↓
Wave 4:         Phase 47  (41~46 전부 의존)
```

Phase 46(HTML 검사)은 다른 quality 모듈에 의존하지 않으므로 Wave 1에서 41과 병렬 실행 가능.
