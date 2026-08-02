# PHASE36-SUMMARY.md — Phase 36 (정상 초안 생성 복구 + 안전망 잔여 구멍 차단) 완료 기록

> 작성: 2026-08-02
> 커밋: mc `a9b27f5` / `4c43ba0` / `a457591` / 5000 `1dff13638` (로컬 커밋 — push 미수행)
> 상태: **코드 수정 완료(검증됨) + end-to-end 실증 완료(검증됨) → push/실발행은 대표 최종 승인 시**

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

## 2. end-to-end 실증 완료 (검증됨) — PLAN 완료조건 3 충족

커밋: mc `a457591` `test(36): end-to-end 실증 — 정상 초안 생성 + dry-run 게이트 통과`

- **방식**: derive만 dry-run 3회(DB 쓰기 없음) → 정상 응답 1건으로 체인 1개(10015)만 DB 저장 → draft → dry-run 발행 게이트. push/발행 없음, 로컬 전용.
- **실증 키워드**: `스파라쿠아` (etc→depth, 10006/10007 용인로만바스와 동일 조건 — 대조 최적).
- **derive dry-run 3회 (BUG-001/002)**: 3회 모두 truncation 없음·파싱 0에러(post 3개). BUG-001 재시도 로직 실발동 실측 — 1회차 첫 호출 `finish_reason=length len=281` → `max_tokens 12512 재시도` 후 완결 응답. draft step 1에서도 `len=8870` 절단 → 재시도 후 3,046자 완성.
- **게이트 실측 (원문 draft_md 기준)**: step 1/2/3 = **0.0 / 0.0 / 0.036** (임계 0.20). 대조: 10006=0.522, 10007=0.348, 정상=0.0.
- **dry-run 발행 (T4 본문 + FM 메타 + protected)**: 3개 post 전부 CLEAN — 정화 제거 0건, 본문/FM/protected 릭 잔존 0건 = **생성층에서 릭 없는 정상 초안** 확인.
- **회귀**: pytest **907 passed** (변경 후 동일), git status clean.

## 3. 미검증 (실발행 게이트로 이관)

- **다른 카테고리 실효성**: travel/lateral/stock/automotive 등에서 BUG-001/002 수정 실효성은 미실증 (실증은 etc→depth 1건만).
- **draft 비결정성**: draft 생성 1회만 수행 (체인 1개 제한). AI 비결정성에 따른 초안 품질 변동 미확인.
- **Hugo/R2/deploy 실배포**: dry-run은 발행 게이트·정화 파이프라인까지. 실제 hugo build·R2 업로드·wrangler deploy는 의도적으로 미실행.
- **이미지/카드 주입**: 실발행 경로에서의 이미지 생성·카드 주입·smoke test 미검증.

## 4. 실발행 조건 (다음 세션)

1. **(a)** 발행 대상 정상 초안 확보 (게이트 통과 초안 — 10015 계열 또는 신규 생성).
2. **(b)** 실배포 dry-run → 실행 게이트 (hugo build → R2 → deploy 단계별 확인).
3. **(c)** 대표 최종 승인.

push/배포/실발행은 위 3조건 충족 전까지 수행 금지.

## 5. push/발행 보류 사유

- 실발행은 대표 최종 승인 시에만 수행 (미수행). 로컬 커밋만 완료.

## 6. 커밋 해시

| 레포 | 커밋 | 내용 |
|------|------|------|
| **5000** | `1dff13638` | `fix(ai_writer): reasoning 응답 JSON 완결성 검사로 truncation 감지 (BUG-001)` — shared/ai_writer.py + tests/shared/test_ai_writer.py (2파일, 187+) |
| **mc** | `a9b27f5` | `fix(36): 생성 파이프라인 복구 + 안전망 잔여 구멍 차단` — 11파일, 821+ (T2/T3/T4/T5 + 테스트 5파일 + untracked 2파일 `test_ai_writer_bug001.py`/`test_search_retriever_bug003.py` tracked 진입) |
| **mc** | `4c43ba0` | `docs(36): PHASE36-SUMMARY — 코드 수정 완료(907 passed), end-to-end 실증 미완으로 push 보류` (본 문서 최초 기록) |
| **mc** | `a457591` | `test(36): end-to-end 실증 — 정상 초안 생성 + dry-run 게이트 통과` — e2e 스크립트 3개 + `.planning/phase36/e2e/` 산출물 6건 (9파일, 505+) |

## 7. 위반 감지 이력 (다음 세션 주의사항)

1. **T4 초기 구현이 기존 보호 설계 파괴**: protected 스캔에 `get_plan_text_patterns()`(ultra 포함)를 적용해 기존 `TestReasoningLeakUltra::test_ultra_{table,list}_protected` 2건이 깨짐. → PLAN.md 방향("계획텍스트 특유 표현")에 맞게 **plan_text_gate 패턴만 사용**으로 수정, 기존 테스트는 수정하지 않고 코드를 수정해 보존.
   - **주의사항**: protected(리스트/표/헤더)는 구조 보존 우선 설계. 계획텍스트 스캔 추가 시 ultra 패턴은 포함하지 말 것.
2. **게이트 실측 경로 혼동**: strip_leaks 적용 후 텍스트로 ratio를 계산하면 10006/10007이 4.3%/13.0%로 통과해 보이지만, 실제 게이트(`_publish_hugo` line 485)는 **draft_md 원문** 기준. 게이트 실측은 원문 기준으로 확인할 것.
3. **e2e 재실행 시 DB 중복 체인 주의**: `e2e_save_and_draft.py`를 백그라운드로 재실행하면 create_chain이 재호출되어 중복 체인(10016)이 생성됨. 이후 10016은 삭제 완료(실 DB 스냅샷: chains 10012/10015만 존재, publish_log 105건 무변경). e2e 스크립트는 `e2e_draft_only.py`(create_chain 없음)를 사용할 것 — `e2e_save_and_draft.py`는 커밋 대상에서 제외·삭제됨.
