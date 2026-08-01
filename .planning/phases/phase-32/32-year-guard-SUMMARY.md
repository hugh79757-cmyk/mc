---
phase: 32
plan: year-guard
subsystem: pipeline
tags: [year-guard, quality, defense-in-depth]
dependency:
  requires: []
  provides: [year_guard_util]
  affects: [chain_drafter, chain_publisher_core, chain_card_injector, markdown_processor, prompts]
tech-stack:
  added: [year_guard.py]
  patterns: [regex-validation, pipeline-interception]
key-files:
  created: [mc/year_guard.py, test_year_guard.py]
  modified: [chain_drafter.py, chain_card_injector.py, markdown_processor.py, config/prompts.yaml, test_chain_drafter.py, test_chain_publisher_core.py]
decisions:
  - "year_guard.py를 mc/ 디렉토리에 배치 (mc.leak_defense 패턴 준수)"
  - "사실 날짜 보호는 뒤쪽 컨텍스트만 확인 (앞쪽은 오검출 위험)"
  - "standalone 과거 연도는 플래그만, 치환은 최신/기준/현재 조합에 한정"
  - "markdown_processor.py 파이프라인에 year_guard 단계 삽입 (strip_leaks → year_guard → clean_symbols)"
metrics:
  duration: "~10min"
  completed: "2026-08-01"
---

# Phase 32 Plan: year-guard Summary

## 한 줄 요약
year_guard.py 유틸리티로 과거연도+최신/기준/현재 조합 자동 치환 + 사실 날짜 보호 3겹 방어 구현

## 변경 파일

| 파일 | 변경 유형 | 설명 |
|------|-----------|------|
| `mc/year_guard.py` | 신규 | 연도 검증/치환 유틸리티 (validate_and_fix_years, build_allowed_years) |
| `test_year_guard.py` | 신규 | 22건 단위테스트 |
| `chain_drafter.py` | 수정 | 입력단(ctx 보정) + 출력단(FM 조립 전 검증) |
| `chain_card_injector.py` | 수정 | 카드 주입 후 최종 draft_md 검증 |
| `markdown_processor.py` | 수정 | process() 파이프라인에 year_guard 단계 삽입 |
| `config/prompts.yaml` | 수정 | [YEAR ACCURACY] 블록 추가 |
| `test_chain_drafter.py` | 수정 | 3건 통합테스트 추가 |
| `test_chain_publisher_core.py` | 수정 | 3건 통합테스트 추가 |

## 테스트 결과

- **기존:** 764건
- **신규:** 28건 (단위 22 + 통합 6)
- **최종:** 792건 통과, 회귀 없음

## 3겹 방어 구현

1. **입력단 (1차):** `chain_drafter.py` — `retrieve_context_for_post()` 이후 `validate_and_fix_years(ctx)` 호출
2. **생성단 (2차):** `config/prompts.yaml` — `[YEAR ACCURACY]` 블록으로 LLM에 연도 정확성 지시
3. **출력단 (3차):** 
   - `chain_drafter.py` — FM 조립 전 본문 검증
   - `chain_card_injector.py` — 카드 주입 후 검증
   - `markdown_processor.py` — `process()` 파이프라인 통합 (strip_leaks → year_guard → clean_symbols)

## 검증 시나리오

| 시나리오 | 입력 | 기대 | 결과 |
|---------|------|------|------|
| 과거연도+최신 | "2025 최신 정보입니다" | "2026 최신 정보입니다" | ✅ 통과 |
| 과거연도+기준 | "2024년 기준 가격" | "2026년 기준 가격" | ✅ 통과 |
| 사실 날짜 | "2025년 축제 개최" | "2025년 축제 개최" | ✅ 통과 |
| 허용 연도 | "2026년 신규 프로그램" | "2026년 신규 프로그램" | ✅ 통과 |
| 카드 라벨 | "2025년형 추천" | "2026년형 추천" | ⚠️ standalone 경고만 (design) |

## Known Stubs

- 카드 라벨 "년형" 패턴은 최신/기준/현재 조합이 아니므로 standalone 경고만 발생. 향후 필요 시 패턴 확장 가능.

## Threat Flags

- 없음 (기존 파이프라인에 additive 변경만 적용)
