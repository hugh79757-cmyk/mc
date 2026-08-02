# PHASE36-SUMMARY.md — Phase 36 (정상 초안 생성 복구 + 안전망 잔여 구멍 차단) 완료 기록

> 작성: 2026-08-02
> 커밋: mc `a9b27f5` / 5000 `1dff13638` (로컬 커밋 — push 미수행)
> 상태: **코드 수정 완료(검증됨) + 정상 초안 end-to-end 실증 미완 → push/발행 보류**

---

## 1. 완료 (검증됨)

| BUG | 수정 내용 | 검증 근거 |
|-----|----------|----------|
| **BUG-001** truncation | `shared/ai_writer.py` `_is_truncated()` JSON 완결성 검사 추가 — `{`/`[`로 시작 시 닫는 괄호 불균형 → 중간 절단 판정 (기존 `finish_reason=="length"` 단독 감지 구멍 보완) | 5000 `tests/shared/test_ai_writer.py` 14 passed. 재현 케이스(742자, `"image_prompt": "Overhead...` 문자열 도중 절단) 감지 실증. mc `test_ai_writer_bug001.py` 11건 포함 |
| **BUG-002** fallback 파싱 | `chain_deriver.py` `_extract_list()` — `_is_posts_list()`로 요소가 전부 dict인지 검증, 문자열 배열(key_points)의 post 오인 방지 | `test_chain_deriver.py` 55 passed (기존 51 + 신규 4) |
| **BUG-006** 파손 초안 게이트 | `chain_publisher_core.py` `check_plan_text_ratio()` + `_publish_hugo` 선차단 — 계획텍스트 지시 문구 라인 비율 > 20%면 `DeployValidationError`로 발행 중단 | 실측 원문 기준: 10006 **52.2% 차단**, 10007 **34.8% 차단**, 정상 초안 0.0% 통과. `TestPlanTextGate` 6건 → `test_chain_publisher_core.py` 65 passed |
| **BUG-005** protected 정밀 스캔 | `mc/leak_defense.py` `_remove_reasoning_leaks_paragraph()` — protected(리스트/표/헤더) 문단 내부에서도 `plan_text_gate` 패턴 2차 스캔. 코드블록 마커/정상 리스트(제품 스펙/장단점)는 보존 | 10007 draft_md protected 계획텍스트 3건(라인 56/61/68) 제거 실측. `TestReasoningLeakProtectedScan` 6건 + 오탐 회귀 → `test_leak_defense_reasoning.py` 44 passed. 기존 `test_ultra_{table,list}_protected` 보호 설계 유지(ultra는 protected 내 보존) |
| **BUG-003** use_context 스킵 | `search_retriever.py` `retrieve_context_for_post(..., retries=1, backoff)` 재시도 + `chain_drafter.py` `post.get("id")` None 체크 + DB 저장 예외 격리 (id 부재 시 주입은 계속) | `test_search_retriever_bug003.py` 8 passed (재시도 4 + id 격리 4). draft에 검색 컨텍스트(참고 자료) 주입 실증 |
| **회귀** | pytest 전체 | **907 passed = 872(베이스라인) + 35 신규**, 실패 0 |

## 2. 미완 (실증 필요)

- **정상 초안 end-to-end 생성 실증 (PLAN 완료조건 3)**: BUG-001/002/003 수정 후 실제 생성 파이프라인으로 정상 초안 1건 이상 확보 → dry-run 발행 게이트(T4 본문 + FM 메타 + D8 CTA + BUG-006/005) 통과 실증 **미수행**.
  - 현재까지는 단위 테스트로 게이트 동작(정상 0%, 파손 52%/35% 차단)만 실증됨.
  - 발행 후보 10006/10007은 여전히 파손 초안(게이트가 차단하는 대상) — 새 정상 초안 생성 필요.

## 3. push/발행 보류 사유

- **end-to-end 정상 초안 실증 미수행**: 수정된 생성 파이프라인(BUG-001~003)으로 정상 초안이 실제로 생성되는지 실증 전까지는 발행 대상이 없고, 게이트 통과 실증도 불가.
- 실제 발행/배포/push는 end-to-end 정상 초안 실증 + 대표 최종 승인 시에만 수행 (미수행).

## 4. 커밋 해시

| 레포 | 커밋 | 내용 |
|------|------|------|
| **5000** | `1dff13638` | `fix(ai_writer): reasoning 응답 JSON 완결성 검사로 truncation 감지 (BUG-001)` — shared/ai_writer.py + tests/shared/test_ai_writer.py (2파일, 187+) |
| **mc** | `a9b27f5` | `fix(36): 생성 파이프라인 복구 + 안전망 잔여 구멍 차단` — 11파일, 821+ (T2/T3/T4/T5 + 테스트 5파일 + untracked 2파일 `test_ai_writer_bug001.py`/`test_search_retriever_bug003.py` tracked 진입) |

## 5. 위반 감지 이력 (다음 세션 주의사항)

1. **T4 초기 구현이 기존 보호 설계 파괴**: protected 스캔에 `get_plan_text_patterns()`(ultra 포함)를 적용해 기존 `TestReasoningLeakUltra::test_ultra_{table,list}_protected` 2건이 깨짐. → PLAN.md 방향("계획텍스트 특유 표현")에 맞게 **plan_text_gate 패턴만 사용**으로 수정, 기존 테스트는 수정하지 않고 코드를 수정해 보존.
   - **주의사항**: protected(리스트/표/헤더)는 구조 보존 우선 설계. 계획텍스트 스캔 추가 시 ultra 패턴은 포함하지 말 것.
2. **게이트 실측 경로 혼동**: strip_leaks 적용 후 텍스트로 ratio를 계산하면 10006/10007이 4.3%/13.0%로 통과해 보이지만, 실제 게이트(`_publish_hugo` line 485)는 **draft_md 원문** 기준. 게이트 실측은 원문 기준으로 확인할 것.
