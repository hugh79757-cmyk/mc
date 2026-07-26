# CONTEXT.md — Phase 22: 콘텐츠 품질 제어

**Phase:** 22  
**Created:** 2026-07-26  
**Milestone:** 품질 게이트 파이프라인 삽입  
**Mode:** execute (코드 착수)

---

## Objective

발행된 모든 포스트가 최소 품질 기준(글자수, CTA, SEO 메타, 릭 방어)을 자동으로 충족하도록 품질 게이트를 파이프라인에 삽입한다.

---

## Background

Phase 17에서 CTA 시나리오 설계가 완료되었으나(`.planning/phase-17/CTA-SCENARIO.md`), 코드화되지 않은 상태다. 현재 CTA 텍스트는 `chain_card_injector.py:get_cta()`가 site×direction만 보고 고정 문구를 반환하며, 카테고리별 분기/내부이동 vs 최종행동 분리가 없다.

또한 프롬프트 릭/플레이스홀더/부적절 CTA 방어 패턴이 `chain_drafter.py`, `chain_publisher_core.py`, `audit/audit_chain.py`, `conftest.py` 4개 파일에 중복 분산되어 있다.

글자수 제한(prompts.yaml: 2500~3500자)은 프롬프트에만 명시되고 검증 로직이 없다.

Phase 21에서 smoke test가 추가되었으나, 품질 게이트(사전 검증)는 없다.

---

## Dependencies

### Upstream (이미 완료)
- Phase 17: CTA 시나리오 설계 확정 (문구 통일 "더 알아보기 →", 링크 목적지만 분기)
- Phase 21: smoke_test() 구현, 이미지 파이프라인 최적화(병렬화/백오프/썸네일 재사용)
- Phase 13: `_sanitize_markdown_body`, `_extract_clean_body`, `_clean_markdown_symbols` 구현
- Phase 9-11: `_strip_prompt_leak`, D8-GATE CTA leak 스캐너 구현

### Downstream (Phase 22 이후)
- Phase 23: 품질 게이트 실패 시 재작성 루프 (retry with feedback)
- Phase 24: 글자수 미달 시 발행 차단 (현재는 warning만)

---

## Current State Summary

### 품질 검증 현황
| 항목 | 현재 상태 | Phase 22 목표 |
|------|----------|---------------|
| 글자수 검증 | ❌ 없음 (프롬프트만) | ✅ 측정 함수 + 검증 게이트 (warning) |
| CTA 주입 | ❌ site×direction 고정 | ✅ category×depth 템플릿 + 공식 CTA 1개 강제 |
| SEO 메타 | ⚠️ description 존재, 길이 검증 없음 | ✅ 150자 제한 + 이미지 alt 자동 추가 |
| 릭 방어 | ⚠️ 4개 파일에 분산 | ✅ 단일 모듈 통합 + strip_leaks() 함수 |
| 프론트매터 | ✅ 필수 필드 검증 | ✅ 유지 + description 길이 검증 |

### 파이프라인 삽입 지점
```
derive_chain → draft_chain → [품질 게이트 1: 글자수/CTA/SEO/릭] → generate_chain_images
                                                     ↓
publish_chain → inject_cards_chain → [품질 게이트 2: smoke test] → 완료
```

---

## Scope

### In Scope (Phase 22)
1. **글자수 기준 정립 + 검증 게이트** (`prompts.yaml` + `_validate_draft_schema` 확장)
2. **CTA 코드화** (`config/cta_templates.yaml` + `get_cta()` + sanitize 필터 + 검증)
3. **릭 방어 패턴 통합 + SEO 메타 보강** (`config/leak_defense.yaml` + `strip_leaks()` + frontmatter 보강)

### Out of Scope (향후 Phase)
- 품질 미달 시 자동 재작성 루프 (Phase 23)
- 글자수 미달 발행 차단 (Phase 24, 현재는 warning만)
- 카테고리별 비교 대상 사이트 구체화 (P2 별도)

---

## Constraints

- 기존 인터페이스(함수 시그니처, 반환값) 변경 금지 — 하위호환 유지
- 이미 통과 중인 테스트(251개) 깨지지 않게 수정
- CTA 문구는 Phase 17 확정안("더 알아보기 →" 통일) 준수
- 플레이스홀더는 `{{ENTRY_LINK}}`만 사용 (`{{FUNNEL_LINK}}`, `{{CPA_LINK_PLACEHOLDER}}` 금지)
- 기준 미달이어도 파이프라인 차단하지 않음 (warning + 플래그만)

---

## Risks

| 위험 | 완화 방안 |
|------|-----------|
| 글자수 측정 로직이 마크다운 문법을 잘못 제외 | 단위 테스트로 한글/영문/혼합/마크다운 포함 케이스 검증 |
| CTA 교체 로직이 기존 card_injector와 충돌 | 통합 테스트로 기존 체인 발행 플로우 검증 |
| 릭 방어 통합 시 기존 패턴 누락 | 기존 4개 파일의 모든 패턴을 RESEARCH.md에 매핑 후 이전 |
| SEO 메타 보강이 Hugo 빌드 깨뜨림 | `_verify_before_deploy` 검증으로 사전 차단 |