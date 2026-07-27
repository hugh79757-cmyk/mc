# VERIFICATION.md — Phase 24: 콘텐츠 차별화 + 운영 실증

**Phase:** 24  
**Created:** 2026-07-26  
**Status:** Draft

---

## Verification Overview

Phase 24의 3개 Task에 대한 검증 계획을 3분법([검증됨]/[부분검증]/[검증불가])으로 분류하여 기록.

---

## Task 1: Persona 어조 설계 + 적용

### 검증 항목

| ID | 검증 내용 | 분류 | 검증 방법 | 근거/비고 |
|----|-----------|------|-----------|-----------|
| T1-01 | `config/personas.yaml` 로드 + 파싱 | [검증불가] | 단위 테스트 `test_persona.py::test_load_personas` 작성 후 실행 | 파일이 새로 생성되므로 테스트 작성 전까지 검증 불가. 테스트 작성 후 [검증됨] 전환 예정 |
| T1-02 | persona가 system message에 주입되는지 | [검증불가] | `chain_drafter.draft_single_post()` 호출 시 system_prompt에 persona 텍스트 포함 확인 (로그/디버그) | 코드 수정 전까지 검증 불가. 수정 후 로그 출력으로 확인 |
| T1-03 | 동일 키워드 다른 step draft 어조 차이 | [검증불가] | `mc "테스트키워드" --draft`로 3개 step draft 생성 후 수동 비교 | 자동화 불가 — 수동 리뷰 필요. [부분검증] 대상 |
| T1-04 | persona forbidden 단어가 draft에 없음 | [검증불가] | 단위 테스트 `test_persona.py::test_forbidden_filter` 작성 | 테스트 작성 전까지 검증 불가. forbidden 단어 리스트 기반 grep 검증 가능 |
| T1-05 | prompts.yaml draft_system과 충돌 안 함 | [검증불가] | draft 생성 시 프롬프트 구조 유지 확인 | [PERSONA-01] 테스트로 검증 예정 |
| T1-06 | 단위 테스트: persona 로드, 프롬프트 조립, forbidden 필터 | [검증불가] | `pytest tests/test_persona.py -x -q` | 테스트 파일 신규 생성 필요 |

### Task 1 검증 요약

- **자동 검증 가능**: T1-01, T1-04, T1-06 (단위 테스트 작성 후)
- **수동 검증 필요**: T1-03 (어조 차이는 주관적 평가)
- **코드 수정 후 확인**: T1-02, T1-05

---

## Task 2: 카테고리별 검색/품질 개선

### 검증 항목

| ID | 검증 내용 | 분류 | 검증 방법 | 근거/비고 |
|----|-----------|------|-----------|-----------|
| T2-01 | `travel.compare_sources` config 로드 | [검증불가] | 단위 테스트 `test_category_config.py::test_travel_compare_sources_exists` | 테스트 작성 전까지 검증 불가 |
| T2-02 | travel Step 2 프롬프트에 compare_sources 포함 | [검증불가] | `mc "제주도카페" --draft` 실행 후 Step 2 user_prompt 로그 확인 | chain_drafter 수정 후 검증 가능 |
| T2-03 | automotive grounding: false 시 Naver 검색 스킵 | [검증불가] | `mc "전기차보조금2026" --draft` 실행 후 "[drafter] 검색 컨텍스트 스킵" 로그 확인 | grounding 플래그 체크 로직 추가 후 확인 |
| T2-04 | real_estate grounding: false 시 Naver 검색 스킵 | [검증불가] | `mc "서울아파트시세" --draft` 실행 후 검색 스킵 로그 확인 | 동일 |
| T2-05 | `quality_gates.char_count.enforce` config 로드 | [검증불가] | 단위 테스트 `test_category_config.py::test_quality_gates_enforce_config` | 테스트 작성 전까지 검증 불가 |
| T2-06 | enforce=true 시 글자수 미달 draft 재생성(retry) | [검증불가] | 인위적으로 짧은 draft 생성 시 retry 로직 동작 확인 | retry 로직 구현 후 테스트 필요 |
| T2-07 | enforce=false 시 warning만 기록 (기존 동작 유지) | [검증불가] | 기존 테스트 `test_chain_drafter.py` 품질 게이트 테스트로 회귀 확인 | Phase 22 테스트가 커버해야 함 |
| T2-08 | 단위 테스트: 카테고리 config 조회, enforce retry 로직 | [검증불가] | `pytest tests/test_category_config.py -x -q` | 테스트 파일 신규 생성 필요 |

### Task 2 검증 요약

- **자동 검증 가능**: T2-01, T2-05, T2-08 (단위 테스트)
- **통합 검증 필요**: T2-02, T2-03, T2-04 (--draft 실행 로그 확인)
- **회귀 검증**: T2-07 (기존 테스트 유지 확인)

---

## Task 3: 운영 실증 — 키워드 10개 자동 발행

### 검증 항목

