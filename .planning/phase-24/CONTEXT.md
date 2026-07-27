# CONTEXT.md — Phase 24: 콘텐츠 차별화 + 운영 실증

**Phase:** 24  
**Created:** 2026-07-26  
**Milestone:** 사이트별 persona/어조 차별화 + 실제 키워드 10개 자동 발행으로 시스템 안정성 실증  
**Mode:** execute (코드 착수)

---

## Objective

mc가 생성하는 콘텐츠에 사이트별(rotcha/issue.techpawz/techpawz) 어조와 전문성 차이를 부여하고, 실제 키워드 10개를 자동 발행하여 시스템 안정성을 실증한다.

---

## Background

Phase 22에서 품질 게이트(글자수 검증 warning-only, CTA 코드화, 릭 방어 통합, SEO 메타 보강)가 추가되었으나:
- persona/어조 차별화 미적용 (단일 draft_system 프롬프트로 3개 사이트 공용)
- Travel 비교 대상 사이트 미구체화 (Step 2 비교/탐색형이 어떤 사이트와 비교할지 없음)
- Automotive 검색 유효하지 않음 (Phase 20 실측: Naver API가 스펙/가격/연비 미반환)
- 품질 게이트가 warning-only라 실제 차단/실증 불가
- 실제 운영 환경에서 10개 키워드 end-to-end 검증 미수행

CONTEXT.md §열린 잔존 과제에서 Persona 어조(P3), 글자수·Travel 비교 대상(P2), Automotive 검색 무효(Phase 20) 이슈가 식별됨.

---

## Dependencies

### Upstream (이미 완료)
- Phase 17: CTA 시나리오 설계 확정 (문구 통일 "더 알아보기 →", 링크 목적지만 분기)
- Phase 20: 검색 유효성 실측 (Stock ✅, Travel ✅, Automotive ❌, Real Estate 미측정)
- Phase 21: 이미지 파이프라인 최적화 + Smoke Test
- Phase 22: 품질 게이트 파이프라인 (글자수 warning, CTA 필터, strip_leaks 통합, SEO 메타)

### Downstream (Phase 24 이후)
- Phase 23: 품질 미달 시 자동 재작성 루프 (retry with feedback)
- Phase 25: 글자수 미달 시 발행 차단 (enforce: true 기본값 전환)

---

## Current State Summary

| 항목 | 현재 상태 | Phase 24 목표 |
|------|----------|---------------|
| Persona/어조 | ❌ 단일 draft_system (전 사이트 공용) | ✅ site×depth별 persona_tone 주입 |
| Travel 비교 대상 | ❌ 없음 (Step 2 비교/탐색 힌트만) | ✅ keyword_categories.travel.compare_targets 명시 |
| Automotive 검색 | ❌ Naver API 무효 (기업 위키만 반환) | ✅ grounding: false + fallback 설계 |
| 품질 게이트 | ⚠️ warning-only (enforce 없음) | ✅ quality_gates.enforce 토글 + 검증 런용 true |
| 운영 실증 | ❌ 수동 테스트만 | ✅ mc auto 10회 실행 + RESULT.md 기록 |

---

## Scope

### In Scope (Phase 24)

**Task 1: Persona 어조 설계 + 적용**
- `config/personas.yaml` 신규 생성 (site×depth별 role/tone/style/forbidden)
- `chain_drafter.py`에서 prompt assembly 시 persona system message 주입
- 단위 테스트: persona 로드, 프롬프트 조립, forbidden 필터

**Task 2: 카테고리별 검색/품질 개선**
- `config/category_config.yaml` 신규 또는 `prompts.yaml` 확장: travel.compare_sources, automotive.grounding, real_estate.grounding
- Travel Step 2 프롬프트에 compare_sources 포함
- Automotive/Real Estate Naver 검색 실측 후 grounding 설정
- 글자수 차단 전환: `quality_gates.char_count.enforce` 설정 추가 (기본 false, Phase 25에서 true)

**Task 3: 운영 실증 — 키워드 10개 자동 발행**
- 키워드 10개 큐 등록 (travel 3, tech 2, automotive 1, real_estate 1, education 1, health 1, finance 1)
- `mc auto` 10회 실행으로 전체 큐 소진
- 각 실행: 키워드, 소요 시간, 성공/실패, smoke_test, quality_warnings 기록
- 실패 시 근본 원인 분석 → 코드 수정 → 재실행
- 10개 완료 후 `mc status --json` → `.planning/phase-24/RESULTS.md` 기록

