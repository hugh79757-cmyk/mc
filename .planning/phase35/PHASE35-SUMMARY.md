# PHASE35-SUMMARY.md — Phase 35 (릭 방어 강화, 방향 A/B) 완료 기록

> 작성: 2026-08-02
> 커밋: `fe527a4` (T4 발행 안전망 실제 배선 + frontmatter 메타 릭 방어)
> 상태: **완료(검증된 범위 한정) + 미해결 5건 Phase 36 이관 + 실발행 미수행**

---

## 1. 완료 (검증됨)

| 항목 | 검증 근거 |
|------|----------|
| **T4 발행 안전망 실제 배선** | `chain_publisher_core.py` line 694-700 `strip_leaks(cleaned.body, context="body")` 실연결. dry-run 실측: 본문 릭 **21건 → 0건** (chain 10007, `.planning/phase35/dryrun/10007_final_publish.md`) |
| **frontmatter 메타 릭 방어** | `mc/leak_defense.py` `strip_frontmatter_meta_leaks()` — description 매칭 시 `""` 정화, title 매칭 시 발행 차단(DeployValidationError). dry-run: description 정화 1건, title 0건 |
| **방향 1 축소** | `config/prompts.yaml` STEP별 금지 표현 제거 + `config/leak_defense.yaml` ultra_high_signals 2단 리스트(38 ultra + 9 저특이도) |
| **BUG-004 수정** | 빈 줄 separator 소실 수정 (`mc/leak_defense.py`), `TestReasoningLeakBlankLinePreservation` 4건 검증 |
| **파손 초안 게이트 작동 실증** | chain 10007 파손 초안이 발행 단계에서 protected 계획텍스트 잔존으로 적발 → 발행 보류. 게이트(T4+FM 메타+육안)가 오염 발행물을 실제 차단함을 실증 |
| **회귀** | pytest **872 passed** (기존 866 + 신규 6, `TestFrontmatterMetaLeaks`) |

## 2. 미해결 (Phase 36 이관)

| BUG | 재현 조건 | 수정 방향 (비확정) |
|-----|----------|-------------------|
| **BUG-001** | shared/ai_writer.py reasoning_content 추출 시 응답 중간 절단 (`Unterminated string`) | finish_reason=="length" 절단 보정 또는 max_tokens 증가 |
| **BUG-002** | chain_deriver._parse_derivation fallback 4가 부분 배열을 post 배열로 오인 → AttributeError | 파싱 결과 요소 dict 검증 (`all(isinstance(x, dict))`) |
| **BUG-003** | draft_single_post use_context=True에서 16회 중 12회 NaverSearch 예외('id')로 컨텍스트 스킵 | 예외 로깅 강화 + 재시도/endpoint 폴백 |
| **BUG-005** | protected(리스트/표/헤더) 문단은 초고특이도 스캔 제외 → 계획텍스트 잔존 발행물 노출 (10007 라인 42/47/54) | protected 내 지시 문구 패턴 스캔 추가 (**정상 리스트 오탐 방지 필수**) |
| **BUG-006** | 파손 초안(draft_md 계획텍스트 대부분) 발행 선차단 부재 | 발행 전 계획텍스트 비율 임계치 게이트 → 초과 시 발행 중단/재생성 |

## 3. 실발행 미수행 사유

- **정상 초안 부재 (생성 파이프라인 고장)**: 발행 대상 후보 10006/10007 모두 파손 초안(본문 대부분이 계획텍스트). BUG-001(truncation) + BUG-003(context 스킵)이 초안 생성 품질 저하의 근본 원인으로 추정. 정상 초안이 나와야 발행 대상 확보 가능 → **생성 복구가 안전망 잔여보다 선행** (Phase 36 우선순위 근거).
- 실제 발행/배포/push는 게이트 통과 + 대표 최종 승인 시에만 수행 (미수행).

## 4. 위반 감지 이력 (다음 세션 주의사항)

1. **"T4 발행 경로 연결" 기록과 실제 미배선 불일치**: 이전 세션 보고("발행 경로 context='body'에 적용")와 실제 코드 불일치 — `_publish_hugo`에 `strip_leaks` 호출이 없었음. dry-run 본문 릭 21건으로 적발 → 이번에 실제 배선 완료.
   - **주의사항**: "적용했다"는 주장은 grep으로 실증할 것. `git diff` + dry-run 산출물 스캔을 커밋 전 기본 검증으로.
2. **10007 "정상 초안" 오분류**: 이전 세션에서 10007을 정상 초안으로 분류했으나, 실제 draft_md는 파손 초안(152줄 중 초반 144줄 계획텍스트). 10006과 동일 계열이었음.
   - **주의사항**: 초안 품질 판정은 draft_md 원문을 직접 열어 육안 확인할 것. 메타데이터/이전 기록 신뢰 금지.

## 5. 잔존 위험

- BUG-005/006 미수정 상태로 존재 — 정상 초안이 발행 대상으로 확보되더라도 protected 계획텍스트 잔존 가능성 있음 (Phase 36에서 선처리).
- 커밋 `fe527a4`는 로컬 브랜치(`feat/keyword-category-template`) — push/배포는 최종 승인 전까지 보류.
- BUG-001/002/003은 Phase 35 검증 범위 밖으로 미조사 — 재현 조건만 등록됨.