| ID | 검증 내용 | 분류 | 검증 방법 | 근거/비고 |
|----|-----------|------|-----------|-----------|
| T3-01 | 10개 키워드 큐 등록 확인 | [검증불가] | `mc queue list` 실행 후 10개 pending 확인 | CLI 명령으로 검증 가능 |
| T3-02 | `mc --validate-10` 실행 후 큐 비어있음 | [검증불가] | 실행 후 `mc queue list` 결과 empty 확인 | 검증 스크립트 완료 후 확인 |
| T3-03 | 성공률 70% 이상 (7/10 이상 성공) | [검증불가] | `RESULTS.md`의 Summary 섹션 확인 | 10개 실행 완료 후 확정 |
| T3-04 | `mc status --json` 정상 출력 | [검증불가] | JSON 파싱 가능 여부 + 필드 완전성 확인 | 검증 완료 후 실행 |
| T3-05 | RESULTS.md에 실증 데이터 기록 | [검증불가] | 파일 존재 + 필수 섹션(Summary, Quality Warnings, Per-Keyword) 확인 | 검증 스크립트 완료 후 자동 생성 |
| T3-06 | 실패 키워드 근본 원인 분석 및 수정 기록 | [부분검증] | PLAN.md "운영 중 발견 이슈" 섹션에 기록 여부 확인 | 실행 과정에서 발생 시 기록 |
| T3-07 | 품질 게이트 enforce 모드 정상 동작 | [검증불가] | `--enforce` 플래그로 실행 시 글자수 미달 차단 확인 | Task 2 완료 후 검증 가능 |

### Task 3 검증 요약

- **CLI 명령으로 검증**: T3-01, T3-02, T3-04
- **결과 파일로 검증**: T3-03, T3-05
- **프로세스 검증**: T3-06 (수동 기록)
- **통합 검증**: T3-07 (Task 2 연동)

---

## 전체 검증 계획

### Phase Gate (Phase 24 완료 조건)

| 조건 | 검증 방법 | 상태 |
|------|-----------|------|
| 전체 pytest 통과 (286 + Phase 24 신규) | `pytest -x -q` | [검증불가] — 테스트 작성 후 |
| Task 1: persona 어조 차이 수동 확인 | `--draft` 3개 step 비교 | [검증불가] — 구현 후 |
| Task 2: travel compare_sources 프롬프트 반영 | Step 2 user_prompt 로그 확인 | [검증불가] — 구현 후 |
| Task 2: automotive/real_estate grounding false | 검색 스킵 로그 확인 | [검증불가] — 구현 후 |
| Task 3: 10개 키워드 70% 성공 | RESULTS.md Summary 확인 | [검증불가] — 실행 후 |

---

## 잔존 위험 (Residual Risks)

| 위험 | 영향도 | 완화 방안 | 검증 시점 |
|------|--------|-----------|-----------|
| Persona 주입 후 어조가 오히려 어색해짐 | 높음 | 동일 키워드 --draft로 3개 step 생성 후 수동 리뷰 → 어색하면 personas.yaml 수정 | Task 1 완료 직후 |
| Travel compare_sources가 프롬프트에 반영 안 됨 | 중간 | H2 가이드라인에 {compare_sources} 플레이스홀더 강제 포함 | Task 2 구현 시 |
| Automotive grounding false로 hallucination 증가 | 높음 | STOCK & AUTOMOTIVE GROUNDING 프롬프트 가드 유지 + "공개 전/추정/예상" 강제 | Task 2 구현 시 |
| 10개 키워드 중 5개 이상 실패 | 높음 | 실패 즉시 분석 → 수정 → 재실행 루프, PLAN.md에 기록 | Task 3 실행 중 |
| enforce=true 시 기존 체인 발행 차단 | 중간 | Phase 24는 enforce: false 기본, 검증용 --enforce만 사용 | Task 2 config 설정 시 |
| 품질 게이트 retry 로직 무한 루프 | 낮음 | 최대 1회 retry 후 warning으로 fallback | Task 2 구현 시 |

---

## 검증 완료 보고 시 포함할 것

1. **테스트 실행 결과**: `pytest -x -q` 출력 (pass/fail 개수)
2. **수동 검증 증거**: Persona 어조 비교 스크린샷/발췌, travel compare_sources 프롬프트 로그
3. **운영 실증 데이터**: RESULTS.md 전문
4. **수정 내역**: PLAN.md "운영 중 발견 이슈" 섹션
5. **잔존 위험 현황**: 위 표의 각 항목별 해소/미해소 상태

---

## 승인 체크포인트

```
╔═══════════════════════════════════════════════════════════════╗
║  CHECKPOINT: Verification Required                          ║
╚═══════════════════════════════════════════════════════════════╝

Phase 24 모든 Task 구현 완료 후, 위 검증 항목 실행하여 결과 보고.

→ Type "approved" when all verification items pass
→ Describe issues if any verification fails
```