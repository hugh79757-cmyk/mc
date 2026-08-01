# PLAN.md — Phase 32: 연도 오류 방지 시스템

**Phase:** 32
**기반:** CONTEXT.md (조사 완료)
**현재 테스트:** 764개 (`pytest --co -q` 실측)

---

## 목표

mc 파이프라인에서 과거 연도 + '최신/기준/현재' 조합으로 인한 연도 오류를 3겹 방어로 차단.
- 소스 데이터에서 오는 과거 연도는 '최신/기준' 문맥에서만 현재 연도로 치환
- LLM 생성본에서 과거 연도 + 최신/기준/현재 조합은 자동 치환
- 카드 문구의 연도는 항상 현재 연도

**핵심 원칙:** 사실 날짜(축제 개최일, 이벤트 기간 등)는 절대 변경하지 않음.

---

## 공통 유틸 설계: `year_guard.py` (신규 모듈)

### 함수 시그니처

```python
from datetime import datetime

def validate_and_fix_years(
    text: str,
    allowed_years: set[int] | None = None,
    current_year: int | None = None,
    fix_mode: bool = True,
) -> tuple[str, list[str]]:
    """텍스트에서 연도를 검증하고 필요 시 치환.

    Args:
        text: 검증할 마크다운 텍스트
        allowed_years: 허용 연도 목록. None이면 {현재 연도}만 허용
        current_year: 기준 연도. None이면 datetime.now().year
        fix_mode: True면 '과거연도+최신/기준/현재' 패턴을 현재 연도로 자동 치환.
                  False면 플래그만 반환 (치환 없음).

    Returns:
        (처리된 텍스트, 경고 메시지 리스트)
        fix_mode=True: 치환된 텍스트 + 변경 로그
        fix_mode=False: 원본 텍스트 + 경고 로그
    """
```

### 허용 목록 산출 방식

```python
def build_allowed_years(source_years: set[int] | None = None) -> set[int]:
    """허용 연도 목록 생성.

    Args:
        source_years: 소스 데이터에서 추출한 연도 목록 (TourAPI/DB 등)
                      None이면 빈 세트

    Returns:
        {현재 연도} ∪ source_years
    """
    current = datetime.now().year
    allowed = {current}
    if source_years:
        allowed.update(source_years)
    return allowed
```

### 자동 치환 규칙 (정규식)

```python
import re

# 패턴 1: 과거 연도 + '최신/기준/현재' → 현재 연도로 치환
# 예: "2025 최신 정보" → "2026 최신 정보"
PATTERN_YEAR_WITH_CONTEXT = re.compile(
    r'(20\d{2})\s*(최신|기준|현재)'
)

# 패턴 2: '최신/기준/현재' + 과거 연도 → 현재 연도로 치환
# 예: "최신 2025년 정보" → "최신 2026년 정보"
PATTERN_CONTEXT_WITH_YEAR = re.compile(
    r'(최신|기준|현재)\s*(20\d{2})\s*년?'
)

# 패턴 3: standalone 과거 연도 (최신/기준/현재 없음) → 플래그만 (치환 안 함)
# 예: "2025년 축제" → 사실 정보이므로 보호
PATTERN_STANDALONE_YEAR = re.compile(r'(20\d{2})\s*년?')
```

### 자동 치환 규칙 상세

| 패턴 | 예시 | 처리 |
|------|------|------|
| `20\d{2}\s*(최신\|기준\|현재)` | "2025 최신 정보" | **치환**: 현재 연도로 교체 |
| `(최신\|기준\|현재)\s*20\d{2}년?` | "최신 2025년 트렌드" | **치환**: 현재 연도로 교체 |
| `20\d{2}년?\s*(축제\|개최\|행사\|기간\|일정)` | "2025년 축제 개최" | **보호**: 사실 날짜이므로 변경 안 함 |
| `20\d{2}년?\s*(부터\|까지\|이후\|전까지)` | "2025년부터 적용" | **보호**: 사실 기간이므로 변경 안 함 |
| standalone `20\d{2}` | "2024년 매출" | **허용 목록 확인**: 허용 목록에 있으면 통과, 없으면 경고 |

### 사실 날짜 보호 규칙

```python
# 사실 날짜 보호 패턴 — 이 패턴이 매칭되면 치환하지 않음
FACTUAL_DATE_PATTERNS = [
    r'20\d{2}년?\s*(축제|개최|행사|기간|일정|운영|개장|폐장)',  # 이벤트 날짜
    r'20\d{2}년?\s*(부터|까지|이후|전까지|중)',                   # 기간 표현
    r'20\d{2}년?\s*\d{1,2}월',                                    # 구체적 월
    r'20\d{2}년?\s*\d{1,2}월\s*\d{1,2}일',                       # 구체적 일
]
```

---

## 적용 지점 매핑

### 1차 적용: 입력단 — 소스 데이터 보정

**지점:** `chain_drafter.py` line 283-290 (`retrieve_context_for_post()` 이후)

```python
# 현재:
ok, ctx = retrieve_context_for_post(...)
user_prompt += "\n\n" + ctx

# 변경 후:
ok, ctx = retrieve_context_for_post(...)
ctx, _year_warnings = validate_and_fix_years(ctx, fix_mode=True)
user_prompt += "\n\n" + ctx
```

### 2차 적용: 생성단 — 프롬프트 지시

**지점:** `config/prompts.yaml` line 157 (`draft_user` 템플릿)

기존 `[TRAVEL GROUNDING]` 블록 아래에 추가:

