# BUG-QUEUE.md — 프로덕션 버그 등록 큐

> 생성: 2026-08-02
> 성격: 발견/등록 전용. **수정 금지** — 별도 승인 후 수정.
> 관련 작업: Phase 35 릭 방어 방향 1 검증 중 발견 (방향 1 검증 범위 밖 이슈).

## 등록 규칙
- 발견 시 이 파일에 항목 추가 (수정은 별도 티켓/승인 필요)
- 각 항목: 재현 조건, 영향, 수정 방향 제안 (비확정)

---

## BUG-001: shared/ai_writer.py reasoning_content 추출로 인한 응답 중간 절단

- **위치**: `/Users/twinssn/Projects/5000/shared/ai_writer.py` `generate()` (line 127-132)
- **증상**: reasoning 모델에서 `content`가 비어있으면 `reasoning_content`(사고 과정)를 그대로 반환. reasoning_content는 완결된 문장이 아니어서 **JSON이 중간에 잘림** (`Unterminated string`).
- **재현**: 2026-08-02 `chain_deriver.derive_chain("함안연꽃테마파크")` 2회
  - 1차: 14,629자 응답 (파싱 실패)
  - 2차: 742자 응답 — `"image_prompt": "Overhead panoramic view...` 문자열 도중 절단 확인
  - 이후 단독 `generate()` 재호출은 정상 (비결정적 발현)
- **영향**: derive/draft 단계 AI JSON 파싱 실패 → chain 생성 중단, orphan chain 발생
- **수정 방향 제안 (비확정)**: `finish_reason == "length"` 또는 reasoning_content 추출 시 최종 문장에서 절단 보정, 또는 max_tokens 증가

## BUG-002: chain_deriver._parse_derivation fallback 4가 부분 배열을 post 배열로 오인

- **위치**: `chain_deriver.py` `_parse_derivation()` (line 205-214, fallback 4)
- **증상**: 전체 JSON 파싱 실패 시 각 `[` 위치에서 부분 배열 파싱 시도 → 잘린 응답에서 **key_points 배열**(문자열 리스트)을 최상위 post 배열로 반환 → `post.get()` AttributeError (`'str' object has no attribute 'get'`)
- **재현**: BUG-001의 잘린 응답 2건 모두. `_parse_derivation(742자)` 직접 호출 시 5개 문자열(key_points) 반환 확인
- **영향**: `derive_chain` line 124에서 크래시, `create_chain`은 이미 실행되어 orphan chain(10013/10014) 잔존 (본 조사에서 삭제 완료)
- **수정 방향 제안 (비확정)**: fallback 4에서 파싱 결과 요소가 dict인지 검증 (`all(isinstance(x, dict) for x in result)`) 후 아니면 무시

## BUG-003: draft_single_post use_context=True에서 NaverSearch 예외('id')로 컨텍스트 스킵

- **위치**: `chain_drafter.py` `draft_single_post()` (line 296-324) — 검색 컨텍스트 주입 블록
- **증상**: 16회 루프 측정(B2/B3) 중 `use_context=True` 12회 전부 `⚠️ 검색 컨텍스트 스킵: 'id'` 예외 → 컨텍스트 없는 상태로 초안 생성. 단독 호출(`retrieve_context_for_post("용인로만바스", "webkr")`)은 정상 (성공)
- **재현 조건**: draft_single_post 반복 호출 중에만 발현. 일시적/상태 의존 (Naver API rate limit 또는 keep-alive 연결 상태 추정)
- **영향**: `use_context=True`가 사실상 no-context로 동작 → 검색 컨텍스트 주입 효과 측정 불가 (Phase 35 B2/B3 [부분검증] 제한 원인)
- **수정 방향 제안 (비확정)**: 예외 메시지('id') 로깅 강화 + 재시도 로직 추가, 또는 Naver API 응답 파싱 실패 시 endpoint 폴백

## BUG-005: protected(리스트/표/헤더) 영역 내 계획텍스트 잔존 → 발행물 노출

