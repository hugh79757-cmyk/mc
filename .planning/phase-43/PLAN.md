# Phase 43: 사실 기반 필터 (Factuality Filter)

**Milestone:** M3 — 9점 품질 달성
**Goal:** AI 생성 콘텐츠에서 사실 주장에 출처를 강제하고, 확인되지 않은 주장을 필터링.

## Why

AI가 사실인 것처럼 쓰지만 실제 확인되지 않은 주장을 생성. "최저가", "가장 인기", "100% 자연산" 등 근거 없는 단정이 문제. Phase 19의 terra-tomato 사례에서 "가격 확인 없이 최저가로 단정"이 발견됨.

## Plan

### W1: factuality_checker.py

- `source_tag` 필수 규칙: 인용·수치·사실 주장에 출처 명시 강제
- 금지 패턴: `최저가`, `100%`, `가장`, `유일한`, `검증된` 등 과대 표현
- factuality 스코어 산출: 출처가 있는 사실 주장 / 전체 사실 주장 비율

### W2: _strip_prompt_leak() 연동

- 기존 `chain_drafter.py::_strip_prompt_leak()` 패턴과 통합
- 프롬프트 릭 방어 + 사실 기반 필터를 하나의 파이프라인으로 묶기
- `config/leak_defense.yaml`의 기존 상수 재사용

### W3: 게이트 통합

- `quality_gate.py`에 사실성 검증 추가
- 기준: factuality 스코어 0.7미만 = 위반

### W4: pytest

- 출처 포함 콘텐츠 (통과)
- 미확인 단정 콘텐츠 (위반)
- 빈 콘텐츠 엣지 케이스

## Dependencies

- Phase 41 (quality_gate.py)
- 기존 `chain_drafter.py::_strip_prompt_leak()`
- 기존 `config/leak_defense.yaml`

## Risks

- 한국어 사실 주장 패턴이 영어와 다름 → 한국어 특화 패턴 필요
- 과도한 필터링으로 유효한 콘텐츠 차단 → 관대한 기준 시작
