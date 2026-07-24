# CONTEXT.md — Phase 16

**Phase:** 16  
**Created:** 2026-07-23  
**Milestone:** 실전 검증 파이프라인  
**Mode:** wave-based execution

## Objective

키워드 "하이바이풀빌라"로 실제 발행을 돌리면서 체인 시스템의 9개 항목(슬롯/역할/MD문법/프롬프트릭/썸네일/R2/카드/외부링크/글품질)을 전수 검증.
dry-run 먼저, 실발행은 대표님 승인 후 진행.

## 검증 범위

| STEP | 내용 |
|------|------|
| STEP-1 | dry-run 실행 및 초안 품질 검증 |
| STEP-2 | 이미지/썸네일 생성 검증 |
| STEP-3 | 카드 삽입 검증 |
| STEP-4 | 글쓰기 프롬프트 품질 검증 |
| STEP-5 | 실발행 전 종합 판단 |

## Constraints

- dry-run 우선, 실발행은 승인 후
- 프롬프트 내용이 본문에 노출되는 프롬프트 릭 절대 금지
- Hugo 빌드 깨지면 즉시 중단
- 배포는 Wave-4와 별도 승인

## Inputs

- RESEARCH.md (Phase 16)
- config/prompts.yaml (draft_system / draft_user)
- chain_publisher_core.py (generate_chain_images, publish)
- chain_card_injector.py (inject_cards, find_external_links)
- chain DB: `/Users/twinssn/Projects/5000/data/mc_chains.db`

## 키워드

- **테스트 키워드:** 하이바이풀빌라
- **예상 분류:** travel → lateral (숙소/여행)

## 잔존 위험 — Depth/Swallow 방향 category 분기 미완

### 발견 (Phase 16 실행 중 확인)
- 모든 `derive_user_*` 프롬프트(depth/swallow/lateral)가 category 불문하고 동일한 Step3 방향성 정의 사용
- Phase 16에서는 Lateral만 수정 (travel이 타는 경로)
- Depth/Swallow도 동일한 angle 하드코딩 문제를 갖고 있으나:
  - 어떤 카테고리가 Depth/Swallow 경로를 타는지 실데이터 검증 부족
  - 당면 문제(하이바이풀빌라 travel → lateral)는 Lateral 수정으로 해결

### 재발 조건
1. `keyword_categories`에 새로운 카테고리 추가 시 `derive_user_*` 프롬프트도 함께 수정해야 함
2. travel이 아닌 카테고리(real_estate/automotive/stock)가 Depth/Swallow 경로를 탈 경우, Step3가 비즈니스/산업 프레임으로 붕괴 위험 동일
3. Depth/Swallow 방향의 category별 angle 재정의가 없으면 Phase 16 이전 상태의 동일한 붕괴가 다른 경로에서 재발

### 권고: 후속 Phase 필수 과제
- **Phase 17+**: Depth/Swallow `derive_user_*` 프롬프트를 category별로 분기
  - depth: 모든 category에 대해 "점점 더 깊은 전환/실행" 방향으로 통일 (현재 "기초→분석→전문" 프레임은 유지하되 category별 내용 차별화)
  - swallow: shopping 전용이었으나 shopping 카테고리가 사라짐. "역방향 확장"의 정의 자체를 재검토 필요
- 실데이터 기반 검증: 어떤 category가 Depth/Swallow를 타는지 DB 체인 데이터로 통계 수집 후 정의
