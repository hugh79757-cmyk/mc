---
date: 2026-07-30
type: refactor
status: resolved
---

# Phase 24: YAML Frontmatter Structural Fix + 외부 링크 카드 CTA 동적화

## What
두 가지 변경:
1. **FM 분리** — AI가 YAML frontmatter를 직접 생성하지 않도록 구조 변경. FM은 `_build_frontmatter()`가 코드에서 조립.
2. **외부 링크 카드 CTA 동적화** — 공식 사이트 카드의 "바로가기 →" 버튼 문구에 검색 결과 사이트명(title) 포함.

## Why
1. AI가 생성한 FM 필드(title/tags/categories)는 발행 시 전부 무시되고 DB 값으로 대체됨 → FM 생성은 토큰 낭비 + FM 누수 버그 원인.
2. 모든 공식 사이트 카드가 동일한 "바로가기 →" 문구를 사용 → 맥락에 맞게 "인천항 여객터미널 바로가기 →" 식으로 표시되어야 UX 개선.

## Files changed
- `config/prompts.yaml` — `[Frontmatter — 필수]` 섹션 제거, `[IMPORTANT — 출력 형식]` 신규 섹션 추가
- `chain_drafter.py` — `_build_frontmatter()` + `_extract_description()` 신규; `_ensure_frontmatter()` 91→23라인 단순화; `draft_chain()` FM 조립 순서 변경
- `chain_models.py` — `_extract_body_from_raw()`에 AI FM 블록 선제 제거 로직 추가
- `test_chain_drafter.py` — mock 3건 body-only AI 출력으로 업데이트; 신규 테스트 16개 (TestBuildFrontmatter, TestExtractDescription, TestEnsureFrontmatterPhase24, FM strip)
- `chain_card_injector.py` — `build_external_link_card()` CTA 문구: `"바로가기 →"` → `f'{title} 바로가기 →'`

## How
1. 프롬프트에서 FM 관련 지시 제거 → AI는 body만 생성
2. `_build_frontmatter()`가 post dict + body → 완전한 Hugo 마크다운 조립 (featureimage 포함)
3. `_extract_description()`가 body 첫 문장에서 description 추출 (150자 제한)
4. `_ensure_frontmatter()`는 순수 안전장치(safety net)로만 유지
5. `_extract_body_from_raw()`가 AI가 지시 무시하고 출력한 FM 블록을 제거
6. 외부 링크 카드의 `primary` dict에 있는 `title` 필드를 CTA 버튼 텍스트에 포함

## Verification
- 378/378 pytest 통과 (기존 362 + 신규 16)
- `_ensure_frontmatter()` 23라인 확인 (91→75% 감소)
- card injector 테스트 48/48, audit_format 47/47 통과
- D9 중복제거 정규식/audit 정규식 모두 "바로가기 →" 포함 유지되어 영향 없음
