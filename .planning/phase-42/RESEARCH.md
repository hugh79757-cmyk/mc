# RESEARCH: Phase 42 — 제목-본문 정합성

## 기존 코드베이스 분석

### 1. 제목 생성 (chain_drafter.py)

`draft_single_post()`는 AI에게 제목+본문을 한번에 생성 요청. 제목은 frontmatter의 `title` 필드에 저장.

현재 제목 검증:
- `_validate_hugo_frontmatter_text()` (chain_publisher_core.py:45-55): `title` 필드 존재 +非空만 확인
- 제목-본문 정합성 검증 없음

### 2. H2 섹션 구조 (prompts.yaml)

`prompts.yaml`의 `keyword_categories`마다 `step1_sections`, `step2_sections`, `step3_sections` 정의:

```yaml
keyword_categories:
  travel:
    step1_sections:
      - "## {keyword} — 위치와 기본 정보"
      - "## 접근 방법과 교통"
      - "## 이용 정보와 요금"
    step2_sections:
      - "## {keyword} vs 대안 비교"
      ...
```

`audit_format.py`의 `_load_step_sections()`이 이 템플릿을 로드하고, `_extract_keyword_from_template()`으로 시맨틱 패턴 추출.

### 3. 형태소 분석 없이 키워드 추출

PLAN.md에서 "형태소 분석 없이 간단한 패턴 매칭" 지시. 한국어 제목 정규화:
- 공백·특수문자 무시
- 명사구 추출: 형태소 분석기(KoNLPy) 없이 `re.split(r'[\s·\-—|]', title)`로 토큰 분리
- 불용어 제거: "가이드", "추천", "Best", "총정리" 등 일반적 수식어 제외

### 4. 본문 키워드 출현 검사

기존 `audit_format.py`의 H2 매칭 로직 재사용:
- `_extract_keyword_from_template()`이 `{keyword}`를 제거한 시맨틱 패턴 반환
- 본문에서 해당 패턴 포함 H2 존재 여부 확인

## 통합 지점

1. **title_body_checker.py**: `title_body_consistency(post_md) -> TitleBodyResult`
2. **quality_gate.py**: `validate_title_body(post_md) -> GateResult` 래퍼
3. **audit_format.py**: `_load_step_sections()` 재사용 — H2 템플릿과 실제 본문 매칭

## 리스크

- 형태소 분석 없이 키워드 매칭하면 오탐 가능 → 관대한 기준 시작 (최소 2회 출현)
- 한글 제목의 복합어 분리 어려움 → 공백/특수문자 기준 분리

## 권장 사항

1. 제목에서 핵심 키워드 추출: `re.split(r'[\s·\-—|]', title)` → 불용어 제거 → 남은 토큰
2. 본문 H2/H3에서 해당 토큰 존재 확인
3. 점수 산출: (매칭된 H2/H3 수) / (전체 H2/H3 수) — 0.0~1.0
4. 기준: 점수 0.3미만 = 위반 (관대하게 시작)
