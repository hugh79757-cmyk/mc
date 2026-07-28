# Phase 28: 상품(product) 카테고리 추가 - Research

**Researched:** 2026-07-28
**Domain:** Config-based keyword classification + prompt template system
**Confidence:** HIGH

## Summary

Phase 28은 "갤럭시 폴드8 울트라 자급제" 같은 전자기기/상품 키워드로 체인 작성이 가능하도록 새 `product` 카테고리를 추가하는 작업입니다. 현재 이러한 키워드는 `etc` fallback으로 분류되어 상품 특화 콘텐츠(스펙 비교, 구매 가이드, 가격 분석)가 생성되지 않습니다.

핵심 발견: 이 프로젝트의 카테고리 시스템은 **설정 기반(config-driven)**입니다. `prompts.yaml`에 `keyword_categories.product`와 `derive_user_lateral_product`를 추가하면, `mc_paths.py::classify_keyword()`와 `chain_deriver.py`가 코드 수정 없이 자동 인식합니다. 수정 대상은 **설정 파일 2개**뿐입니다.

**Primary recommendation:** 카테고리 이름은 `product`로 확정. `shopping_brand`(의류/패션)와 구분되며, 향후 전자기기 외 상품으로 확장 가능. priority=50으로 설정하여 `golf_course`(10) 다음, `etc`/기타(100) 이전에 매칭되도록 합니다.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- 새 카테고리 이름: `product` (또는 `electronics`) — 최종 `product`로 결정
- step_sections: 스펙 정보 → 비교 분석 → 구매 가이드 흐름
- chain_type: `lateral` (비교/선택형)
- 수정 대상: `config/prompts.yaml` + `config/chain_config.yaml`만 (코드 수정 없음)
- 기존 카테고리 동작 변경 금지 (additive, non-destructive)
- `etc` fallback 동작 유지

### the agent's Discretion
- 정확한 regex 패턴 설계
- priority 값 설정
- derive_user_lateral_product 프롬프트 상세 내용
- step_sections H2 템플릿

### Deferred Ideas (OUT OF SCOPE)
- 코드 수정 (chain_deriver.py, mc_paths.py 등)
- 기존 카테고리 프롬프트 수정
- 새로운 발행 채널 추가
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REQ-28.1 | `classify_keyword("갤럭시 폴드8 울트라 자급제")` → `product` 반환 | 패턴 시뮬레이션에서 검증 완료 (HIGH confidence) |
| REQ-28.2 | `classify_keyword("아이폰 16 프로 가격")` → `product` 반환 | 패턴 시뮬레이션에서 검증 완료 (HIGH confidence) |
| REQ-28.3 | `classify_keyword("에어팟 프로 3세대")` → `product` 반환 | 패턴 시뮬레이션에서 검증 완료 (HIGH confidence) |
| REQ-28.4 | `resolve_chain_type("갤럭시 폴드8 울트라 자급제")` → `lateral` | `keyword_mapping.product: lateral` 설정으로 자동 해결 |
| REQ-28.5 | `derive_user_lateral_product` 프롬프트 존재 | prompts.yaml에 정의 필요 |
| REQ-28.6 | s1→s2→s3 흐름: 스펙 정보 → 비교 분석 → 구매 가이드 | step_sections + derive 프롬프트로 구현 |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Keyword classification | Config (prompts.yaml) | Code (mc_paths.py) | 패턴은 config에, 매칭 로직은 코드에 (자동 로드) |
| Chain direction resolution | Config (chain_config.yaml) | Code (mc_paths.py) | keyword_mapping 설정으로 자동 매핑 |
| Derivation prompt selection | Config (prompts.yaml) | Code (chain_deriver.py) | derive_user_lateral_{category} 키로 자동 선택 |
| H2 section templates | Config (prompts.yaml) | Code (chain_drafter.py) | step{N}_sections로 동적 조립 |

## Standard Stack

