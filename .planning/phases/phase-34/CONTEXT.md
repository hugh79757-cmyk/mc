# CONTEXT.md — Phase 34: deepseek-v4-flash 사고 과정(규칙 재인용) 본문 유출 근본 개선

## 문제 요약

체인 405(뉴발란스 740) s3(techpawz) 라이브 본문에 프롬프트 지침 문단이 노출됐던 사고. 수동 정제·재발행으로 라이브는 정상화됨. 이후 재현 테스트로 원인 판정 완료:

- **판정**: "프롬프트 구조(규칙 밀도 높은 시스템 프롬프트)가 유발 요인 + deepseek-v4-flash 출력 비결정성이 발현 여부를 좌우하는 복합 구조"
- **재현율**: 동일 프롬프트·동일 모델로 4회 생성 → 2회에서 사고 과정/규칙 재인용이 본문으로 유출 (RUN 3: `주의: "하시기 바랍니다" 금지… 피하자.`/`표 2: 구매 경로별 특징.`/`제공된 참고 자료가 없지만…`, RUN 4: `프롬프트는 "참고 자료에 없는 구체적 수치를 절대 만들지 마세요"라고 했지만…`/`이미지 플레이스홀더: 썸네일용은 본문 어디에?`)
- **미제거 원인**: 발행 safety net(`strip_leaks` reasoning_leak)이 **라인 단위 매칭**(매칭 라인 → 다음 빈 줄까지 문단 제거)이라, **문단 중간에 삽입된 지침**은 시작 라인이 매칭되지 않아 제거 실패.

## 진단에서 드러난 3대 약점

| # | 약점 | 세부 |
|---|------|------|
| C1 | **raw_output 미보존** | 초안 생성 시 AI 원문(raw_output)을 어디에도 저장하지 않음 → 이번 진단에서 원본을 대화 로그로만 복원. 재발 시 분석 불가. |
| A1 | **프롬프트 규칙 나열 밀도** | `draft_system`에 [ABSOLUTE BAN] 18종·[ANTI-HALLUCINATION]·[분량 규칙]·[톤]·[형식]·[IMPORTANT]·[Output Checklist] 10항 — 계획/검토형 출력을 유발하는 구조. |
| B1 | **leak_defense 라인 단위 한계** | `_remove_reasoning_leaks()`가 "라인 시작 매칭 → 다음 빈 줄"까지만 제거. 문단 중간 삽입 지침 미제거. |

## 핵심 코드 위치 (read로 갱신한 최신 라인)

| 기능 | 파일 | 라인 |
|------|------|------|
| `generate()` 호출 + `raw_output = result["content"]` | `chain_drafter.py` | 368-369 |
| `parse_ai_output()` 분기 (파싱 실패 시 `draft_md = raw_output`) | `chain_drafter.py` | 373-386 |
| `strip_leaks(context="draft")` (초안 정제) | `chain_drafter.py` | 391 |
| `update_post_draft()` (draft_md 저장 — raw 미저장) | `chain_db.py` | 509 |
| `_remove_reasoning_leaks()` (라인 단위 문단 제거) | `mc/leak_defense.py` | 185-245 |
| `strip_leaks()` 컨텍스트 분기 (1.5 reasoning: draft/body/test) | `mc/leak_defense.py` | 100-104 |
| 발행 safety net — Hugo 본문 정제 후 | `chain_publisher_core.py` | 697-700 |
| 발행 safety net — Blogger 본문 정제 후 | `chain_publisher_core.py` | 813-816 |
| `reasoning_leak` 패턴 정의 | `config/leak_defense.yaml` | 50-125 |
| `draft_system` [IMPORTANT — 출력 형식] (규칙 재인용 방지 지시) | `config/prompts.yaml` | 127-134 |
| `draft_user` 전체 문자열 (계획형 문구 포함) | `config/prompts.yaml` | 160 |
| temperature 설정 (chain_drafter 명시 인자 0.85 + models.yaml default 0.85) | `chain_drafter.py:368` / `5000/config/models.yaml:2-5` | — |
| raw 저장 후보 경로 gitignore 여부 | `.gitignore` | `output/`, `logs/` ignore됨 ✓ |