```yaml
[YEAR ACCURACY — 연도 정확성 지시]
- '2025 최신 정보', '2024년 기준', '2023년 현재' 등 과거 연도와 '최신/기준/현재' 조합을 절대 사용하지 마세요.
- '최신', '기준', '현재'를 표현할 때는 항상 올해 연도({current_year})를 사용하세요.
- 축제 개최일, 이벤트 기간 등 실제 사실 기반 연도는 그대로 유지하세요.
- 검색 자료에 있는 과거 연도 데이터는 그대로 인용하되, '최신/기준/현재'와 조합하지 마세요.
```

### 3차 적용: 출력단 — 사후 검증/치환

#### 본문 파이프라인

**지점 1:** `chain_drafter.py` line 381 (`frontmatter_utils.build_frontmatter()` 직전)

```python
# FM 조립 전 본문 연도 검증
draft_md, _year_warnings = validate_and_fix_years(draft_md, fix_mode=True)
if _year_warnings:
    for w in _year_warnings:
        print(f"  [drafter] ⚠️ 연도 경고: {w}")
```

**지점 2:** `chain_publisher_core.py` line 1065 (`_sanitize_markdown_body()` 내부)

`markdown_processor.py`의 `process()` 메서드에 연도 검증 단계 추가:

```python
# 기존 process() 순서: fix_fences → strip_leaks → clean_symbols
# 변경 후: fix_fences → strip_leaks → **year_guard** → clean_symbols
```

#### 카드 문구 파이프라인

**지점:** `chain_card_injector.py` line 451 (`inject_cards_into_draft()` 종료 직전)

```python
# 카드 주입 후 최종 draft_md 연도 검증
draft_md, _year_warnings = validate_and_fix_years(draft_md, fix_mode=True)
```

---

## Task 분해

### Task 1: 백업

```bash
cp chain_drafter.py chain_drafter.py.bak
cp chain_publisher_core.py chain_publisher_core.py.bak
cp chain_card_injector.py chain_card_injector.py.bak
cp markdown_processor.py markdown_processor.py.bak
cp config/prompts.yaml config/prompts.yaml.bak
```

### Task 2: `year_guard.py` 신규 모듈 생성

- `validate_and_fix_years()` 함수 구현
- `build_allowed_years()` 함수 구현
- 정규식 패턴 3개 + 사실 날짜 보호 패턴 정의
- 단위 테스트: `test_year_guard.py`

### Task 3: 본문단 적용

- `chain_drafter.py` line 381: FM 조립 전 `validate_and_fix_years()` 호출
- `chain_publisher_core.py` `_sanitize_markdown_body()`: `markdown_processor.process()`에 year_guard 단계 삽입
- `chain_card_injector.py` `inject_cards_into_draft()`: 카드 주입 후 검증

### Task 4: 프롬프트 수정

- `config/prompts.yaml` line 157: `draft_user` 템플릿에 `[YEAR ACCURACY]` 블록 추가

### Task 5: 테스트 추가

- `test_year_guard.py`: 유틸 단위 테스트 (15건 이상)
  - "2025 최신정보" → 현재 연도 치환
  - "2025년 축제 개최" → 사실 날짜 보호
  - "2024년 기준 가격" → 현재 연도 치환
  - standalone "2024년 매출" → 허용 목록 확인
  - 허용 목록에 과거 연도 포함 시 통과
- `test_chain_drafter.py`: 본문 연도 검증 통합 테스트 (3건)
- `test_chain_publisher_core.py`: 연도 검증 통합 테스트 (3건)

### Task 6: 전체 테스트 실행 + 회귀 확인

```bash
python -m pytest -q
# 목표: 764 + 신규 테스트 수 만큼 통과, 회귀 없음
```

### Task 7: 검증 재현

| 시나리오 | 입력 | 기대 결과 |
|---------|------|----------|
| 과거연도+최신 | "2025 최신 정보입니다" | "2026 최신 정보입니다" |
| 과거연도+기준 | "2024년 기준 가격" | "2026년 기준 가격" |
| 사실 날짜 | "2025년 축제 개최" | "2025년 축제 개최" (변경 없음) |
| 허용 연도 | "2026년 신규 프로그램" | "2026년 신규 프로그램" (변경 없음) |
| 카드 라벨 | "2025년형 추천" | "2026년형 추천" |

---

## 리스크/롤백

| 리스크 | 영향 | 방지책 |
|--------|------|--------|
| 사실 날짜 오치환 | "2025년 축제" → "2026년 축제" | `FACTUAL_DATE_PATTERNS`로 보호. 패턴 누락 시 보수적 치환 (standalone 연도는 플래그만) |
| 허용 목록 누락 | 정상 연도가 경고 발생 | `build_allowed_years()`에서 소스 연도 명시적 전달. 테스트로 검증 |
| 프롬프트 변경으로 AI 품질 저하 | 초안 품질 변화 | `[YEAR ACCURACY]` 블록은 기존 블록 아래에 추가. 전체 프롬프트 구조 변경 없음 |

**백업/복구:** Task 1에서 `.bak` 파일 생성. 원복 시 `cp *.bak` 명령으로 즉시 복구 가능.

---

## 검증 기준

- [ ] `year_guard.py` 단위 테스트 15건 이상 통과
- [ ] 본문 연도 치환 테스트 통과
- [ ] 사실 날짜 보호 테스트 통과
- [ ] 카드 문구 연도 검증 테스트 통과
- [ ] 프롬프트 `[YEAR ACCURACY]` 블록 추가 확인
- [ ] 전체 테스트 764 + 신규 테스트 수 통과 (회귀 없음)
- [ ] `.bak` 파일 5개만 생성