- **위치**: `mc/leak_defense.py` `_remove_reasoning_leaks_paragraph()` — protected 타입 문단은 릭 스캔에서 제외
- **증상**: 문단이 `- `(리스트) / `|`(표) / `##`(헤더) 형태로 시작하면 protected로 분류되어 초고특이도 패턴 스캔 대상에서 제외됨 → 계획텍스트가 리스트/표/헤더 모양으로 초안에 들어있으면 **정화 없이 그대로 발행물로 이어짐**
- **재현**: chain 10007 (파손 초안, draft_md 대부분 계획텍스트) dry-run 발행물 `.planning/phase35/dryrun/10007_final_publish.md` 라인 42/47/54 — `- 이 섹션에서는 실제 이용 후기와 평점을 다루어야 합니다...`, `- 여기서 "가격 비교"와 "구매처"를 다루어야 합니다...`, `- 이 섹션에서는 최종 추천과 선택 기준을 제시합니다...` (T4 본문 방어 + FM 메타 방어 모두 통과한 상태에서 잔존)
- **영향**: 발행물에 AI 생성 지침·구조 계획 일부 노출 → 품질/신뢰도 저하. 문단 단위 초고특이도 방어(T4)를 protected 모양으로 우회 가능
- **수정 방향 제안 (비확정)**: ① protected 내 계획텍스트 지시 문구(`다루어야 합니다`, `작성합니다`, `섹션은`, `플레이스홀더` 등) 패턴 추가 스캔, ② 파손 초안 선차단(아래 BUG-006)이 근본 해법
- **상태**: 미수정 (Phase 35 방향 B 지시: 등록만. 실제 수정은 별도 승인 후)

## BUG-006: 파손 초안(draft_md가 계획텍스트 대부분) 선차단 부재

- **위치**: `chain_publisher_core.py` 발행 경로 — draft_md 품질 선검증 단계 없음
- **증상**: 초안 생성 실패/오염으로 draft_md 본문이 계획텍스트(생성 지침·구조 계획·참고자료)로 채워져도 발행 파이프라인이 그대로 진행. T4(문단 단위)는 content 문단만 정화하므로 파손 초안은 protected 잔존으로 남아 발행물 오염
- **재현**: chain 10007 — draft_md 152줄 중 초반 144줄이 계획텍스트. 발행물은 T4+FM 방어 후에도 라인 42/47/54 계획텍스트 잔존 (BUG-005 참조)
- **영향**: 발행물 품질 저하 + 발행량 낭비. 10006류 파손 초안과 동일 계열
- **수정 방향 제안 (비확정)**: 발행 전 draft_md 계획텍스트 비율(예: 지시 문구 패턴 밀도) 검사 게이트 추가 — 초과 시 발행 중단(DeployValidationError) 또는 재생성 트리거
- **상태**: 미수정 (Phase 35 방향 B 지시: 별도 작업)

---

## BUG-004: leak_defense._remove_reasoning_leaks_paragraph 문단 separator(빈 줄) 소실

- **위치**: `mc/leak_defense.py` `_remove_reasoning_leaks_paragraph()` — 문단 재조립 루프
- **증상**: 문단을 개행(`\n\n`)으로 분리 저장할 때 separator를 저장하지 않고, 재조립 시 모든 문단을 `\n\n`로 이어붙임. → **removed=0인데도** 문단 구분이 유지되는 것처럼 보이나, 실제로는 빈 줄 정보가 ('blank') 분리 없이 손실되어 문단이 뭉침 (가독성 저하, 마크다운 구조 훼손 위험)
- **재현**: 문단 분리 시 `("[\n]", "blank")` 저장 없이 재조립하는 코드 경로. 단순 텍스트 2개 문단 입력에서 빈 줄 보존 실패 확인
- **영향**: 발행 본문 문단 뭉침 → 가독성/포맷 저하. 표/헤더/리스트/코드블록 구조 훼손 가능
- **수정 방향 제안 (비확정)**: 빈 줄을 `("[\n]", "blank")`로 분리 저장 후 재조립 시 복원 — **본 수정은 Phase 35 방향 B 작업 범위 내 이미 적용 완료 (test_leak_defense_reasoning.py::TestReasoningLeakBlankLinePreservation 4건으로 검증)**
- **상태**: 수정 완료 (2026-08-02, mc/leak_defense.py)

---
## 큐 상태
- [ ] BUG-001 — 미수정 (검증 범위 밖)
- [ ] BUG-002 — 미수정 (검증 범위 밖)
- [ ] BUG-003 — 미수정 (검증 범위 밖)
- [x] BUG-004 — 수정 완료 (Phase 35 방향 B 범위 내, 테스트 4건 검증)
- [ ] BUG-005 — 미수정 (Phase 35 방향 B 지시: 등록만)
- [ ] BUG-006 — 미수정 (Phase 35 방향 B 지시: 별도 작업)