## 현재 테스트 기준선

- `pytest --co -q`: **828 tests collected** (실측, 2026-08-01)
  - 참고: 지시문의 "현재 819"와 상이 → **실측 828을 베이스라인으로 사용** (분해: 828 = phase-33 시점 792 + 이후 신규 테스트 누적)

## 개선 방향 (합의됨 — C→A→B 순서)

### C. 관측 강화 (최우선)
- 초안 생성 시 `raw_output`(정제 전 AI 원문)을 **파일 + DB 컬럼**으로 보존.
- 저장 위치: `output/drafts/{chain_id}/step-{N}-{slug}.raw.md` (output/는 gitignore라 커밋 미오염) + `chain_posts.raw_ai_output` 컬럼(마이그레이션, nullable).
- 보존 기간: 발행 성공 후에도 유지 (재발 분석용). 용량: 1회 생성 ~6KB, 일 10체인 가정 시 ~180KB/일 — 무시 가능.

### A. 프롬프트 수정 (근본 — 유발 요인 저감)
- `draft_system` [IMPORTANT]에 "계획·검토·규칙 재인용·자가 지시·'피하자/주의:' 같은 메타 대화를 출력하지 말 것. **출력은 완성된 글 본문만**" 명시 (diff 형태로 PLAN에 제시).
- `draft_user`의 계획형 문구("변형하세요", "구체화하고", "그대로 복사하지 말고" 등) 축소 검토 — 실행 요구 문구는 유지, 메타 대화 유발 표현만 조정.
- temperature 0.85 → 0.7 하향: `chain_drafter.py:368` 명시 인자 + `models.yaml` default tier 둘 다.

### B. leak_defense 문단 단위 안전망 (안전망 — 오탐 최소화)
- 현재 `remove_paragraph`: "매칭 라인 → 다음 빈 줄" 제거 → **문단 중간 삽입 미제거**.
- 개선: 고특이도 패턴에 한정해 **"시그니처 포함 문단 전체 제거"** 추가.
  - 단독 사용 금지(오탐 위험): `주의:`, `표 N:` — 단독으로는 문단 삭제 금지.
  - 고특이도(메타 대화 특유): `프롬프트에서는`, `프롬프트는 …라고 했`, `금지어:`, `피하자`, `만들지 말 것`, `이미지 플레이스홀더`, `제공된 참고 자료`.
  - 또는 "메타 대화 신호 2개 이상 동시 출현" 시에만 문단 삭제.
- **발행 safety net(`context="body"`)에만 적용**, 초안 저장(`context="draft"`)에는 미적용 → 2단계 정제(원문 보존 + 발행 전 방어).

## 별도 이슈 (이번 범위 밖 — 기록만)

- **카테고리 불일치**: `classify_keyword('뉴발란스 740')` → `etc` vs DB `category_guess='쇼핑/소비'`. derive 단계와 draft 단계의 분류가 불일치. 이번 PLAN 범위에서 제외하고, 이후 별도 이슈로 추적.

## 수정 범위 제약

- **코드·설정·프롬프트 파일 수정은 PLAN 승인 후에만**. 본 CONTEXT/PLAN 작성 단계에서는 read-only 조사만 수행.
- 발행·배포·DB 쓰기 금지.
- 실행 방법 불명확 시 계획서에 "확인 필요"로 명시.

## 검증 계획 (PLAN에 반영)

1. 재현 테스트를 `use_context=True`(검색 컨텍스트 有)로도 수행 — 이전 진단은 `use_context=False`였음. 컨텍스트 유무에 따른 발현률 차이 확인.
2. A 적용만으로 발현률이 충분히 떨어지는지 측정 후 B 공격성 조절(과도한 문단 삭제 방지).
3. 오탐 회귀: 정상 본문에 `주의:`/`표 N:` 포함된 케이스가 보존되는지.
4. pytest 베이스라인: 828 (실측) → 신규 테스트 반영 후 총 개수 재실측.
5. 기존 8종 시그니처 스캔(`프롬프트`/`LLM 구축`/`금지어`/`구성안`/`Wait,`/`구조:`/`Let me|I need`/`image_type`) 회귀 유지.
