# Phase 46: 발행 전 사전 리서치 단계 삽입

**Milestone:** M3 — 9점 품질 달성
**Goal:** draft 단계 전에 Naver API + GPT 요약으로 사실 기반 데이터를 수집하고, 이를 drafting 프롬프트에 주입.

## Why

현재 파이프라인은 키워드 → 바로 초안 생성. 사전 리서치 없이 AI가 자체 지식에 의존 → 사실 오류, 미확인 가격 단정, 근거 없는 리뷰 생성. terra-tomato 사례에서 "가격 확인 없이 최저가 단정"이 대표적 문제.

## Plan

### W1: pre_publish_researcher.py

- 기존 `search_retriever.py` (Naver API) 재사용
- 키워드 → Naver 검색 → 상위5개 결과 수집
- GPT로 검색 결과 요약: factoids·수치·출처 URL

### W2: 리서치 결과 → 프롬프트 주입

- 리서치 결과를 `prompts.yaml`의 drafting 프롬프트에 주입
- 형식: `[사전 리서치]\n- factoid1 (출처: URL)\n- factoid2 (출처: URL)`
- AI가 리서치 결과를 기반으로 콘텐츠 작성하도록 유도

### W3: derive 단계와의 통합

- derive 후, draft 전 리서치 실행
- `chain_publisher.py` 파이프라인에 리서치 단계 삽입
- 리서치 실패 시 경고 후 기존 방식대로 진행 (fallback)

### W4: pytest

- 리서치 단계 정상 동작 테스트
- 리서치 실패 시 fallback 테스트
- 프롬프트 주입 테스트

## Dependencies

- 기존 `search_retriever.py` (Naver API)
- 기존 `chain_drafter.py` (프롬프트 구성)
- OpenAI API (GPT 요약용)

## Risks

- Naver API rate limit → 기존 rate limit 처리 재사용
- 리서치 시간 증가 → 병렬 처리 또는 캐싱 고려
- 리서치 결과 품질 불일치 → GPT 요약 품질 검증 필요
