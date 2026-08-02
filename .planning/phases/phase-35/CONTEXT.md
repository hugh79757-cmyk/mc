# CONTEXT.md — Phase 35: 실발행 재검증 + use_context 효과 실측 + 카테고리 불일치 해결 + 중간 CTA 카드 구현

## 문제 요약

Phase 33/34에서 완료된 개선 사항들을 실발행 환경에서 재검증하고, Phase 34에서 발견된 `use_context=True` 시 릭 0 현상의 원인을 실측으로 검증하며, 카테고리 분류 불일치와 중간 CTA 카드 미구현 이슈를 해결한다.

**핵심 문제**:
1. **Chain #378, #405 실발행 재검증 필요** — Phase 33/34 수정 사항이 실제 발행 환경에서 검증되지 않음
2. **use_context=True 시 릭 0 현상** — 검색 컨텍스트가 릭 방지에 효과적이지만, 실측 데이터(실제 모델 호출) 없음
3. **카테고리 불일치** — `classify_keyword('뉴발란스 740')` → `etc` 반환 vs AI 작성 `category_guess='쇼핑/소비'` 저장
4. **중간 CTA 카드 미구현** — Phase 17 설계(dual_info 타입) 미구현, hub URL 플레이스홀더 치환 파이프라인 부재

## 진단에서 드러난 4대 개선 과제

| # | 과제 | 현재 상태 | 목표 |
|---|------|-----------|------|
| **P0** | 실발행 재검증 | Phase 33/34 PLAN 승인 대기 중 | Chain #378/#405 재발행 성공 확인 |
| **P1** | use_context 효과 실측 | 모킹 테스트만 존재, 실측 없음 | Step 2/3 실제 모델로 5회씩 생성 → 8종 시그니처 0건 검증 |
| **P1** | 카테고리 불일치 | `classify_keyword('뉴발란스 740')` → `etc` vs AI `category_guess='쇼핑/소비'` | `shopping_brand` 패턴에 브랜드 추가 + `etc` fallback 시 AI 값 존중 |
| **P2** | 중간 CTA 카드 미구현 | Phase 17 설계만 존재, 미구현 | Step 1/2 중간 카드(dual_info) + hub URL 치환 파이프라인 구현 |

## 핵심 코드 위치 (read로 갱신한 최신 라인)

| 기능 | 파일 | 라인 |
|------|------|------|
| `classify_keyword()` | `mc_paths.py` | 98-137 |
| `resolve_chain_type()` | `mc_paths.py` | 140-152 |
| `draft_single_post()` | `chain_drafter.py` | 232-357 |
| 검색 컨텍스트 주입 | `chain_drafter.py` | 296-324 |
| `retrieve_context_for_post()` | `search_retriever.py` | 117-196 |
| `strip_leaks()` | `mc/leak_defense.py` | 74-127 |
| 문단 단위 reasoning leak | `mc/leak_defense.py` | 181-314 |
| `inject_cards_into_draft()` | `chain_card_injector.py` | 452-578 |
| `get_cta()` | `mc/cta.py` | 36-96 |
| `detect_ai_cta()` | `mc/cta.py` | 130-158 |
| `keyword_categories` 패턴 | `config/prompts.yaml` | 159-561 |
| `keyword_mapping` | `config/chain_config.yaml` | 83-94 |
| CTA 템플릿 | `config/cta_templates.yaml` | 1-62 |
| `retrieve_context_for_post()` angle 매핑 | `chain_drafter.py` | 296-324 |
| `draft_single_post()` force_context 추가 필요 | `chain_drafter.py` | 232-245 |
| `inject_cards_into_draft()` 중간 카드 로직 | `chain_card_injector.py` | 561-573 |
| `get_cta()` dual_info 반환 | `mc/cta.py` | 76-79 |

## 현재 테스트 기준선

- `pytest --co -q`: **851 tests collected** (836 + 신규 15)
- Phase 34 T6: `test_t5_t6_regression.py::TestT6ManifestationRate` — 모킹 기반, 실측 필요
- Phase 34 T6: `test_use_context_true_manifestation` — 모킹 기반, 실측 필요

## 개선 방향 (합의됨 — P0→P1→P2 순서)

### P0. 실발행 재검증 (선행 필수)
- Chain #378: `python chain_publisher.py --chain-id 378 --publish` → 3스텝 모두 성공 확인
- Chain #405: 라이브 URL 확인으로 8종 시그니처 0건 확인
- Phase 33/34 PLAN 완료 및 머지 후 실행

### P1. use_context=True 실측 검증 (정책 확정용)
- Step 2/3 각 키워드 5회 생성 × 2조건(use_context=True/False) = 30회 생성
- `use_context=True` 시 8종 시그니처 0건, `False` 시 발현률 측정
- "리뷰형 step 검색 컨텍스트 우선" 정책 확정: Step 2/3 강제, Step 1 선택

### P1. 카테고리 불일치 해결
- **방안 A**: `prompts.yaml` `shopping_brand` 패턴에 브랜드명/모델코드 추가
- **방안 C**: `chain_drafter.py` `etc` fallback 시 AI `category_guess` 존중 로직 추가
- 병행 권장

### P2. 중간 CTA 카드 구현
- `chain_card_injector.py` 중간 카드 로직에 `dual_info` 타입 통합
- `CardInjector._get_hub_url(chain_id)` 헬퍼 추가
- `{{HUB_LINK}}` 플레이스홀더 치환 파이프라인 연결 (발행 시점 치환)

## 검증 계획

1. **P0 완료 후**: Chain #378 `python chain_publisher.py --chain-id 378 --publish` 3스텝 성공, Chain #405 라이브 8종 시그니처 0건 확인
2. **P1 완료 후**: `test_t5_t6_regression.py` 확장 — 실제 모델로 Step 2/3 각 5회 × 2조건 비교, 카테고리 분류 테스트, 중간 CTA 카드 삽입 검증 테스트 추가
3. **P2 완료 후**: 통합 테스트 — Step 1/2/3 각 H2≥3일 때 카드 2개(하단+중간) 삽입, 플레이스홀더 잔존 0건, 발행 후 8종 시그니처 0건
4. **전체**: pytest 851 → 851+ 유지, 회귀 0건

## 수정 범위 제약

- Phase 33/34 완료 후 Phase 35 착수 (의존성 있음)
- `config/prompts.yaml.bak` 오염 — git으로 롤백, .gitignore로 제외
- 발행·배포·DB 데이터 쓰기 금지 (검증 단계 제외)
- 실행 방법 불명확 시 "확인 필요"로 명시

## 상위 Phase 의존성

| Phase | 상태 | 비고 |
|-------|------|------|
| 33 | 승인 대기 | JSON 메타데이터 파싱 재설계 완료, PLAN 승인 대기 |
| 34 | 승인 대기 | C/A/B 3겹 방어 완료, T6 실측 검증 대기 |
| 35 | **계획 수립 중** | 33/34 완료 후 착수 |
