---
wave: 1
gap_closure: false
---

# PLAN.md — Phase 34 Wave 1: deepseek-v4-flash 사고 과정(규칙 재인용) 본문 유출 근본 개선 (C→A→B)

**Phase:** 34
**Wave:** 1 (코드/설정/프롬프트 수정 + 테스트 — 라이브 발행 제외)
**기반:** CONTEXT.md (조사 완료, read로 라인 갱신함)
**현재 테스트:** 828개 (`pytest --co -q` 실측, 2026-08-01)

---

## 목표

체인 405 s3 지침 노출 사고의 근본 원인(프롬프트 규칙 밀도 + deepseek-v4-flash 사고 과정 출력)을 3축으로 개선:

- **C (최우선)**: 초안 생성 시 `raw_output` 보존 → 재발 시 원인 즉시 분석 가능.
- **A (근본)**: 프롬프트에 메타 대화 금지 명시 + 계획형 문구 축소 + temperature 하향 → 유발 요인 저감.
- **B (안전망)**: leak_defense에 고특이도 문단 단위 정제 추가(오탐 최소화) → 발행 safety net에서 문단 중간 삽입 지침 차단.

**핵심 원칙**: "유발 요인 저감(A)"과 "발행 전 차단(B)" 병행 + "분석 가능성(C)" 확보. Wave 1은 라이브 발행·배포 제외.

---

## Wave 1 범위

코드·설정·프롬프트 수정 + 로컬 Mocking 테스트(828 tests) + 재현 테스트(use_context=False/True 비교)까지 수행한다.
**실제 신규 체인 발행 검증은 Wave 2(별도 승인)에서 수행.**

---

## Task 분해 (C → A → B 순서)

### T1: 백업 (5분)

- [ ] 수정 대상 파일 5개 백업
  - `cp chain_drafter.py chain_drafter.py.bak`
  - `cp mc/leak_defense.py mc/leak_defense.py.bak`
  - `cp chain_db.py chain_db.py.bak`
  - `cp config/prompts.yaml config/prompts.yaml.bak`
  - `cp config/leak_defense.yaml config/leak_defense.yaml.bak`
  - `cp /Users/twinssn/Projects/5000/config/models.yaml /Users/twinssn/Projects/5000/config/models.yaml.bak` (확인 필요: 5000 repo는 별도 관리 — 백업 후 변경 시에도 5000 repo 정책 확인)

**검증**: `ls *.bak config/*.bak mc/*.bak` → 6개 확인. `git status`로 의도치 않은 변경 0건.

---

### T2 [C]: raw_output 관측 강화 (30분)

#### 2-1. DB 컬럼 추가 — `chain_posts.raw_ai_output` (nullable TEXT)

**대상**: `chain_db.py` (마이그레이션 함수 + 모델)

- [ ] `ALTER TABLE chain_posts ADD COLUMN raw_ai_output TEXT` 마이그레이션 함수 추가 (기존 `_migrate` 패턴 확인 필요 — chain_db.py 내 스키마 마이그레이션 루틴 유무를 read로 확인)
- [ ] 신규 함수 `update_post_raw_output(post_id: int, raw_md: str)` 추가 — `update_post_draft()`(line 509)와 동일 패턴.
- [ ] `chain_models.py`/`ImageMetaDB` 등 스키마 모델이 있으면 컬럼 추가 반영 (확인 필요)

**주의**: `chain_posts` 테이블 실측 컬럼 목록 확인 완료 (34개, `raw_ai_output` 없음). ALTER TABLE은 `CREATE TABLE IF NOT EXISTS` 후 실행되도록 마이그레이션 함수 내에서 수행 — DB 쓰기는 Wave 1 실행 단계에서만.

#### 2-2. raw_output 저장 — `chain_drafter.py:369` 주변

**대상**: `chain_drafter.py`

