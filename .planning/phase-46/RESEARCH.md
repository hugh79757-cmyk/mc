# RESEARCH: Phase 46 — 발행 전 사전 리서치 삽입

## 기존 코드베이스 분석

### 1. 검색 모듈 (search_retriever.py)

`NaverSearchClient`:
- Naver API를 사용한 블로그/웹사이트 검색
- `search(query, display=5) -> list[dict]` — 제목, 설명, URL 반환
- rate limit 처리 포함

`retrieve_context_for_post(keyword, step)`:
- 키워드 + 단계별 검색 쿼리 생성
- 상위 N개 결과 수집 후 컨텍스트 문자열 반환
- 현재 `chain_drafter.py`에서 draft 단계에만 사용

### 2. 초안 생성 (chain_drafter.py)

`draft_single_post()`:
- `retrieve_context_for_post()`로 검색 컨텍스트 수집
- `_build_prev_context()`로 이전 단계 포스트 정보 조립
- prompts.yaml의 draft_system/draft_user 템플릿 사용
- AI에게 검색 컨텍스트 + 이전 컨텍스트 전달

**현재 문제:** 검색 컨텍스트가 "info" 형태로 전달됨. factoid·수치·출처 URL이 구조화되지 않음.

### 3. 파이프라인 흐름 (chain_publisher.py)

```
derive keyword → draft (3 posts) → image → publish
```

`derive`와 `draft` 사이에 리서치 단계 삽입 필요.

### 4. rate limit 처리

`search_retriever.py`에서:
- Naver API rate limit: 초당5회 제한
- retry 로직: exponential backoff
- timeout:5초

## 통합 지점

1. **pre_publish_researcher.py**: `research_keyword(keyword) -> ResearchResult`
2. **chain_drafter.py**: 리서치 결과를 프롬프트에 주입
3. **chain_publisher.py**: derive→research→draft 파이프라인 수정

## 리서치 결과 형식

```python
@dataclass
class ResearchResult:
    keyword: str
    factoids: list[Factoid]  # factoid text + source URL
    summary: str              # GPT 요약
    raw_results: list[dict]   # Naver 검색 원본

@dataclass
class Factoid:
    text: str
    source_url: str
    confidence: float  # 0.0~1.0
```

## 리스크

- Naver API rate limit → 기존 rate limit 처리 재사용
- 리서치 시간 증가 → 병렬 처리 또는 캐싱 고려
- 리서치 결과 품질 불일치 → GPT 요약 품질 검증 필요
- OpenAI API 추가 비용 → GPT-4o-mini 사용으로 비용 최소화

## 권장 사항

1. derive 후, draft 전 리서치 실행
2. 리서치 실패 시 경고 후 기존 방식대로 진행 (fallback)
3. 리서치 결과를 `prompts.yaml`의 drafting 프롬프트에 `[사전 리서치]` 블록으로 주입
4. factoid 형식: `- factoid text (출처: URL)`
