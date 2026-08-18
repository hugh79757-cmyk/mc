# RESEARCH: Phase 47 — 스코어링 시스템

## 기존 코드베이스 분석

### 1. M3 전체 모듈 의존성

Phase 47은 M3의 마지막 단계로, 모든 검증 모듈의 결과를 종합:

| Phase | 모듈 | 결과 타입 | 가중치 |
|-------|------|----------|--------|
| 41 | quality_gate.py (contract) | GateResult | 40% |
| 42 | title_body_checker.py | TitleBodyResult | (41에 포함) |
| 43 | factuality_checker.py | FactualityResult | 25% |
| 44 | cross_blog_checker.py | CrossBlogResult | 20% |
| 45 | html_render_checker.py | HtmlRenderResult | 15% |
| 46 | pre_publish_researcher.py | ResearchResult | (간접적) |

### 2. 이미지 모듈 (image/)

```
image/
├── base_provider.py      — BaseImageProvider 추상 클래스
├── cache_manager.py      — 이미지 캐시 관리
├── prompt_builder.py     — 컨텍스트 기반 프롬프트 생성
├── r2_uploader.py        — R2 업로드
└── search_providers.py   — Unsplash/Pexels API
```

썸네일 검증: `image/` 모듈에서 생성한 이미지의 존재 여부 + R2 URL 유효성 확인.

### 3. 기존 결과 집계 패턴 (audit_chain.py)

`run_all_checks()` 패턴:
```python
def run_all_checks(chain_id):
    results = {}
    results["prompt_leak"] = check_prompt_leak(body)
    results["markers"] = check_unresolved_markers(body)
    # ... 각 check 함수 호출
    return results
```

**재사용:** `quality_scorer.py`에서 동일한 패턴으로 각 모듈 결과 수집.

### 4. chain_models.py Result 패턴

```python
@dataclass(frozen=True)
class Result:
    ok: bool
    value: Any = None
    error: Optional[Error] = None
```

**스코어 결과도 동일 패턴 적용:** `QualityScore(ok, score, breakdown, violations)`

## 스코어링 가중치

| 항목 | 가중치 | 기준 |
|------|--------|------|
| 계약 충족 | 40% | Phase41 계약서 검증 통과 비율 |
| 사실성 | 25% | Phase43 factuality 스코어 |
| 역할 분리 | 20% | Phase44 중복 + 역할 검증 결과 |
| 시각 품질 | 15% | 썸네일 존재 + HTML 렌더링 중복 없음 |

## 자동 판정 기준

| 점수 | 판정 | 액션 |
|------|------|------|
| 7.0미만 | 재생성 | 다른 키워드로 재시도 |
| 7.0~8.9 | 수동 검토 | 운영자 승인 대기 |
| 9.0+ | 자동 승인 | 즉시 발행 |

## 통합 지점

1. **quality_scorer.py**: `calculate_score(post_md, chain_posts) -> QualityScore`
2. **chain_publisher.py**: 발행 전 스코어링 호출 → 기준 미달 시 발행 차단
3. **audit_chain.py**: 스코어 결과를 감사 리포트에 포함

## 리스크

- 스코어링 가중치가 실제 품질과 안 맞을 수 있음 → 점진적 조정
- 자동 승인 기준9.0이 너무 높을 수 있음 → 초기8.5로 시작 가능
- 각 모듈의 결과 품질에 따라 스코어 신뢰도 변동

## 권장 사항

1. 가중합 점수 산출: `score = w1*contract + w2*factuality + w3*role + w4*visual`
2. 각 항목을0.0~1.0으로 정규화 후 가중합
3. 스코어 결과를 DB에 저장해 추후 분석 가능하게
4. 초기8.5 자동 승인 기준으로 시작, 운영 데이터 기반 조정
