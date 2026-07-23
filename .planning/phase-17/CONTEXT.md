# CONTEXT.md — Phase 17

**Phase:** 17  
**Created:** 2026-07-24  
**Milestone:** CTA 설계  
**Mode:** design-only  

## Objective

5개 카테고리에 대해 독자 행동 여정에 맞는 CTA 시나리오를 설계한다. Phase 16의 H2 수준 구조를 넘어 실제 독자의 다음 행동으로 연결하는 문구와 배치 전략을 정의한다.

## Scope

- 카테고리별 독자 행동 여정 정의
- CTA 문구 후보 작성 및 억지 CTA 제외 근거
- Step별 CTA 강도 배치 설계
- mc 시스템 주입 구조 설계 (`keyword_categories.cta_phrases` 필드)
- 내부이동 CTA vs 최종행동 CTA 분리 설계
- 프롬프트 릭 방지 설계 (주입 지시 + 출력 검증)

## Constraints

- 코드 작성 금지 (설계만)
- 플레이스홀더 명칭: `{{ENTRY_LINK}}` 또는 `{{FUNNEL_LINK}}` (`{{CPA_LINK_PLACEHOLDER}}` 사용 금지)
- CTA는 rotcha(퍼널 입구)로 보내는 유입 링크 개념으로 명시
- 대표님 CTA 문구 확정 후에만 코드 착수

## Inputs

- `config/prompts.yaml` (`keyword_categories` 참고)
- `chain_drafter.py` (draft 생성 위치 참고 — 수정 금지)
- `.planning/phase-16/` (CTA 설계는 Phase 16 Wave-4에서 다루었으나 상세 설계는 Phase 17에서 진행)
- 대표님 CTA 시나리오 표 검토 피드백

## 잔존 위험

- 설계 확정 전 코드에 cta_phrases 필드를 미리 추가하면, 대표님이 문구를 변경할 때 rollback 비용이 발생함
- 플레이스홀더 이름이 기존 폐기 개념(CPA)과 혼동될 경우, 향후 개발자가 제휴 로직을 되살릴 위험이 있으므로 명칭을 확정해야 함