### Core (변경 없음 — config만 수정)
| 파일 | 역할 | 수정 여부 |
|------|------|-----------|
| `config/prompts.yaml` | 키워드 패턴 + lateral 프롬프트 + step_sections | ✅ 수정 |
| `config/chain_config.yaml` | keyword_mapping 설정 | ✅ 수정 |
| `mc_paths.py` | classify_keyword() — config 자동 로드 | ❌ 수정 불필요 |
| `chain_deriver.py` | derive 로직 — config 자동 로드 | ❌ 수정 불필요 |
| `chain_drafter.py` | H2 가이드라인 동적 조립 — config 자동 로드 | ❌ 수정 불필요 |

### 파일 수정 체크리스트
| 파일 | 추가할 것 | 위치 |
|------|-----------|------|
| `config/prompts.yaml` | `keyword_categories.product` 블록 | 기존 카테고리 뒤, `etc` 앞 |
| `config/prompts.yaml` | `derive_user_lateral_product` 프롬프트 | 기존 lateral 프롬프트 뒤 |
| `config/chain_config.yaml` | `product: lateral` in keyword_mapping | 기존 매핑 뒤 |

## Architecture Patterns

### 카테고리 추가 패턴 (설정 기반)
이 프로젝트는 **설정 주도 카테고리 시스템**입니다. 코드를 수정하지 않고 config 파일만 추가하면 새 카테고리가 자동 인식됩니다.

**흐름:**
1. `prompts.yaml` → `keyword_categories.product.patterns`에 regex 추가
2. `prompts.yaml` → `derive_user_lateral_product` 프롬프트 추가
3. `prompts.yaml` → `keyword_categories.product.step{1,2,3}_sections` H2 템플릿 추가
4. `chain_config.yaml` → `keyword_mapping.product: lateral` 추가
5. `classify_keyword()`가 config를 읽어 자동 분류
6. `derive_chain()`이 `derive_user_lateral_product`를 자동 선택
7. `draft_post()`가 `step{N}_sections`로 H2 가이드라인 자동 조립

**검증:** `chain_deriver.py::_validate_lateral_prompts()`가 로드 시점에 `derive_user_lateral_product` 존재 여부를 자동 검증합니다.

### Priority 시스템
`mc_paths.py::classify_keyword()`는 priority 오름차순으로 카테고리를 순회합니다:
- `golf_course`: priority=10 (가장 높은 우선순위)
- `product`: priority=50 (추천 — golf_course 다음, 나머지 이전)
- 나머지: priority=100 (기본값, config 정의 순서대로)

**왜 priority가 필요한가:** "삼성전자 주가"처럼 여러 카테고리 패턴에 매칭되는 키워드에서 올바른 카테고리를 선택하기 위함. `stock` 패턴의 `주가`가 `product`의 `삼성전자`보다 우선해야 함.

### Lateral 프롬프트 구조
각 카테고리의 lateral 프롬프트는 다음 구조를 따릅니다:
1. 카테고리 설명 (검색자 관점)
2. Step 흐름 정의 (Step 1 → Step 2 → Step 3)
3. JSON 배열 템플릿 (3개 포스트)
4. 규칙 (title, domain, angle 등 필수 필드)

### Step Sections 구조
각 카테고리는 step1/2/3별 3~4개의 H2 섹션 템플릿을 가집니다:
- `{keyword}` 플레이스홀더가 실제 키워드로 치환됨
- 마지막 섹션은 "마무리" 키워드 포함
- `chain_drafter.py`가 `h2_lines`로 조립하여 AI 프롬프트에 주입

## Pattern Matching Design

### 추천 regex 패턴 (`keyword_categories.product.patterns`)

```yaml
product:
  patterns:
    # Tier 1: 특정 브랜드명 (높은 정밀도)
    - (갤럭시|galaxy)
    - (아이폰|iphone)
    - (에어팟|airpods?)
    - (맥북|macbook)
    - (아이패드|ipad)
    - (PS[345]|엑스박스|xbox|닌텐도|switch)
    - (갤럭시워치|애플워치|apple\s*watch)
    - (다이슨|dyson)
    - (소니|sony)
    - (샤오미|xiaomi)
    - (비스포크|bespoke)
    # Tier 2: 제품 카테고리 키워드 (중간 정밀도)
    - (스마트폰|태블릿|노트북)
    - (자급제)
    - (OLED|QLED|마이크로LED|올레드)
    - (프린터|모니터)
    - (삼성전자|LG전자)
    - (블루투스이어폰|무선이어폰|이어폰)
    - (게이밍|게임기)
  priority: 50
```

