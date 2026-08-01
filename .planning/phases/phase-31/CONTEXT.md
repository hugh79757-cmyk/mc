# CONTEXT.md — Phase 31: 동적 공식 링크 탐색 시스템

## 목적

`chain_card_injector.py`의 공식 링크 탐색 로직을 개선하여, 정부 TLD(.go.kr, .or.kr 등)에서 무조건 "공공기관" 라벨을 하드코딩하는 대신, 검색을 통해 해당 시설의 실제 공식 홈페이지를 동적으로 찾아낸다.

## 현재 동작 (As-Is)

**검색 흐름:**
1. `find_external_links()` → `_search_via_api()` 호출
2. `_search_via_api()`는 5개 쿼리 템플릿으로 Naver API 검색:
   - "{keyword} 공식 사이트", "{keyword} 공식 홈페이지", "{keyword} 예약 공식", etc.
3. 각 결과를 `_score_official()`로 점수화 → 정부 TLD면 무조건 `label = "공공기관"`
4. 최고 점수 결과를 primary로 선택

**문제:**
- `_score_official()` Lines 106-111: 정부 TLD 감지 시 "공공기관" 하드코딩
- 여행/레저 시설(워터파크, 골프장 등)이 .go.kr 도메인을 사용하면 "공공기관"으로 표기
- 시설 자체 공식 사이트가 검색 결과에 있어도 "공공기관" 라벨이 우선

## 목표 동작 (To-Be)

1. 정부 TLD 결과와 비정부 TLD 결과를 구분하여 평가
2. 정부 TLD 결과가 최고 점수이더라도, 비정부 TLD 결과 중 키워드와 높은 관련성을 가진 것이 있으면 그것을 primary로 선택
3. 정부 TLD가 실제로 해당 시설의 공식 사이트인 경우(예: 건강보험공단 → nhis.or.kr)에만 "공공기관" 라벨 유지
4. 탐색 쿼리 확장: 예약 페이지, 공식 안내 등 더 다양한 검색 수행

## 변경 범위

- `chain_card_injector.py` 내 `_score_official()` 함수의 라벨 로직
- `OFFICIAL_QUERY_TEMPLATES` 확장 (선택)
- 기존 테스트 갱신 + 새 테스트 추가

## 제약

- 함수 시그니처 변경 없음 (priority, score 반환값 유지)
- 스크래핑 절대 금지 (Naver API만 사용)
- 기존 762+ 테스트 회귀 없음