- [ ] line 369 `raw_output = result["content"]` 직후, DB 저장 + 파일 저장 로직 추가
  - DB: `update_post_raw_output(post["id"], raw_output)` (호출부는 `draft_single_post` — 이 함수는 원래 DB 쓰기를 하지 않으므로, `draft_chain`(line 417)에서 호출되는 흐름과 맞춰 **저장 위치 결정 필요**: `draft_single_post` 내부 추가 vs `draft_chain`에서 추가. 후자가 안전 — draft_single_post는 재현 테스트에서 단독 호출되므로 DB 쓰기 최소화 유지)
  - 파일: `output/drafts/{chain_id}/step-{step}-{slug}.raw.md` — `draft_chain`의 기존 파일 저장부(line 470-472) 옆에 추가
- [ ] 저장 형식: raw_output 원문 그대로(전처리 전). 인코딩 utf-8.

**검증**: Mocking 테스트로 `draft_chain` 호출 시 `*.raw.md` 파일 생성 + DB `raw_ai_output` 컬럼에 원문 저장 확인.

---

### T3 [A]: 프롬프트 수정 + temperature 하향 (40분)

#### 3-1. `draft_system` [IMPORTANT] 확장 — `config/prompts.yaml:127-134`

**현재** (line 131-133):
```
- 프롬프트의 작성 지시사항, 규칙, 가이드라인, 체크리스트, JSON 메타데이터 설명, 이미지 플레이스홀더 지시 등을 본문에 절대 포함하거나 언급하지 마세요.
- "알겠습니다", "작성하겠습니다", "주의:", "참고:", "이제 작성", "JSON 마지막 출력", "금지 표현", "이미지 주석" 같은 지시 대화나 사고 과정을 출력하지 마세요.
- 지시사항 준수 여부를 서술하지 마세요. 완성된 블로그 글 본문만 출력하세요.
```

**변경안 (diff 형태 — 적용은 Wave 1 승인 후)**:
```diff
- - "알겠습니다", "작성하겠습니다", "주의:", "참고:", "이제 작성", "JSON 마지막 출력", "금지 표현", "이미지 주석" 같은 지시 대화나 사고 과정을 출력하지 마세요.
+ - "알겠습니다", "작성하겠습니다", "주의:", "참고:", "이제 작성", "JSON 마지막 출력", "금지 표현", "이미지 주석" 같은 지시 대화나 사고 과정을 출력하지 마세요.
+ - 계획·검토·규칙 재인용을 출력하지 마세요. 예를 들어 "피하자", "주의:", "~라고 했으므로", "표 N:", "이미지 플레이스홀더", "제공된 참고 자료", "~금지", "만들지 말 것" 같은 메타 대화(작성 규칙을 스스로 되뇌거나 되풀이하는 문장)를 본문에 쓰지 마세요.
+ - 작성 규칙을 먼저 서술하고 본문을 쓰는 2단 구조를 만들지 마세요. 출력의 처음부터 끝까지 완성된 블로그 글 본문만 출력하세요.
```

#### 3-2. `draft_user` 계획형 문구 축소 — `config/prompts.yaml:160`

**현재 관련 문구**:
- `[STRUCTURE — H2 가이드라인]`의 "H2 제목은 그대로 복사하지 말고, {target_keyword}에 맞게 변형하세요."
- 공통 규칙의 "H2 제목은 target_keyword에 맞게 구체화하고, 템플릿 문구를 그대로 복사하지 말 것."

**변경안 (diff — 축소 검토, 실행 요구는 유지)**:
```diff
- H2 제목은 그대로 복사하지 말고, {target_keyword}에 맞게 변형하세요.
+ H2 제목은 {target_keyword}에 맞게 구체화해 작성하세요.
```
- "구체화하고" → "구체화해" 등 동사 어미를 실행형으로 통일 (계획형 문구 최소화).
- **주의**: `draft_user`는 step 공통 템플릿 — s1/s2/s3 모두에 영향. 회귀 영향은 T6 전체 테스트로 확인.

#### 3-3. temperature 하향 0.85 → 0.7

- [ ] `chain_drafter.py:368` — `generate(system_prompt, user_prompt, tier="default", temperature=0.85)` → `temperature=0.7`
- [ ] `/Users/twinssn/Projects/5000/config/models.yaml` default tier temperature 0.85 → 0.7 (확인 필요: 5000 repo 공유 설정이라 변경 영향 범위 확인 후 결정 — mc 전용 override가 있으면 그쪽만)

