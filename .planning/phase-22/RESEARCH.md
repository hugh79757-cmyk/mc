# RESEARCH.md — Phase 22: 콘텐츠 품질 제어

**Phase:** 22  
**Date:** 2026-07-26  
**Status:** Research Complete

---

## 1. 현재 초안 검증 로직 (`_validate_draft_schema`)

**파일:** `chain_drafter.py` (line 514-568)

**현황:**
- H2 헤딩 최소 1개 검증
- 이미지 마커 (`<!--todo:image-->` 또는 `<!--todo:chart-->`) 존재 검증
- 차트 마커가 아닐 때 `meta.image_keyword` 비어있지 않음 검증
- Frontmatter 필수 필드 검증: `title`, `description`, `tags`, `categories`

**문제점:**
- 글자수 제한 검증 없음 (prompts.yaml에 2500자 명시되어 있으나 검증 안 함)
- 한글/영문 혼합 글자수 측정 로직 없음
- 마크다운 문법, frontmatter, 이미지 마커 제외 순수 본문 글자수 계산 로직 없음

---

## 2. 현재 Sanitize/Leak Defense 로직

### 2.1 `_strip_prompt_leak` (`chain_drafter.py:384-433`)
- Frontmatter 경계 추적 (--- 마커)
- 프롬프트 릭 패턴 매칭 시 전체 섹션 블록 제거
- 하드코딩된 패턴: `_PROMPT_LEAK_RE` (regex 컴파일)

### 2.2 `_sanitize_markdown_body` / `_extract_clean_body` (`chain_publisher_core.py:38-146`)
- 화이트리스트 방식: 유효한 마크다운 요소만 추출
- 허용: ATX 헤딩, 단락, 리스트, 표, 코드 펜스(비JSON), 이미지, 링크
- 거부: HTML 주석, `<meta>/<script>/<div>`, raw JSON, CTA 블록
- CTA leak 패턴 (`_cta_leak_patterns`)은 배포 시점(D8-GATE)에서 별도 스캔

### 2.3 `_clean_markdown_symbols` (`chain_publisher_core.py:1020-1085`)
- 코드 블록, 수식 블록, 테이블, 이미지 마커 보호
- 루즈 파이프(`|`) 이스케이프
- CJK 볼드/이탤릭 스페이싱 수정
- 고아 마크다운 딜리미터 정리

### 2.4 D8-GATE CTA/Placeholder Leak Scanner (`chain_publisher_core.py:622-647`)
- CTA leak 패턴 10개: "더 알아보기", "더 깊이 알아보기", "계속 읽기", "관련 주제", "아래 버튼", "링크를 클릭", "관련 글", "시리즈 보기", "이 시리즈 보기", "전체 글 모아보기", "모아보기"
- 플레이스홀더 leak: `{{...}}` 패턴 (shortcode `{{< >}}` 제외)
- 자동 제거 후 경고 로깅

### 2.5 Audit Module (`audit/audit_chain.py:85-132`)
- `check_prompt_leak`: 14개 패턴 (`# Role`, `# SEO 기본 원칙`, `## 서론` 등)
- `check_cta_leak`: 4개 패턴 (`더 깊이 알아보기`, `더 자세히 보기`, `이어서 실전 적용법`, `관련 주제 보기`)

### 2.6 Conftest Test Helpers
- `assert_no_prompt_leak`: 8개 패턴
- `assert_no_cta_leak`: 4개 패턴
- `assert_no_unresolved_markers`: 6개 패턴

**문제점:**
- 동일한 성격의 방어 패턴이 4개 파일에 중복 분산
- `chain_drafter.py`, `chain_publisher_core.py`, `audit/audit_chain.py`, `conftest.py` 각각 별도 리스트 관리
- 통합 관리 모듈 없음

---

## 3. 현재 Prompts.yaml 구조 (글자수 제한, Persona)

**파일:** `config/prompts.yaml`

**글자수 관련:**
- `draft_system`: "전체 글자수: 2,500자 이상 3,500자 이하 (공백 포함)" — 하드코딩된 문자열
- `draft_user`: 구조 가이드라인만 있고 구체적 글자수 검증 로직 없음

**Persona 관련:**
- `derive_system`: "당신은 SEO 전문 콘텐츠 기획자입니다"
- `draft_system`: "당신은 IT·기술·라이프스타일 분야를 아우르는 전문 콘텐츠 에디터입니다. 10년 경력의 디지털 저널리스트로서..."
- 사이트별/Depth별 persona 분기 없음 (rotcha/issue.techpawz/techpawz 모두 동일 프롬프트 사용)

**CTA 관련:**
- `draft_user`: "[CTA GUIDELINES — prompt leak 금지]" 섹션에서 "더 알아보기 →" 문구 직접 쓰지 말 것 지시

---

## 4. CTA 관련 설계 문서 (Phase 17)

**파일:** `.planning/phase-17/CTA-SCENARIO.md`, `.planning/phase-17/PLAN.md`