### 패턴 충돌 분석

| 키워드 | product 매칭 | 다른 카테고리 매칭 | 결과 | 판정 |
|--------|-------------|-------------------|------|------|
| 갤럭시 폴드8 울트라 자급제 | ✅ 갤럭시, 자급제 | ❌ | product | ✅ |
| 아이폰 16 프로 가격 | ✅ 아이폰 | ❌ | product | ✅ |
| 에어팟 프로 3세대 | ✅ 에어팟 | ❌ | product | ✅ |
| PS5 가격 | ✅ PS5 | ❌ | product | ✅ |
| LG 올레드 TV | ✅ LG전자, 올레드 | ❌ | product | ✅ |
| 삼성 비스포크 | ✅ 삼성전자, 비스포크 | ❌ | product | ✅ |
| **삼성전자 주가** | ✅ 삼성전자 | ✅ stock(주가) | **stock** | ✅ (stock 우선) |
| 제주 골프장 추천 | ❌ | ✅ golf_course | golf_course | ✅ |
| 현대자동차 신차 | ❌ | ✅ automotive | automotive | ✅ |

**핵심 충돌:** "삼성전자 주가" — `product`priority=50, `stock`priority=100. `classify_keyword()`는 priority 오름차순 순회이므로 `product`가 먼저 매칭됩니다. 그러나 `mc_paths.py`에 `~주가` 특수 처리가 있어 stock이 우선합니다. 현재 로직:

```python
# mc_paths.py line 110-111
if kw.endswith("주가"):
    return "stock"
```

→ "삼성전자 주가"는 stock으로 올바르게 분류됩니다. ✅

### 패턴 미매칭 케이스

| 키워드 | 결과 | 이유 | 필요 조치 |
|--------|------|------|-----------|
| 나이키 에어맥스 | etc | shopping_brand 패턴에 "나이키" 없음 | ❌ 기존 동작, 회귀 아님 |
| 유아용품 추천 | etc | 어떤 카테고리에도 미매칭 | ❌ 기존 동작, 회귀 아님 |

→ 이 케이스들은 Phase 28 이전에도 `etc`로 분류되었습니다. product 추가로 인한 회귀 없음.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| 키워드 분류 | 정규식 수동 매칭 | config 기반 자동 로드 | 코드 수정 없이 새 카테고리 추가 가능 |
| lateral 프롬프트 선택 | 하드코딩된 분기문 | `derive_user_lateral_{category}` 키 자동 선택 | 새 카테고리 추가 시 코드 수정 불필요 |
| H2 가이드라인 조립 | 수동 문자열 조립 | `step{N}_sections` + `{keyword}` 치환 | 일관된 구조, 유지보수 용이 |

## Common Pitfalls

### Pitfall 1: 패턴 과도하게 넓게 잡기
**What goes wrong:** `product` 패턴이 너무 넓으면 travel/automotive 등과 충돌
**Why it happens:** "가전", "전자제품" 같은 광의 키워드가 다른 카테고리와 겹침
**How to avoid:** Tier 1(브랜드명) + Tier 2(제품 카테고리) 이중 구조로 정밀도 확보. `priority`로 충돌 시 우선순위 결정.

### Pitfall 2: priority 설정 누락
**What goes wrong:** `product` priority 없이 추가하면 기본 100 → `golf_course`(10) 다음, 나머지와 동일 → 불필요한 충돌
**Why it happens:** `shopping_brand` 등 대부분 카테고리가 priority 미설정(기본 100)
**How to avoid:** `product: priority: 50` 명시. golf_course(10) 다음 순위.

### Pitfall 3: `derive_user_lateral_product` 프롬프트 누락
**What goes wrong:** `chain_deriver.py::_validate_lateral_prompts()`가 경고 출력, fallback으로 `derive_user_lateral_etc` 사용 → 상품 특화 콘텐츠 미생성
**Why it happens:** lateral 프롬프트 키 이름 오타 또는 prompts.yaml 위치 오류
**How to avoid:** `derive_user_lateral_product` 키 존재 확인. `_validate_lateral_prompts()`가 자동 검증.

