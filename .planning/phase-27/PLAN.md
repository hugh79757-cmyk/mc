# PLAN.md — Phase 27: 카테고리별 Draft 품질 검증

**Phase:** 27
**Owner:** 검증 에이전트
**Mode:** validation
**Status:** ✅ Complete
**Estimated effort:** 2~3시간 (AI 호출 비용 포함)

---

## Objective

6개 카테고리 × 2개 시드 = 12개 derive+draft를 실행하여, 카테고리 체계가 실제로 동작하는지 검증한다.

## Scope

### In Scope
- 6개 카테고리 derive 실행 (각 2개 시드)
- 각 derive 결과의 분류/방향/프롬프트/흐름 검증
- 12개 draft 생성 + H2 구조/글자수/연결 검증
- 기존 medicine(#230)/golf_course(#231) 검증 결과와 교차 비교

### Out of Scope
- 이미지 생성/업로드
- 발행/deploy
- 카드 주입
- 코드 수정 (버그 발견 시 별도 이슈로 이월)

---

## Task Breakdown

### Wave 1: Derive 검증 (6개 카테고리 × 2 시드)

| Task | 카테고리 | 시드 1 | 시드 2 | 검증 항목 |
|------|----------|--------|--------|-----------|
| 1-1 | stock | 삼성전자 주가 | ETF 투자 전략 | 분류, 방향(depth), 프롬프트, 흐름 |
| 1-2 | real_estate | 청주 아파트 시세 | 수원 오피스텔 분양 | 분류, 방향(depth), 프롬프트, 흐름 |
| 1-3 | travel | 제주도 여행 코스 | 강릉 여행 숙소 | 분류, 방향(lateral), 프롬프트, 흐름 |
| 1-4 | shopping_brand | 골프웨어 브랜드 추천 | 온라인 쇼핑몰 순위 | 분류, 방향(lateral), 프롬프트, 흐름 |
| 1-5 | customer_service | 삼성전자서비스 고객센터 | 카카오 고객센터 전화번호 | 분류, 방향(lateral), 프롬프트, 흐름 |
| 1-6 | golf_course | 남서울CC 예약 | 용인CC 라운딩 | 분류, 방향(lateral), 프롬프트, 흐름 |

**산출물:** 12개 chain이 DB에 저장됨. chain_id 목록 기록.

### Wave 2: Draft 생성 + 분석

| Task | 내용 |
|------|------|
| 2-1 | 12개 chain 각각 `chain_drafter.py`로 draft 생성 |
| 2-2 | `/tmp/analyze_drafts.py`로 각 chain_id 분석 |
| 2-3 | 분석 결과 테이블 작성 (H2 수, 글자수, 연결 신호) |

### Wave 3: 품질 평가 + 리포트

| Task | 내용 |
|------|------|
| 3-1 | 검증 기준별 통과/실패 판정 |
| 3-2 | 카테고리별 비교 테이블 작성 |
| 3-3 | 발견된 이슈 목록 + 심각도 분류 |
| 3-4 | VERIFICATION.md 작성 |

---

## 검증 기준 상세

### Derive 검증 체크리스트

- [x] `classify_keyword(seed)` → 올바른 카테고리 반환 (11/12 — "수원 오피스텔 분양" misclassified)
- [x] `resolve_chain_type(seed)` → keyword_mapping에 정의된 방향 반환 (11/12 — travel로 misresolve)
- [x] `derive_user_lateral_{category}` 프롬프트 선택 확인 (12/12 — category-specific 프롬프트 사용)
- [x] s1→s2→s3 흐름이 카테고리 설계와 일치 (12/12)
- [x] bridge_logic이 자연스러운 다음 글 예고 포함 (12/12)

### Draft 검증 체크리스트

- [x] H2 구조: step_sections대로 생성 (36/36 — 오차 0)
- [x] 글자수: char_count 범위 내 (5/36 — config 범위 초과, system prompt 2500~3500자 준수)
- [x] s1→s2 연결: s1 마지막에 s2 주제 예고 (12/12 step1→2, 12/12 step2→3)
- [x] s2→s3 연결: s2 마지막에 s3 주제 예고 (12/12)
- [x] s3 마무리: 공식/예약/신청 창구로 배출 (11/12)
- [x] 프롬프트 릭: `_strip_prompt_leak()` 통과 (36/36)

---

## Risk

| 리스크 | 영향 | 대응 |
|--------|------|------|
| AI 응답 변동성 (temperature 0.85) | 같은 시드라도 결과가 다를 수 있음 | 2개 시드로 교차 검증 |
| 주식/부동산은 depth 방향 | lateral 프롬프트와 다른 구조 | depth 방향 프롬프트가 올바르게 선택되는지 확인 |
| API 비용 | 12개 derive + 12개 draft = 24회 AI 호출 | 불필요한 재시도 최소화 |

---

## Success Criteria

- 6개 카테고리 전부 derive 성공 (chain_id 생성)
- 12개 draft 전부 생성 성공
- H2 구조 검증: 10/12 이상 통과 (±1 허용)
- 연결 검증: 10/12 이상 s1→s2→s3 예고 포함
- depth2 배출: 10/12 이상 s3에서 공식/예약 창구 포함
- 프롬프트 릭: 12/12 통과
