# RESEARCH: Phase 43 — 사실 기반 필터

## 기존 코드베이스 분석

### 1. 릭 방어 파이프라인 (mc/leak_defense.py)

기존 `strip_leaks(body, context)` 함수:
- `prompt_leak`: 프롬프트 섹션 헤더 탐지 → 블록 단위 제거
- `reasoning_leak`: AI 사고과정 탐지 → 저특이도(2신호 동시) / 초고특이도(1개만) 문단 제거
- `cta_leak`: AI 생성 CTA 블록 탐지

`config/leak_defense.yaml`의 패턴 구조:
- `patterns`: 정규식 리스트
- `min_signals`: 동시 출현 신호 수
- `ultra_high_signals`: 1개만으로도 차단
- `action`: "remove_block"

### 2. Chain 10063 사건 분석

`.planning/triage/20260817--chain-10063-root-cause-plan.md`에서:
- "가격 확인 없이 최저가로 단정" — 사실 기반 필터 부재가 근본 원인
- AI가 자체 지식에 의존해 미확인 사실 주장을 생성

### 3. 기존 factuality 관련 코드

현재 사실성 검증 없음. 다음에서 관련 패턴 발견:
- `audit_chain.py` `check_content_by_whitelist()`: HTML 태그/JSON 탐지 (사실성 무관)
- `chain_drafter.py` `_strip_prompt_leak()`: 프롬프트 릭만 처리

### 4. 한국어 사실 주장 패턴

영어와 다른 한국어 특성:
- "최저가", "~원", "~만원" — 가격 단정
- "100% 자연산", "유일한", "가장 인기" — 과대 표현
- "~에 따르면", "~기준" — 출처 표시 (긍정 패턴)
- "관련 공식 사이트에서 확인 가능" — 간접 출처 (부분 긍정)

## 통합 지점

1. **factuality_checker.py**: `check_factuality(body) -> FactualityResult`
2. **config/factuality_patterns.yaml`: 금지 패턴 + 긍정 패턴 정의
3. **leak_defense.py 연동**: `strip_leaks()` 호출 후 factuality 검증 추가
4. **quality_gate.py**: `validate_factuality(post_md) -> GateResult`

## 리스크

- 한국어 사실 주장 패턴이 영어와 다름 → 한국어 특화 패턴 필요
- 과도한 필터링으로 유효한 콘텐츠 차단 → 관대한 기준 시작
- "최저가"가 사실인 경우도 있음 (예: 공식 최저가 확인 가능) → 출처 있으면 통과

## 권장 사항

1. 금지 패턴: `최저가`, `100%`, `가장`, `유일한`, `검증된` — 출처 없이 단정 시 위반
2. 긍정 패턴: `~에 따르면`, `~기준`, `~확인`, `공식 사이트` — 출처 표시 시 통과
3. factuality 스코어: (출처 포함 사실 주장) / (전체 사실 주장)
4. 기준: 스코어 0.7미만 = 위반