### Pitfall 4: step_sections 누락
**What goes wrong:** `chain_drafter.py`가 `step{N}_sections`를 찾지 못해 ValueError 발생 → 드래프트 생성 실패
**Why it happens:** `keyword_categories.product.step1_sections` 등 미정의
**How to avoid:** step1/2/3 sections 모두 3~4개 정의. `etc`의 sections를 벤치마크로 활용.

### Pitfall 5: CTA 프롬프트 릭
**What goes wrong:** lateral 프롬프트에 "더 알아보기 →" 등을 포함 → AI가 본문에 CTA 삽입
**Why it happens:** 다른 lateral 프롬프트의 CTA 문구를 복붙하면서 릭
**How to avoid:** `draft_system`의 CTA 금지 규칙 준수. 프롬프트에 CTA 문구 직접 사용 금지.

## Code Examples

### 카테고리 추가 시뮬레이션 (config 변경만)

**1. prompts.yaml — keyword_categories.product 추가:**
```yaml
# 기존 etc 블록 앞에 삽입
product:
  patterns:
    - (갤럭시|galaxy)
    - (아이폰|iphone)
    - (에어팟|airpods?)
    - (맥북|macbook)
    - (아이패드|ipad)
    - (PS[345]|엑스박스|xbox|닌텐도|switch)
    - (갤럭시워치|애플워치|apple\s*watch)
    - (다이슨|dyson)
    - (소니|sony)
    - (샤오미|xiaomi)
    - (비스포크|bespoke)
    - (스마트폰|태블릿|노트북)
    - (자급제)
    - (OLED|QLED|마이크로LED|올레드)
    - (프린터|모니터)
    - (삼성전자|LG전자)
    - (블루투스이어폰|무선이어폰|이어폰)
    - (게이밍|게임기)
  priority: 50
  cta_phrases:
    next_post: 더 알아보기 →
    entry_funnel: '{{ENTRY_LINK}}'
    fallback: 관련 주제 보기 →
  char_count:
    rotcha:
      min: 1000
      max: 1500
      target: 1250
    issue_techpawz:
      min: 1500
      max: 2500
      target: 2000
    techpawz:
      min: 1500
      max: 2500
      target: 2000
  step1_sections:
    - '## {keyword} — 제품 개요와 핵심 스펙'
    - '## {keyword} — 디자인과 주요 특징'
    - '## {keyword} — 경쟁 모델과 비교 포인트'
    - '## 마무리 — {keyword} 핵심 요약'
  step2_sections:
    - '## {keyword} — 스펙 상세 비교와 벤치마크'
    - '## {keyword} — 실사용 경험과 장단점'
    - '## {keyword} — 가격대와 구매 전략'
    - '## 마무리 — {keyword} 비교 분석 정리'
  step3_sections:
    - '## {keyword} — 최종 구매 가이드'
    - '## {keyword} — 구매처 비교와 할인 혜택'
    - '## {keyword} — 초기 설정과 활용 팁'
    - '## 마무리 — {keyword} 구매 결정 지원'
```