**핵심 설계 (v2 확정):**
- **단일 CTA 문구:** "더 알아보기 →"로 통일 (빨간 배경 #DC2626 / 흰 글씨)
- **카테고리 차이는 링크 목적지로만 분기** (문구 차이 없음)
- `chain-card` (내부이동): 다음 step 포스트 URL
- `hub CTA` (`{{ENTRY_LINK}}`): `rotcha.kr/hub/{slug}`
- 듀얼 CTA 전환성: 폐기 (애드센스 모델에서 목적지 없음)
- 금지 표현: "지금 구매하세요", "한정 수량", "최저가 보장", "지금 매수", "오늘 계약", "아래 버튼", "링크를 클릭"

**`config/prompts.yaml`에 이미 반영된 `keyword_categories.cta_phrases`:**
```yaml
travel:
  cta_phrases:
    next_post: "더 알아보기 →"
    entry_funnel: "{{ENTRY_LINK}}"
    fallback: "관련 주제 보기 →"
# real_estate, automotive, stock, etc 동일 구조
```

**주입 구조:**
- `chain_card_injector.py:227` `get_cta(blog_key, direction)` — 현재 `card_cta`에서 direction별 고정 문구 반환
- `DualCTAInjector` — 듀얼 CTA 주입 (info + conv, 현재 conv는 dead link)
- 플레이스홀더 `{{ENTRY_LINK}}` 발행 시 hub URL로 치환

---

## 5. Frontmatter 생성 코드 현황

**파일:** `chain_publisher_core.py` (`_publish_hugo`, `_write_hugo_post`)

**현황:**
- Frontmatter 필수 필드: `title`, `description`, `tags`, `categories`, `draft: false`, `featureimage`
- `description`: AI가 생성한 meta description (150자 이내) 포함
- `featureimage`: R2 썸네일 URL (og:image용)
- `description` 필드 검증: `_verify_before_deploy`에서 빈 값/상대경로 시 에러

**문제점:**
- `description` 필드에 AI 생성 메타 설명이 포함되나, 150자 제한 강제 검증 없음
- 이미지 마크다운에 `alt` 텍스트 자동 추가 로직 없음 (비어있는 경우 많음)

---

## 6. Leak Defense 패턴 현황 통합

### 분산 위치별 패턴 수:

| 파일/모듈 | Prompt Leak 패턴 | CTA Leak 패턴 | Placeholder Leak |
|-----------|------------------|---------------|------------------|
| `chain_drafter.py::_strip_prompt_leak` | `_PROMPT_LEAK_RE` (복합 regex) | - | - |
| `chain_publisher_core.py` (D8-GATE) | - | 10개 (`더 알아보기` 등) | `{{...}}` regex |
| `audit/audit_chain.py` | 14개 리스트 | 4개 리스트 | - |
| `conftest.py` | 8개 리스트 | 4개 리스트 | 6개 리스트 |

### 중복/충돌:
- "더 알아보기" 계열: D8-GATE 10개, audit 4개, conftest 4개 — 겹침 있으나 미세하게 다름
- 프롬프트 릭: chain_drafter는 regex 기반 블록 제거, audit/conftest는 단순 문자열 포함 검사

---

## 7. 결론 및 Phase 22 설계 방향

### Task 1: 글자수 기준 정립 + 검증 게이트
- `prompts.yaml`의 `keyword_categories`에 `char_count` 필드 추가 (site×depth별)
- 순수 본문 글자수 측정 함수 작성 (frontmatter, 마크다운 문법, 이미지 마커 제외)
- `_validate_draft_schema`에 글자수 검증 추가 → 미달 시 warning + `quality_warning: "undercount"` 플래그

### Task 2: CTA 코드화
- Phase 17 설계(`CTA-SCENARIO.md`) 기반 `config/cta_templates.yaml` 또는 기존 config 통합
- `get_cta(category, depth, next_url)` 함수 작성
- `_sanitize_markdown_body` / D8-GATE에 AI 생성 CTA 감지/제거 + 공식 CTA 교체 로직 추가
- 최종 마크다운에 CTA 블록 정확히 1개 존재 검증 assert 추가

### Task 3: 릭 방어 패턴 통합 + SEO 메타 보강
- `config/leak_defense.yaml` 또는 `mc/leak_defense.py` 생성 — 모든 blocklist/regex 통합
- `strip_leaks(text) -> cleaned_text` 단일 함수 제공
- 기존 4개 파일의 개별 leak 방어 호출을 이 함수로 교체
- Frontmatter `description` 150자 제한 강제 + 이미지 `alt` 텍스트 자동 추가

---

## References

- `chain_drafter.py` lines 384-433, 514-568
- `chain_publisher_core.py` lines 38-146, 622-647, 1020-1085
- `audit/audit_chain.py` lines 85-132
- `conftest.py` lines 367-405
- `config/prompts.yaml` (`keyword_categories`, `draft_system`, `draft_user`)
- `.planning/phase-17/CTA-SCENARIO.md`
- `.planning/phase-17/PLAN.md`