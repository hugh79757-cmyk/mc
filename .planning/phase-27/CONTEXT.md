# CONTEXT.md — Phase 27: 카테고리별 Draft 품질 검증

**Phase:** 27
**Created:** 2026-07-28
**Mode:** validation

## Objective

6개 카테고리(stock, real_estate, travel, shopping_brand, customer_service, golf_course)에서 각각 2개의 draft를 생성하여 품질을 검증한다. 기존에 검증된 medicine(#230)과 golf_course(#231)의 검증 프로세스를 재사용한다.

## Background

- 10개 카테고리 체계가 구축되었으나, medicine과 golf_course만 E2E 검증됨
- 나머지 6개 카테고리의 derive→draft 파이프라인이 실제로 올바른 결과를 생성하는지 확인 필요
- 각 카테고리별 2개 시드로 테스트하여 일관성을 확인

## Verified Categories (이전 세션)

| 카테고리 | Chain ID | 검증 항목 | 상태 |
|----------|----------|-----------|------|
| medicine | #230 | derive + draft E2E | ✅ |
| golf_course | #231 | derive + draft E2E | ✅ |

## 검증 대상 6개 카테고리

| 카테고리 | 방향 | 검증 시드 1 | 검증 시드 2 |
|----------|------|------------|------------|
| stock | depth | "삼성전자 주가" | "ETF 투자 전략" |
| real_estate | depth | "청주 아파트 시세" | "수원 오피스텔 분양" |
| travel | lateral | "제주도 여행 코스" | "강릉 여행 숙소" |
| shopping_brand | lateral | "골프웨어 브랜드 추천" | "온라인 쇼핑몰 순위" |
| customer_service | lateral | "삼성전자서비스 고객센터" | "카카오 고객센터 전화번호" |
| golf_course | lateral | "남서울CC 예약" | "용인CC 라운딩" |

## 검증 기준

### Derive 검증
- 분류: 올바른 카테고리로 분류되는가
- 방향: keyword_mapping에 정의된 방향으로 resolve되는가
- 프롬프트: category-specific prompt가 선택되는가
- 흐름: s1→s2→s3가 설계대로 자연스러운가
- bridge_logic: 각 step 간 연결이 자연스러운가

### Draft 검증
- H2 구조: step_sections대로 H2가 생성되는가
- 길이: char_count 기준 범위 내인가
- 유기적 연결: s1→s2→s3 다음 글 예고가 있는가
- depth2 배출: s3에서 공식/예약/신청 창구로 마무리되는가
- 프롬프트 릭: AI 프롬프트가 본문에 노출되지 않는가
- 의료 안전 가드 (medicine만): 의사/약사 상담 권고 포함 여부

## 검증 스크립트

`/tmp/analyze_drafts.py` — chain_id 인자로 draft 분석 (H2 구조, 글자수, 유기적 연결 체크)

## 참고 자료

- `config/prompts.yaml` — 카테고리별 lateral 프롬프트 + step_sections
- `config/chain_config.yaml` — keyword_mapping (방향 정의)
- `chain_deriver.py` — derive 로직 + _parse_derivation
- `chain_drafter.py` — draft 생성 로직
