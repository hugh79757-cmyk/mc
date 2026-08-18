# RESEARCH: Phase 44 — 블로그 간 중복 해소 + 역할 분리

## 기존 코드베이스 분석

### 1. 체인 구조 (chain_db.py)

chain_posts 테이블:
- `chain_id`: 체인 ID (하나의 키워드 = 3개 포스트)
- `step`: 1/2/3 (rotcha→issue→techpawz 순서)
- `depth`: 0/1/2 (동일 매핑)
- `title`, `slug`, `draft_md`, `published_md`

**핵심:** 동일 chain_id의3개 포스트가 서로 다른 역할을 가져야 함.

### 2. 역할 매핑 (audit_format.py)

```python
DEPTH_TO_SITE = {0: "rotcha", 1: "issue.techpawz", 2: "techpawz"}
SITE_TO_DOMAIN = {
    "rotcha": "issue.techpawz.com",
    "issue.techpawz": "techpawz.com",
    "techpawz": None,
}
```

### 3. 프롬프트 역할 분리 (prompts.yaml)

`keyword_categories`마다 step1/step2/step3 프롬프트가 다름:
- step1 (rotcha): 정보성 — 개요, 특징, 기준
- step2 (issue): 비교/검증 — A vs B, 검증 항목
- step3 (techpawz): 구매/실전 — 체크리스트, 가격, 추천

### 4. 카드 주입 역할 분리 (chain_card_injector.py)

D8/D9 게이트에서 CTA 텍스트 필터:
- rotcha: "더 알아보기 →" (정보 탐색)
- issue: "비교 확인 →" (비교 검증)
- techpawz: "구매하기 →" (구매 행동)

## 통합 지점

1. **cross_blog_checker.py**: `check_cross_blog_duplicates(posts: list[dict]) -> CrossBlogResult`
2. **quality_gate.py**: `validate_role_separation(posts) -> GateResult`
3. **contracts/*.yaml**: Phase 41의 역할 정의와 연동

## 중복 탐지 접근법

한국어 TF-IDF는 제한적 → 대안:
1. **키워드 오버랩**: 두 포스트의 명사구 추출 후 교집합/합집합 비율
2. **H2 섹션 비교**: 동일 H2 제목이2개 이상 포스트에 있으면 위반
3. **구문 패턴 비교**: "최저가", "~원", "비교표" 등 역할별 금지 표현 탐지

## 리스크

- TF-IDF가 한국어에서 제한적 → 키워드 오버랩 기반으로 시작
- 역할 경계가 모호한 카테고리 존재 → 계약서로 명시적 경계 설정

## 권장 사항

1. 간단한 키워드 오버랩부터 시작 (형태소 분석 없이 공백 기반 토큰화)
2. 역할 분리는 계약서(Phase 41)의 forbidden_sections과 연동
3. 기준: 동일 키워드 50% 이상 오버랩 = 위반