**검증**: `grep -n "temperature" chain_drafter.py /Users/twinssn/Projects/5000/config/models.yaml` → 0.7 확인.

---

### T4 [B]: leak_defense 문단 단위 안전망 (40분)

#### 4-1. `mc/leak_defense.py` — 고특이도 문단 전체 제거 추가

**현재** `_remove_reasoning_leaks()` (line 185-245): 라인 시작 매칭 → 다음 빈 줄까지 제거. 문단 중간 삽입 미제거.

**변경안**:
- [ ] 신규 함수 `_remove_reasoning_paragraphs(text)` 추가 — **"문단 중간 포함" 매칭**:
  - 문단(빈 줄로 구분된 블록) 단위 순회.
  - 고특이도 패턴 목록(아래) 중 **1개라도 문단 내 포함**되면 해당 문단 전체 제거.
  - 헤더(`#`)/표(`|`)/리스트(`-`,`*`)/코드펜스(````) 시작 문단은 스킵(기존 정책 유지).
- [ ] 고특이도 패턴 (문단 내 포함 매칭):
  - `프롬프트에서는`, `프롬프트는 .*라고 했`, `금지어:`, `피하자`, `만들지 말 것`, `이미지 플레이스홀더`, `제공된 참고 자료`, `~라고 했으므로`, `~금지`(문단 내), `작성 규칙`, `2단 구조`
  - **단독 금지 패턴**: `주의:`, `표 N:` — 단독으로는 문단 삭제 금지.
  - **복합 조건**: 단독 금지 패턴은 **메타 대화 신호 2개 이상 동시 출현** 시에만 삭제.
- [ ] `strip_leaks()`의 컨텍스트 분기(line 100-104)에 연결:
  - `context="body"`(발행 safety net): `_remove_reasoning_paragraphs` 적용 (고특이도 문단 전체 제거).
  - `context="draft"`(초안 저장): 기존 `_remove_reasoning_leaks`만 유지 → **원문 보존 + 발행 전 방어 2단계 구조**.
  - `context="test"`: 둘 다 적용(테스트 커버리지).

#### 4-2. `config/leak_defense.yaml` — reasoning_leak 확장

**대상**: line 50-125 `reasoning_leak:` 섹션

- [ ] `paragraph_patterns` 서브섹션 신설: 문단 전체 제거용 고특이도 패턴 목록
- [ ] `pair_patterns` 서브섹션 신설: 단독 금지 패턴 + 복합 조건(2개 이상 동시 출현)
- [ ] `action` 확장: `remove_paragraph` (기존, 라인 단위) + `remove_paragraph_high_specificity` (신규, 문단 단위)

**설계 방침**: 패턴은 YAML에만 정의, 로직은 `mc/leak_defense.py`에만 — 단일 소스 원칙 유지(Phase 26 컨벤션).

#### 4-3. 발행 safety net 연동 확인

- [ ] `chain_publisher_core.py:697` (Hugo) / `:813` (Blogger) — `strip_leaks(..., context="body")`가 이미 호출됨. B 적용 시 자동 연동됨을 테스트로 확인.

**검증**: 오탐 테스트(4-4) + 정상 발행 경로 회귀 테스트.

---

### T5: 테스트 작성 (40분)

#### 5-1. C 관측 테스트 — `test_chain_drafter.py` 확장
```python
class TestRawOutputPreservation:
    def test_draft_chain_writes_raw_file(self, tmp_path, monkeypatch):
        # draft_chain 호출 시 output/drafts/{id}/step-*.raw.md 생성 확인
        # generate() mock → raw_output "원문" 반환
        ...
    def test_update_post_raw_output_writes_db(self, tmp_path, monkeypatch):
        # update_post_raw_output → chain_posts.raw_ai_output 컬럼 저장 확인
        ...
```

