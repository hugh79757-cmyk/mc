---
phase: 43-pre-research
plan: "01"
subsystem: quality
tags: [pre-research, factsheet, naver-search, pipeline]
dependency_graph:
  requires: ["41-01"]
  provides: ["quality/pre_researcher.py"]
  affects: [quality, shared/ai_writer.py]
tech_stack:
  added: []
  patterns: [dataclass, naver-search-api, graceful-degradation]
key_files:
  created: [quality/pre_researcher.py, tests/test_pre_researcher.py]
  modified: []
decisions:
  - "Reuse existing NaverSearchClient from search_retriever.py instead of building new search client"
  - "Graceful degradation: return empty Factsheet on any search failure, never raise"
  - "inject_factsheet_to_prompt prepends '## 사전 리서치 결과' section to base prompt"
metrics:
  duration: 137s
  completed: "2026-08-18T06:19:49Z"
  tasks_completed: 3
  files_created: 2
---

# Phase 43 Plan 01: pre_researcher Summary

Keyword 기반 웹 리서치 → Factsheet 생성 모듈 구현. Naver Search API 재사용, 검색 실패 시 빈 Factsheet 반환(예외 없음), 파이프라인 프롬프트 주입 인터페이스 제공.

## What Was Built

1. **`quality/pre_researcher.py`** — 핵심 모듈
   - `Fact` dataclass: claim, source_url, retrieved_date, confidence
   - `Factsheet` dataclass: facts list, keyword, researched_at
   - `research_keyword(keyword)`: NaverSearchClient로 상위 5건 검색 → Factsheet 반환. 실패 시 빈 Factsheet
   - `save_factsheet(factsheet, chain_id)`: `data/factsheets/{chain_id}.json`에 저장
   - `inject_factsheet_to_prompt(factsheet, base_prompt)`: "## 사전 리서치 결과" 섹션을 프롬프트에 주입

2. **`tests/test_pre_researcher.py`** — 16개 테스트
   - Factsheet/Fact 생성/직렬화 (4건)
   - inject 빈/값 있는 팩트시트 (3건)
   - research_keyword 목/mock (4건)
   - save_factsheet 저장/디렉토리 생성 (2건)
   - _extract_facts_from_results (3건)

## Deviations from Plan

None — plan executed exactly as written.

## Verification

| Check | Result |
|-------|--------|
| `python -c "from quality.pre_researcher import Factsheet, Fact"` | [검증됨] Factsheet 인스턴스 정상 생성 |
| `python -c "from quality.pre_researcher import inject_factsheet_to_prompt, Factsheet"` | [검증됨] 빈 factsheet 경고 메시지 포함 확인 |
| `python -m pytest tests/test_pre_researcher.py -v` | [검증됨] 16 passed in 0.04s |
| `python -m pytest --tb=short -q` (전체 스위트) | [검증됨] 966 passed, 5 failed (기존 5건 회귀 없음) |

## Known Stubs

None — 모듈이 독립적으로 동작하며, Phase 47에서 파이프라인 삽입(drafter 호출 전 factsheet 주입)이 수행됨.

## Threat Flags

None — 검색 API 호출은 기존 search_retriever.py의 NaverSearchClient를 재사용하며, 새로운 네트워크 엔드포인트나 인증 경로를 추가하지 않음.

## Residual Risks

- **5건 기존 테스트 실패**: `test_ai_writer_bug001.py` 3건 (truncation retry), `test_chain_drafter.py` 2건 (raw_ai_output 컬럼 누락). 이번 변경과 무관.
