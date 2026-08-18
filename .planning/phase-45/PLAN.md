# Phase 45: HTML 렌더링 중복 검사

**Milestone:** M3 — 9점 품질 달성
**Goal:** Hugo 빌드 후 HTML에서 중복 문단, 이미지, 카드가 존재하는지 검증.

## Why

Markdown에서 보이지 않는 중복이 HTML 렌더링 후 발생. 예: 동일 이미지가2번 삽입, chain-card shortcode 중복 렌더링, CTA 블록 반복. 사용자 경험 저하 + AdSense 정책 위반 가능.

## Plan

### W1: html_render_checker.py

- Hugo 빌드 후 HTML 파싱 (BeautifulSoup 또는 정규식)
- 중복 문단 탐지: 동일 텍스트가2회 이상 반복
- 중복 이미지 탐지: 동일 src가2회 이상
- 중복 카드 탐지: chain-card shortcode가 의도보다 많이 렌더링

### W2: 카드/CTA 렌더링 검증

- `chain-card`, `chain-official-card`, `dual-cta` shortcode 정상 렌더링 확인
- 카드 내부 링크 유효성 (broken link 검사)
- CTA 텍스트 존재 확인 (빈 CTA 차단)

### W3: 기존 audit_format.py 연동

- Phase 29의 `audit_format.py` 검증 항목과 통합
- `check_card_count`, `check_card_placement` 재사용
- 중복 검사를 기존 audit 체계에 추가

### W4: 게이트 통합 + pytest

- `quality_gate.py`에 렌더링 검증 추가
- 중복 없는 정상 HTML (통과)
- 중복 포함 HTML (위반)
- pytest 녹색 유지

## Dependencies

- Phase 41 (quality_gate.py)
- 기존 `audit/audit_format.py` (Phase 29)
- 기존 `html_renderer.py`

## Risks

- BeautifulSoup 의존성 추가 → 기존 의존성 목록 확인 필요
- Hugo 빌드 없이 HTML 검증 불가 → 빌드 후 검증 파이프라인 연결