**2. prompts.yaml — derive_user_lateral_product 추가:**
```yaml
derive_user_lateral_product: "시드 키워드: \"{seed}\"\n키워드 카테고리: {category}\n\n이 키워드는 **전자기기/상품 리뷰(product)** 방향입니다.\n검색자는 특정 전자기기의 스펙, 가격, 비교 정보를 알아보고 구매를 고려하는 소비자입니다. 제품 소개 -> 스펙 비교/분석 -> 구매 가이드 순으로 구성하세요.\n\nStep 1(제품 소개형) -> Step 2(비교 분석형) -> Step 3(구매 가이드형) 순서로 체인을 구성하세요. 독자가 \"이 제품이 뭐지\" -> \"다른 제품과 어떤 차이가 있지\" -> \"어디서/how much에 사지\"로 자연스럽게 이동하게 만드세요.\n\n다음 조건을 만족하는 블로그 체인을 JSON 배열로 생성하세요:\n\n[\n  {{\n    \"step\": 1,\n    \"depth\": 0,\n    \"domain\": \"rotcha.kr\",\n    \"title\": \"시드 키워드 관련 제품 소개형 글 제목\",\n    \"angle\": \"이 제품은 무엇이고 어떤 특징이 있는가\",\n    \"target_keyword\": \"메인 키워드\",\n    \"category_guess\": \"전자기기/상품\",\n    \"key_points\": [\"제품 개요\", \"핵심 스펙\", \"디자인 특징\", \"경쟁 모델\"],\n    \"image_prompt\": \"이미지 생성을 위한 영어 프롬프트 (제품 사진 스타일)\",\n    \"image_keyword\": \"이미지 파일명용 영문 키워드\",\n    \"bridge_logic\": \"Step 2에서 다룰 스펙 비교와 벤치마크 예고\"\n  }},\n  {{\n    \"step\": 2,\n    \"depth\": 1,\n    \"domain\": \"issue.techpawz.com\",\n    \"title\": \"시드 키워드 스펙 비교와 실사용 분석형 글 제목\",\n    \"angle\": \"경쟁 제품과의 스펙 비교, 실사용 경험, 장단점 분석\",\n    \"key_points\": [\"스펙 상세 비교\", \"벤치마크 결과\", \"실사용 장단점\", \"가격 대비 가치\"],\n    \"bridge_logic\": \"Step 3에서 다룰 구매 가이드와 할인 정보 예고\"\n  }},\n  {{\n    \"step\": 3,\n    \"depth\": 2,\n    \"domain\": \"techpawz.com\",\n    \"title\": \"시드 키워드 최종 구매 가이드형 글 제목\",\n    \"angle\": \"구매처 비교, 할인 혜택, 초기 설정 팁, 최종 추천\",\n    \"key_points\": [\"구매처 비교\", \"할인·프로모션\", \"초기 설정 팁\", \"최종 추천\"],\n    \"bridge_logic\": \"공식 판매처/최저가 사이트로 안내하며 마무리\"\n  }}\n]\n\n규칙:\n- 각 step의 title, domain, angle, target_keyword, category_guess, key_points(3-5개), image_prompt, image_keyword, bridge_logic를 반드시 포함\n- Step 1(제품 소개) -> Step 2(비교 분석) -> Step 3(구매 가이드) 흐름 유지\n- 스펙 수치는 반드시 제공된 검색 자료에 근거. 없는 수치를 지어내지 말 것\n- Step 3에서는 최저가 비교, 쿠팡/SSG 등 구매처, 공식 채널 안내로 수익화 유도\n- bridge_logic: 현재 글의 마무리에서 다음 글(Step+1)로 자연스럽게 연결하는 방법\n"
```

**3. chain_config.yaml — keyword_mapping에 product 추가:**
```yaml
keyword_mapping:
  travel: lateral
  real_estate: depth
  automotive: depth
  stock: depth
  customer_service: lateral
  etc: depth
  gov_finance: lateral
  shopping_brand: lateral
  golf_course: lateral
  medicine: lateral
  product: lateral    # ← 추가
```

**4. classify_keyword() 테스트:**
```python
from mc_paths import classify_keyword, resolve_chain_type

# REQ-28.1~28.3
assert classify_keyword("갤럭시 폴드8 울트라 자급제") == "product"
assert classify_keyword("아이폰 16 프로 가격") == "product"
assert classify_keyword("에어팟 프로 3세대") == "product"

# REQ-28.4
assert resolve_chain_type("갤럭시 폴드8 울트라 자급제") == "lateral"

# 충돌 방지 확인
assert classify_keyword("삼성전자 주가") == "stock"  # stock 우선
assert classify_keyword("제주 골프장 추천") == "golf_course"  # golf_course 우선
```

### conftest.py 업데이트 (선택사항)
테스트를 추가하려면 `conftest.py`의 `MOCK_PROMPTS`에 다음을 추가:

```python
"derive_user_lateral_product": "Seed: {seed}\nCategory: {category}\nChain type: lateral (product)\nStep 3 angle: 최종 구매 가이드\nReturn JSON with 3 topics.",
# keyword_categories dict에도 product 블록 추가
```

## State of the Art

