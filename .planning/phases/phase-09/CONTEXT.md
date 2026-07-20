# Phase 9 Context: Publish Quality Fix

## Goal

발행 품질 3대 결함(프롬프트 릭, 이미지 미삽입, 썸네일 가독성)을 일괄 수정하여 모든 발행 글이 깔끔하게 렌더링되도록 한다.

## Problem Summary

| 이슈 | 심각도 | 영향 범위 |
|------|--------|----------|
| 프롬프트 릭 | CRITICAL | 3개 사이트 전체 발행 글 |
| 이미지 미삽입 | CRITICAL | 15개 파일, 31개 미해소 마커 |
| 썸네일 가독성 | HIGH | 모든 썸네일 이미지 |

## Root Causes (분석 완료)

### 프롬프트 릭 — 5가지 경로
1. `_strip_prompt_leak()`가 frontmatter 이후 프롬프트 헤더를 제거하지 못함 (skip 플래그 버그)
2. `_sanitize_markdown_body()`가 이미지 교체 전에 플레이스홀더를 삭제 (실행 순서 오류)
3. `draft_user` 템플릿의 `<!-- thumbnail/image -->` 마커가 `_PROMPT_LEAK_RE`에 없음
4. publisher에 프롬프트 헤더 제거 필터 없음
5. `draft_single_post()` 들여쓰기 오류 (lines 257-260)

### 이미지 미삽입 — 5가지 경로
1. `_sanitize_markdown_body()`가 마커를 먼저 삭제 → 치환 코드가 매칭할 대상 없음
2. `<!-- thumbnail: keyword -->` 마커를 처리하는 코드가 시스템 어디에도 없음
3. content image 부재 시 마커 치환 자체가 스킵됨
4. R2 업로드 실패 시 모든 이미지 누락
5. `injector.py`가 발행 파이프라인에서 호출되지 않음

### 썸네일 가독성 — 7가지 문제
1. 기본 폰트 48px 너무 작음 (권장: 56~64px)
2. `elif` 버그로 51자+ 제목 폰트 축소 안 됨
3. 텍스트가 이미지 하단 25%에만 몰림
4. 그림자 offset 너무 작음 (CJK 텍스트)
5. `_fit_text()`가 영한 혼합 텍스트에서 영어 단어를 중간에 끊음
6. Bold 폰트 파일 누락
7. config `bg_alpha` 미적용

## Locked Scope

- **In:** 프롬프트 릭 필터, 이미지 치환 순서, 썸네일 폰트/위치/그림자, 마커 처리 통일
- **Out:** 새 이미지 프로바이더 추가, 프롬프트 전면 재작성, Hugo 테마 변경

## Key Constraint

- 기존 발행 글은 소급 적용 불가 (이미 배포됨)
- 새 발행부터 적용되는 코드 수정만 수행
- `_sanitize_markdown_body()`의 실행 순서를 바꾸는 것이 핵심

## Files

- `chain_drafter.py` — `_strip_prompt_leak()` 재작성, 들여쓰기 수정
- `chain_publisher_core.py` — `_sanitize_markdown_body()` 실행 순서 수정, 마커 치환 로직 통일
- `image/thumbnail.py` — 폰트 크기, 위치, 그림자, `_fit_text()` 개선
- `config/prompts.yaml` — 이미지 마커 지시문 수정
- `config/chain_config.yaml` — 썸네일 설정 추가