#### 5-2. A 프롬프트 변경 테스트 — `test_config_validation.py` / 신규
```python
class TestPromptMetaDialogueBan:
    def test_draft_system_contains_meta_dialogue_ban(self):
        # prompts.yaml draft_system에 "피하자"/"규칙 재인용" 금지 문구 포함 확인
    def test_temperature_below_07(self):
        # chain_drafter.py generate 호출 temperature == 0.7 확인 (소스/문자열 검사)
```

#### 5-3. B 문단 단위 안전망 테스트 — `test_reasoning_leak.py` 확장
```python
class TestParagraphHighSpecificity:
    def test_paragraph_mid_insertion_removed(self):
        # "본문 중간에 삽입된 '프롬프트에서는...' 문단 전체 제거"
        # 입력: "정상 문단\n\n프롬프트에서는 제품 스펙에 없는 기능을...\n\n정상 문단2"
        # context="body" → "프롬프트에서는" 문단 제거, 양쪽 정상 문단 보존
    def test_warning_alone_not_removed(self):
        # "'주의:' 단독 포함 문단은 보존 (오탐 방지)"
    def test_table_number_alone_not_removed(self):
        # "'표 2:' 단독 포함 문단(정상 표 캡션)은 보존"
    def test_pair_signal_removed(self):
        # "메타 대화 신호 2개 동시 출현('주의:' + '금지어:') 문단 제거"
    def test_draft_context_keeps_original(self):
        # context="draft"에서는 문단 단위 정제 미적용 → 원문 보존
    def test_header_table_list_paragraphs_preserved(self):
        # "## 제목" 시작 문단/표/리스트 문단은 삭제되지 않음
```

#### 5-4. 오탐 회귀 테스트 (B)
```python
class TestNoFalsePositiveParagraphRemoval:
    def test_normal_body_with_warning_word(self):
        # "주의: 사이즈 선택 시 발볼을 확인하세요." — 본문의 정상 '주의:' 문단 보존
        # (다른 메타 신호 없음 → 문단 유지)
    def test_normal_body_with_table_caption(self):
        # "표 2: 구매 채널별 비교" — 정상 표 캡션 문단 보존
        # (다른 메타 신호 없음 → 문단 유지)
```

---

### T6: 전체 테스트 실행 + 재현 테스트 비교 (40분)

- [ ] `pytest -q` → **828 + 신규 테스트 통과** (기존 828 유지 + 신규만 추가)
- [ ] `pytest test_reasoning_leak.py -q` 통과 (기존 9건 + 신규)
- [ ] `pytest test_chain_drafter.py -q` 통과
- [ ] **재현 테스트 비교 측정** (발행 금지 — draft 생성까지만):
  1. **적용 전**(git stash 또는 T1 백업 기준): `use_context=False` 4회 + `use_context=True` 4회 → 혼재 건수 기록
  2. **적용 후**(A+B 반영): 동일 8회 → 혼재 건수 비교
  3. 판정: 적용 후 혼재 건수가 유의미하게 감소(예: 2/4 → 0~1/4)하면 B 공격성 유지, 아니면 B를 `pair_signal` 조건으로 강화 조절
  4. **use_context=True 주의**: Naver 검색 API 호출됨 — 네트워크 의존. 실패 시 "검색 스킵" 로그 확인 후 재시도 1회. 결과에 컨텍스트 유/무 표기.

- [ ] **8종 시그니처 스캔 회귀** (적용 후 생성된 초안 8회 전부):
  `프롬프트` / `LLM 구축` / `금지어` / `구성안` / `Wait,` / `구조:` / `Let me|I need` / `image_type` — 0건 유지 확인.

---

## Wave 1 완료 기준 (Definition of Done)