### Out of Scope (향후 Phase)
- Persona 세분화: chain_type(swallow/lateral)별 차별화
- Automotive 유료 API 연동 (카카오/네이버 자동차 API)
- Real Estate 검색 유효성 실측 후 개선
- 품질 미달 시 자동 재작성 (Phase 23)

---

## Constraints

- 기존 인터페이스(함수 시그니처, 반환값) 변경 금지 — 하위호환 유지
- 이미 통과 중인 테스트(286개) 깨지지 않게 수정
- CTA 문구는 Phase 17 확정안("더 알아보기 →" 통일) 준수
- Automotive grounding: false 시 `[STOCK & AUTOMOTIVE GROUNDING]` 가드 유지하며 AI 지식 기반 작성 허용
- 이번 Phase에서는 `enforce: false` 기본 유지 (설정만 추가, Phase 25에서 true 전환)

---

## Risks

| 위험 | 완화 방안 |
|------|-----------|
| Persona 주입 후 톤이 오히려 어색해짐 | 동일 키워드 다른 step으로 --draft 실행하여 수동 검토 후 확정 |
| Travel compare_sources가 프롬프트에 반영 안 됨 | H2 가이드라인에 {compare_sources} 플레이스홀더 추가하여 강제 |
| Automotive grounding false로 인한 hallucination | 프롬프트 가드 유지 + "공개 전/추정/예상" 한정 표현 강제 |
| 10개 키워드 중 실패 다수 발생 | 실패 즉시 분석 → 수정 → 재실행 루프, 수정 내역 PLAN.md 기록 |
| 품질 게이트 enforce=true 시 기존 체인 깨짐 | 이번 Phase에서는 enforce: false 유지, 검증용 별도 플래그 사용 |

---

## Success Criteria

1. **Persona**: rotcha/issue.techpawz/techpawz 각각 Step 1/2/3에서 다른 어조로 생성 확인 (금지어 미포함)
2. **Travel 비교**: Step 2 포스트에 비교 대상 사이트명(야놀자/여기어때/호텔스컴바인) 명시적 언급
3. **Automotive**: Naver 검색 없이도 프롬프트 가드 준수하여 작성 (품질 경고 없음)
4. **품질 게이트**: `quality_gates` 설정 추가, enforce 토글 동작 확인
5. **운영 실증**: 10개 키워드 중 7개 이상 성공 (70% 이상), 평균 소요 시간 기록, RESULTS.md 완성
6. **테스트**: 전체 pytest 통과 (286 + Phase 24 신규)

---

## File Changes Preview

| 파일 | 변경 유형 | Task |
|------|-----------|------|
| `config/personas.yaml` | 신규 생성 | 1 |
| `chain_drafter.py` | 수정 (persona 주입) | 1 |
| `config/prompts.yaml` | 수정 (travel.compare_sources, 품질 게이트 설정) | 2 |
| `config/chain_config.yaml` | 수정 (quality_gates.enforce) | 2 |
| `chain_drafter.py` | 수정 (travel compare_sources 주입, enforce 로직) | 2 |
| `chain_publisher.py` | 수정 (enforce 토글 적용) | 2 |
| `cli/mc.py` | 수정 (--validate-10 플래그) | 3 |
| Tests | 신규/수정 | 1,2,3 |

---

## Decisions Needed (for Discuss-Phase)

1. **Persona granularity**: site×depth (9 combos) vs site×depth×chain_type (27 combos)?
   - 권장: site×depth 9개로 시작, chain_type은 H2 guidelines로 분기

2. **Travel compare_sources 선정 기준**: 공신력(예약 플랫폼) vs 커버리지 vs 제휴?
   - 권장: 야놀자/여기어때(국내 OTA) + 호텔스컴바인(메타서치) + 트립닷컴(글로벌)

3. **Automotive 데이터 소스**: Naver 무효 확인됨 → grounding: false로 fallback 후 Phase 25에서 별도 스파이크
   - 권장: grounding: false 설정만 추가, 데이터 소스는 별도 이슈

4. **10개 키워드 소스**: 트렌드 API vs 수동 큐레이션 vs 과거 성공 체인?
   - 권장: 과거 성공 체인 5개 + 현재 트렌드 5개 믹스

5. **enforce 토글 기본값**: Phase 24는 false, Phase 25에서 true
   - 권장: chain_config.yaml에 enforce: false 명시, 검증 런 시 CLI 플래그로 오버라이드