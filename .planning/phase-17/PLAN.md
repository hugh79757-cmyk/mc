# PLAN.md — Phase 17: CTA 시나리오 설계

**Phase:** 17  
**Owner:** 대표님 + 신입 에이전트  
**Mode:** design-only  
**Status:** ○ Planned

---

## Objective

5개 카테고리(travel, automotive, stock, real_estate, etc)에 대해 독자 행동 여정에 맞는 CTA 시나리오를 설계한다. 코드 작성 없이 설계 산출물만 생성한다.

## 배경

Phase 16 Step3 H2 수준까지 프롬프트 설계가 진행됐으나, 실제 행동유발(CTA) 장치는 미정의 상태이다. 이 phase는 CTA 문구, 강도, Step 배치, mc 주입 위치, 프롬프트 릭 방지 방법까지 설계한다.

## 설계 범위

1. 카테고리별 독자 행동 여정 정의 (정보탐색 → 비교 → 결정 → 행동)
2. CTA 문구 후보 3~5개/카테고리 (억지 CTA 제외 근거 포함)
3. Step별 CTA 배치 설계 (내부이동 vs 최종행동 분리)
4. mc 시스템 주입 구조 설계 (`keyword_categories.cta_phrases` 필드 제안)
5. 프롬프트 릭 방지 설계 (주입 지시 + 출력 검증)

## 산출물

- CTA 시나리오 표 (마크다운, 5개 카테고리 통합)
- `keyword_categories` cta_phrases 필드 설계안
- Step별 주입 위치 설계안
- 플레이스홀더 명칭 정리 (`{{ENTRY_LINK}}` 또는 `{{FUNNEL_LINK}}`)
- 대표님 검토용 요약

## 제약

- 코드 작성 금지 (설계만)
- 플레이스홀더 명칭은 `{{ENTRY_LINK}}` 또는 `{{FUNNEL_LINK}}` 사용 (`{{CPA_LINK_PLACEHOLDER}}` 금지)
- CPA(제휴) 개념과 혼동되지 않도록 rotcha 퍼널 유입 링크 개념으로 명시
- 내부이동 CTA와 최종행동 CTA를 명시적으로 분리
- 프롬프트 릭 방지 검증 방법 설계에 포함

## Definition of Done

- [ ] CTA 시나리오 설계 완성 (5개 카테고리 표)
- [ ] 내부이동 CTA / 최종행동 CTA 분리 설계 완료
- [ ] 플레이스홀더 명칭 정리 완료 (`{{ENTRY_LINK}}`/`{{FUNNEL_LINK}}`)
- [ ] 프롬프트 릭 방지 설계 작성 완료
- [ ] mc 주입 구조 설계 완료
- [ ] 대표님 검토 및 설계 확정
- [ ] 설계안 저장 (`.planning/phase-17/` 내)

## Repository

- **Working dir:** `/Users/twinssn/projects2/mc`
- **Phase dir:** `.planning/phase-17`