1. [ ] `pytest -q` → **828 + 신규 테스트 전부 통과** (기존 회귀 0)
2. [ ] C: `draft_chain` 호출 시 `*.raw.md` 파일 + DB `raw_ai_output` 컬럼 저장 확인 (Mocking 테스트)
3. [ ] A: prompts.yaml [IMPORTANT] 메타 대화 금지 문구 반영 + temperature 0.7 확인
4. [ ] B: 문단 단위 고특이도 정제 — 오탐 테스트(정상 '주의:'/'표 N:' 보존) 통과 + 발행 safety net 연동 확인
5. [ ] 재현 테스트 비교: 적용 후 혼재 건수 감소 확인 (적용 전 vs 후 표로 기록)
6. [ ] 8종 시그니처 스캔 0건 유지
7. [ ] `.bak` 파일 6개만 생성, 기타 의도치 않은 파일 변경 없음 (`git status` 확인)

---

## 리스크/롤백

| 리스크 | 확률 | 영향 | 완화 | 롤백 |
|--------|------|------|------|------|
| B 문단 단위 정제 오탐(정상 '주의:' 문단 삭제) | 중 | 정상 본문 훼손 | 단독 금지 패턴 분리 + 오탐 테스트 5-4 | `git checkout mc/leak_defense.py config/leak_defense.yaml` |
| A 프롬프트 변경으로 s1/s2 발현률 악화 | 낮 | 전체 체인 품질 저하 | T6 재현 테스트 비교로 측정 | `git checkout config/prompts.yaml` |
| temperature 하향으로 글 품질(창의성) 저하 | 중 | 문체 변화 | 0.7로 소폭 하향(0.85→0.7), 0.6 이하 금지 | `git checkout chain_drafter.py` + 5000 models.yaml |
| raw_ai_output 컬럼 마이그레이션 실패 | 낮 | DB 오류 | nullable 컬럼 + try/except 마이그레이션 | ALTER TABLE 롤백(컬럼 삭제) |
| 5000 repo models.yaml 공유 설정 충돌 | 중 | 다른 프로젝트 영향 | 변경 전 5000 repo 컨벤션 확인(확인 필요 항목), mc 전용 override 우선 검토 | 5000 models.yaml 원복 |
| 재현 테스트 네트워크 의존(use_context=True) | 중 | 테스트 지연 | 검색 실패 시 "스킵" 확인 후 결과 표기, 재시도 1회 | 결과에 컨텍스트 유/무 별도 기록 |

**백업 파일**: T1에서 생성한 `*.bak` 6개로 즉시 복구 가능.

---

## 리스크/롤백 요약 (의존성)

```
T1 → T2(C) → T3(A) → T4(B) → T5 → T6
```
- T2, T3, T4는 서로 다른 파일 대상 → 병렬 가능 (단, T4는 T3의 프롬프트 변경 후 문단 정제 패턴 설계에 영향 받을 수 있어 순차 권장)
- T5는 T2~T4 완료 후
- T6은 T5 완료 후 (재현 테스트는 T1 백업 기준 "적용 전"부터 시작 가능)

---

## 별도 이슈 (범위 밖 — 기록만)

- **카테고리 불일치**: `classify_keyword('뉴발란스 740')`→etc vs DB `category_guess='쇼핑/소비'` — derive/draft 분류 불일치. CONTEXT.md에 기록, 이후 별도 phase에서 추적.

---

## 완료 기준 (Definition of Done — Wave 1)

1. [ ] `pytest -q` → **828 + 신규 테스트 전부 통과** (실측 총 개수 재확인)
2. [ ] raw_output 보존 동작 (파일 + DB) — Mocking 테스트 통과
3. [ ] 프롬프트 [IMPORTANT] 메타 대화 금지 반영 + temperature 0.7
4. [ ] 문단 단위 안전망 — 오탐 0건 + 발행 safety net 연동
5. [ ] 재현 테스트 적용 후 혼재 건수 감소 (표 기록)
6. [ ] 8종 시그니처 스캔 0건 유지
7. [ ] `.bak` 6개만 생성, 의도치 않은 변경 없음

### Wave 2 (별도 승인 후 — 본 PLAN 범위 아님)
- 신규 체인 `--draft` → raw_output 저장 확인 → `--publish` → 3개 사이트 라이브 검증(8종 시그니처 0건, H2 정상, 본문 길이 정상)

---

**✅ 승인됨 (2026-08-02 대표님 승인)** — 실발행 검증은 Phase 35 W0-3에서 실행
