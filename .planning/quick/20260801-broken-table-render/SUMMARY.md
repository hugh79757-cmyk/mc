---
date: 2026-08-01
type: bugfix
status: resolved
scope: issue-techpawz-hugo / techpawz-hugo / rotcha-blog + mc 발행 파이프라인
---

# Quick 20260801: 마크다운 표 separator 누락으로 인한 표 렌더링 깨짐 수정 + 재발 방지

## What
사용자 보고: issue.techpawz.com 게시글(알프스대영CC 예약·요금)에서 표가 깨져 보임.
원인 파악 후 3개 사이트의 깨진 표 9건을 수정하고, 발행 파이프라인에
표 separator 자동 보정(`fix_tables`)을 추가해 재발을 방지했다.

## Why (근본 원인)
1. `chain_drafter`가 생성한 AI 초안에서 마크다운 표의 **header 행 바로 아래에
   separator 행(`| --- | --- |`)을 누락**하고 데이터 행을 붙임.
2. Hugo goldmark는 GFM 규격상 header + separator 구조가 아니면 `<table>`이 아닌
   `<p>`(일반 텍스트)로 렌더링 → 표가 깨져 보임.
3. 사용자 보고의 알프스대영CC 표가 정확히 이 패턴 (원본 초안
   `output/drafts/296/step-2-알프스대영cc-20260731-s2.md` L22에서 확인).

## 진단 (전수 스캔)
- 4개 사이트 content/posts 전체 스캔 (3676개 md) — 판정 로직은 "연속 | 행 run의
  두 번째 줄이 separator가 아니면 깨진 표" + "header 단독 잘린 표(bare |)".
- 초기 rough 스캔(48/24/217건)은 오탐 — header+separator가 정상인 표를
  "데이터 행 연속"으로 오판. 재작성한 스캐너로 확정.

| 사이트 | 깨진 표 | 비고 |
|--------|--------|------|
| issue-techpawz-hugo | 4 | 알프스대영CC(separator 누락), 무직자/건강보험(빈 표), 농지대장(Q&A 행) |
| techpawz-hugo | 1 | 프리랜서-고유가(빈 표) |
| rotcha-blog | 4 | 설비보전/건축도장(표 header 분실), 고유가-인천/고물가(빈 표) |
| informationhot-hugo | 0 | 해당 없음 |

## How (수정)
1. **issue-techpawz-hugo (4건)**
   - `알프스대영cc-20260731-s2/index.md` — header 다음 separator 행 `|---|---|---|` 추가 (데이터 6행 보존)
   - `무직자-소액대출…/index.md` — header 단독 빈 표 제거 (데이터 생성 안 됨)
   - `건강보험-환급금…/index.md` — header 단독 빈 표 제거
   - `농지대장…/index.md` — Q1/A 실제 콘텐츠를 유효한 2열 표(`질문`/`답변`)로 변환
2. **techpawz-hugo (1건)** — `프리랜서-고유가…/index.md` header 단독 빈 표 제거
3. **rotcha-blog (4건)**
   - `설비보전기능사…/index.md` — 데이터 행 앞의 mangled separator(`---|…|`)를
     표준 header(`연도|필기|실기`) + separator로 복원
   - `건축도장기능사…/index.md` — 동일 패턴, header(`구분|일정`) + separator 복원
   - `고유가-피해지원금-인천…/index.md` — header 단독 빈 표 제거
   - `고물가…/index.md` — header 단독 빈 표 제거

## 재발 방지 (파이프라인)
1. **`markdown_processor.py`** — `MarkdownProcessor.fix_tables()` 신설:
   - header 다음 데이터 행이 바로 오면 separator 행 삽입 (run 단위, 1회만)
   - header 단독 + bare pipe 잘린 표는 제거
   - 코드 펜스 내부 보호
   - `clean_symbols()` 진입 시 자동 적용 → Hugo/Blogger 발행 경로
     (`_clean_markdown_symbols`, `_sanitize_markdown_body`) 모두 커버
2. **`config/prompts.yaml`** — 표 작성 규칙 강화: "header → 구분선(| --- | --- |) →
   데이터 행 3줄 구조 필수, 열 개수 일치" 지시 추가 (AI 초안 단계에서 방지)

## Verification
- **렌더링 검증:** 3개 사이트 `hugo --gc --minify` 재빌드 후
  수정 4건 모두 `<table>` 렌더링 확인 (`<th>구분</th>`, `<th>연도</th>`, `<th>질문</th>` 등).
  제거 5건은 잔존 `|` 텍스트 없음 확인.
- **스캔 재실행:** 4개 사이트 0 broken 확인.
- **pytest:** 762/762 통과 = 754(기존) + 8(신규 TestFixTables).
  `test_markdown_processor.py` 33/33.
- **파이프라인 E2E:** 실제 알프스대영 초안 → `_sanitize_markdown_body()` 통과 시
  separator 자동 삽입 확인. 빈 표 제거 확인.

## Files changed
- 발행 사이트: issue-techpawz-hugo 4개, techpawz-hugo 1개, rotcha-blog 4개 content/posts md
- `markdown_processor.py` — `fix_tables()` + `_classify_table_line()` 신설
- `test_markdown_processor.py` — TestFixTables 8건 신설
- `config/prompts.yaml` — 표 3줄 구조 지시 추가
- `chain_publisher_core.py` — docstring 갱신 (동작 변경 없음)

## Residual Risk
- rotcha 사례처럼 **header가 아예 분실**된 mangled 표(`---|…|` + 데이터 행)는
  `fix_tables`가 복원하지 못함 (header 내용을 추론할 수 없음). 이번엔 수동 복원.
  향후 AI 초안 단계의 3줄 구조 지시로 예방.
- 빈 표 제거 시 섹션 헤더는 유지됨 (제거는 표 라인만).