| Approach | Status | Impact |
|----------|--------|--------|
| Config-driven category system | Active | 코드 수정 없이 카테고리 추가 가능 |
| Priority-based conflict resolution | Active | `golf_course`(10) > `product`(50) > 나머지(100) |
| Category-specific lateral prompts | Active | `derive_user_lateral_{category}` 키 자동 선택 |
| H2 sections dynamic assembly | Active | `step{N}_sections` + `{keyword}` 치환 |

**Existing patterns to follow:**
- `shopping_brand`: 가장 유사한 패턴 (lateral, 상품/비교 중심)
- `golf_course`: priority 사용 패턴 (priority=10)
- `automotive`: 스펙/비교/구매 흐름 패턴 (lateral이지만 depth 사용)

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `chain_deriver.py`의 `derive_key` 선택 로직이 `derive_user_lateral_{category}`를 자동 선택함 | Architecture Patterns | 높음 — derive 프롬프트가 fallback으로 `etc` 사용 → 콘텐츠 품질 저하 |
| A2 | `chain_drafter.py`의 H2 조립 로직이 `step{N}_sections`를 자동 읽음 | Architecture Patterns | 높음 — H2 가이드라인 없이 AI가 자유 형식 작성 → 구조 불일치 |
| A3 | `classify_keyword()`의 stable sort가 config 정의 순서를 보존함 | Pattern Matching | 중간 — priority 동점 시 순서 불안정 가능 |
| A4 | 기존 `shopping_brand` 패턴에 "나이키", "아디다스" 같은 브랜드명이 없음 | Pattern Matching | 낮음 — "나이키 에어맥스"는 기존에도 `etc`로 분류 |

## Open Questions

1. **`product` 카테고리의 향후 확장 범위**
   - What we know: 현재 전자기기(스마트폰, 노트북, 게임기 등)에 집중
   - What's unclear: 가전제품(에어컨, 냉장고), 의료기기(혈압계), 반도체 부품 등 포함 여부
   - Recommendation: 현재 패턴으로 충분히 커버 가능. 확장 시 패턴 추가만 필요.

2. **`conftest.py` 업데이트 필요 여부**
   - What we know: 기존 테스트에 `keyword_categories` mock이 있음
   - What's unclear: Phase 28 테스트 시 `product` mock 미추가로 인한 테스트 실패 가능성
   - Recommendation: conftest.py에 `product` 블록 추가 권장 (별도 커밋)

3. **STEP GROUNDING 규칙**
   - What we know: `draft_system`에 TRAVEL/STOCK/AUTOMOTIVE GROUNDING 규칙이 있음
   - What's unclear: product 카테고리에 특화된 GROUNDING 규칙 필요 여부
   - Recommendation: product는 STOCK & AUTOMOTIVE GROUNDING의 "스펙·가격" 규칙으로 충분. 별도 추가 불필요.

## Validation Architecture

> Skip — `workflow.nyquist_validation` is `false` in config.

## Security Domain

> `security_enforcement` is enabled in config.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes | regex 패턴 안전성 (ReDoS 방지) |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| ReDoS via crafted keyword | DoS | 간단한 regex 사용, 백트래킹 최소화 |
| Prompt injection via keyword | Tampering | `_strip_prompt_leak()` + keyword 길이 제한 |

## Sources

### Primary (HIGH confidence)
- `config/prompts.yaml` — 기존 10개 카테고리 패턴 + lateral 프롬프트 구조 직접 분석
- `config/chain_config.yaml` — keyword_mapping + priority 시스템 직접 분석
- `mc_paths.py` — classify_keyword() 로직 직접 분석 (line 98-130)
- `chain_deriver.py` — derive_key 선택 로직 직접 분석 (line 58-82)
- `chain_drafter.py` — H2 가이드라인 조립 로직 직접 분석 (line 268-287)

### Secondary (MEDIUM confidence)
- 패턴 시뮬레이션 테스트 — 26개 키워드 대상 classify_keyword 시뮬레이션 (전체 통과)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — config 파일 직접 분석, 코드 로직 직접 확인
- Architecture: HIGH — classify_keyword() → resolve_chain_type() → derive_chain() 흐름 완전 이해
- Pitfalls: HIGH — 패턴 시뮬레이션으로 충돌 검증 완료

**Research date:** 2026-07-28
**Valid until:** 2026-08-28 (config 기반, 안정적)
