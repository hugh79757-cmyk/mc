---
phase: 28
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - config/prompts.yaml
  - config/chain_config.yaml
  - conftest.py
  - test_chain_deriver.py
autonomous: true
requirements: [REQ-28.1, REQ-28.2, REQ-28.3, REQ-28.4, REQ-28.5, REQ-28.6]

must_haves:
  truths:
    - 'classify_keyword("갤럭시 폴드8 울트라 자급제") returns "product"'
    - 'classify_keyword("아이폰 16 프로 가격") returns "product"'
    - 'classify_keyword("에어팟 프로 3세대") returns "product"'
    - 'resolve_chain_type("갤럭시 폴드8 울트라 자급제") returns "lateral"'
    - 'derive_user_lateral_product prompt exists in prompts.yaml'
    - 'product keyword_categories block with step1/2/3_sections exists'
    - '기존 카테고리 분류 unchanged (회귀 없음)'
  artifacts:
    - path: config/prompts.yaml
      provides: "product keyword_categories + derive_user_lateral_product prompt"
      contains: "keyword_categories.product"
    - path: config/chain_config.yaml
      provides: "product → lateral mapping"
      contains: "product: lateral"
    - path: conftest.py
      provides: "product mock in MOCK_PROMPTS"
      contains: "derive_user_lateral_product"
    - path: test_chain_deriver.py
      provides: "product category test cases"
      contains: "class TestKeywordClassification"
  key_links:
    - from: config/prompts.yaml
      to: mc_paths.py::classify_keyword()
      via: "keyword_categories config auto-load"
      pattern: "keyword_categories.*product"
    - from: config/chain_config.yaml
      to: mc_paths.py::resolve_chain_type()
      via: "keyword_mapping config auto-load"
      pattern: "product.*lateral"
    - from: config/prompts.yaml
      to: chain_deriver.py::derive_chain()
      via: "derive_user_lateral_product key auto-selection"
      pattern: "derive_user_lateral_product"
    - from: config/prompts.yaml
      to: chain_drafter.py::h2_lines assembly
      via: "step{N}_sections auto-load"
      pattern: "step[123]_sections.*product"
---

<objective>
Add a new "product" (electronics/smartphone) keyword category to the mc chain system so that keywords like "갤럭시 폴드8 울트라 자급제" are classified as `product` instead of `etc`, using lateral chain direction with product-specific prompts and step sections.

Purpose: Enable product review/comparison/buying-guide content generation for electronics keywords currently falling through to generic `etc` fallback.

Output: Updated config/prompts.yaml (keyword_categories.product + derive_user_lateral_product), config/chain_config.yaml (keyword_mapping.product: lateral), conftest.py (product mock), test_chain_deriver.py (regression + product tests).
</objective>

<execution_context>
@/Users/twinssn/.config/opencode/get-shit-done/workflows/execute-plan.md
@/Users/twinssn/.config/opencode/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phase-28/CONTEXT.md
@.planning/phase-28/RESEARCH.md

<interfaces>
<!-- Key types and contracts the executor needs. Extracted from codebase. -->

From mc_paths.py:
```python
def classify_keyword(keyword: str) -> str:
    """prompts.yaml의 keyword_categories 패턴을 config에서 자동으로 읽어 판별.
    priority 오름차순 순회. etc는 항상 마지막 fallback."""

def resolve_chain_type(keyword: str, override: str = None) -> str:
    """chain_config.yaml의 keyword_mapping에서 category → chain type 매핑."""
```

From chain_deriver.py:
```python
def _validate_lateral_prompts(prompts: dict) -> None:
    """keyword_categories 키로부터 derive_user_lateral_{cat} 존재 여부 자동 검증."""

def derive_chain(seed, chain_type=None, ...) -> int:
    """derive_user_lateral_{category} 키로 category-specific 프롬프트 자동 선택."""
```

From chain_drafter.py:
```python
step_key = f"step{post.get('step', 1)}_sections"
h2_lines = []
for i, tmpl in enumerate(cat_config.get(step_key, [])):
    h2_lines.append(f"{i}. {tmpl.replace('{keyword}', seed_keyword)}")
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add product category config blocks to prompts.yaml + chain_config.yaml</name>
  <files>config/prompts.yaml, config/chain_config.yaml</files>
  <behavior>
    - classify_keyword("갤럭시 폴드8 울트라 자급제") == "product" (pattern: 갤럭시, 자급제)
    - classify_keyword("아이폰 16 프로 가격") == "product" (pattern: 아이폰)
    - classify_keyword("에어팟 프로 3세대") == "product" (pattern: 에어팟)
    - classify_keyword("맥북 프로 M4") == "product" (pattern: 맥북)
    - classify_keyword("PS5 가격") == "product" (pattern: PS5)
    - classify_keyword("닌텐도 스위치2") == "product" (pattern: 닌텐도)
    - classify_keyword("갤럭시 S25 울트라 자급제") == "product" (pattern: 갤럭시)
    - classify_keyword("삼성전자 주가") == "stock" (conflict: stock ~주가 특수 처리 우선)
    - classify_keyword("제주 골프장 추천") == "golf_course" (regression: golf_course priority=10 우선)
    - classify_keyword("서울 워터파크") == "travel" (regression: travel unchanged)
    - resolve_chain_type("갤럭시 폴드8 울트라 자급제") == "lateral" (keyword_mapping.product: lateral)
  </behavior>
  <action>
**Step 1: Add `keyword_categories.product` block to `config/prompts.yaml`**

Insert BEFORE the `etc` block (currently at line 490). Place it after the `medicine` block (line 489). Per D-01 (category name = `product`) and D-02 (priority = 50).

The product block MUST include:

1. `patterns` — Two-tier regex list per RESEARCH.md design:
   - Tier 1 (brand): `(갤럭시|galaxy)`, `(아이폰|iphone)`, `(에어팟|airpods?)`, `(맥북|macbook)`, `(아이패드|ipad)`, `(PS[345]|엑스박스|xbox|닌텐도|switch)`, `(갤럭시워치|애플워치|apple\s*watch)`, `(다이슨|dyson)`, `(소니|sony)`, `(샤오미|xiaomi)`, `(비스포크|bespoke)`
   - Tier 2 (category): `(스마트폰|태블릿|노트북)`, `(자급제)`, `(OLED|QLED|마이크로LED|올레드)`, `(프린터|모니터)`, `(삼성전자|LG전자)`, `(블루투스이어폰|무선이어폰|이어폰)`, `(게이밍|게임기)`
   - NOTE: 삼성전자 is included but `mc_paths.py` line 110-111 has `~주가` special handling that returns "stock" BEFORE pattern matching, so "삼성전자 주가" correctly resolves to stock.

2. `priority: 50` — Between golf_course(10) and default(100). Per RESEARCH.md conflict analysis.

3. `cta_phrases` — Same as all other categories:
   ```
   next_post: 더 알아보기 →
   entry_funnel: '{{ENTRY_LINK}}'
   fallback: 관련 주제 보기 →
   ```

4. `char_count` — Same as other categories (rotcha: 1000-1500, issue_techpawz/techpawz: 1500-2500).

5. `step1_sections` — Product intro flow (per D-03: 스펙 정보 → 비교 분석 → 구매 가이드):
   ```
   - '## {keyword} — 제품 개요와 핵심 스펙'
   - '## {keyword} — 디자인과 주요 특징'
   - '## {keyword} — 경쟁 모델과 비교 포인트'
   - '## 마무리 — {keyword} 핵심 요약'
   ```

6. `step2_sections` — Comparison analysis:
   ```
   - '## {keyword} — 스펙 상세 비교와 벤치마크'
   - '## {keyword} — 실사용 경험과 장단점'
   - '## {keyword} — 가격대와 구매 전략'
   - '## 마무리 — {keyword} 비교 분석 정리'
   ```

7. `step3_sections` — Buying guide:
   ```
   - '## {keyword} — 최종 구매 가이드'
   - '## {keyword} — 구매처 비교와 할인 혜택'
   - '## {keyword} — 초기 설정과 활용 팁'
   - '## 마무리 — {keyword} 구매 결정 지원'
   ```

**Step 2: Add `derive_user_lateral_product` prompt to `config/prompts.yaml`**

Insert after the last existing `derive_user_lateral_*` prompt (after `derive_user_lateral_medicine` at line 528), before the file end. The prompt MUST follow the exact structure from RESEARCH.md section "Code Examples — 2. prompts.yaml":

- Opening: `시드 키워드: "{seed}"` / `키워드 카테고리: {category}`
- Direction: `이 키워드는 **전자기기/상품 리뷰(product)** 방향입니다.`
- Reader perspective: `검색자는 특정 전자기기의 스펙, 가격, 비교 정보를 알아보고 구매를 고려하는 소비자입니다.`
- Flow: `제품 소개 -> 스펙 비교/분석 -> 구매 가이드 순으로 구성하세요.`
- Reader journey: `"이 제품이 뭐지" -> "다른 제품과 어떤 차이가 있지" -> "어디서/how much에 사지"`
- 3-post JSON array with:
  - Step 1: `제품 소개형` — rotcha.kr, category_guess=전자기기/상품, key_points=[제품 개요, 핵심 스펙, 디자인 특징, 경쟁 모델]
  - Step 2: `비교 분석형` — issue.techpawz.com, key_points=[스펙 상세 비교, 벤치마크 결과, 실사용 장단점, 가격 대비 가치]
  - Step 3: `구매 가이드형` — techpawz.com, key_points=[구매처 비교, 할인·프로모션, 초기 설정 팁, 최종 추천]
- Rules section:
  - `각 step의 title, domain, angle, target_keyword, category_guess, key_points(3-5개), image_prompt, image_keyword, bridge_logic를 반드시 포함`
  - `Step 1(제품 소개) -> Step 2(비교 분석) -> Step 3(구매 가이드) 흐름 유지`
  - `스펙 수치는 반드시 제공된 검색 자료에 근거. 없는 수치를 지어내지 말 것`
  - `Step 3에서는 최저가 비교, 쿠팡/SSG 등 구매처, 공식 채널 안내로 수익화 유도`
  - `bridge_logic: 현재 글의 마무리에서 다음 글(Step+1)로 자연스럽게 연결하는 방법`

**Step 3: Add `product: lateral` to `config/chain_config.yaml` keyword_mapping**

At line 93 (after `medicine: lateral`), add:
```yaml
  product: lateral
```

**Step 4: Run classify_keyword tests to verify**

Execute the verification commands below to confirm all 11 behavior conditions pass before completing this task.
  </action>
  <verify>
    <automated>cd /Users/twinssn/projects2/mc && python -c "
from mc_paths import classify_keyword, resolve_chain_type

# REQ-28.1: product classification
assert classify_keyword('갤럭시 폴드8 울트라 자급제') == 'product', 'REQ-28.1 failed'
assert classify_keyword('아이폰 16 프로 가격') == 'product', 'REQ-28.2 failed'
assert classify_keyword('에어팟 프로 3세대') == 'product', 'REQ-28.3 failed'

# REQ-28.4: lateral chain type
assert resolve_chain_type('갤럭시 폴드8 울트라 자급제') == 'lateral', 'REQ-28.4 failed'

# Regression: existing categories unchanged
assert classify_keyword('삼성전자 주가') == 'stock', 'regression: stock failed'
assert classify_keyword('제주 골프장 추천') == 'golf_course', 'regression: golf_course failed'
assert classify_keyword('서울 워터파크') == 'travel', 'regression: travel failed'
assert classify_keyword('타이레놀정 복용법') == 'medicine', 'regression: medicine failed'
assert classify_keyword('근로장려금 신청자격') == 'gov_finance', 'regression: gov_finance failed'

# Additional product keywords
assert classify_keyword('맥북 프로 M4') == 'product', 'macbook failed'
assert classify_keyword('PS5 가격') == 'product', 'PS5 failed'
assert classify_keyword('닌텐도 스위치2') == 'product', 'nintendo failed'

print('All 11 assertions passed')
"
</automated>
  </verify>
  <done>
- `keyword_categories.product` block exists in prompts.yaml with patterns, priority=50, cta_phrases, char_count, step1/2/3_sections
- `derive_user_lateral_product` prompt exists in prompts.yaml with product-specific content flow (제품 소개 → 비교 분석 → 구매 가이드)
- `product: lateral` mapping exists in chain_config.yaml keyword_mapping
- classify_keyword() returns "product" for 7 test keywords
- resolve_chain_type() returns "lateral" for product keywords
- No regression: stock/golf_course/travel/medicine/gov_finance classification unchanged
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Update conftest.py mock + add regression tests to test_chain_deriver.py</name>
  <files>conftest.py, test_chain_deriver.py</files>
  <behavior>
    - conftest.py MOCK_PROMPTS contains "derive_user_lateral_product" key
    - conftest.py MOCK_PROMPTS keyword_categories contains "product" block with step1/2/3_sections
    - Existing test_chain_deriver.py tests continue to pass (no regression)
    - New test: TestProductCategory with classify_keyword/resolve_chain_type tests
    - pytest exits 0 with all tests passing
  </behavior>
  <action>
**Step 1: Update `conftest.py` sample_prompts fixture**

Add `derive_user_lateral_product` to the MOCK_PROMPTS dict (after `derive_user_lateral_etc` at line 158):
```python
"derive_user_lateral_product": "Seed: {seed}\nCategory: {category}\nChain type: lateral (product)\nStep 3 angle: 최종 구매 가이드\nReturn JSON with 3 topics.",
```

Add `product` block to `keyword_categories` dict (after the `etc` block, before the closing `}`):
```python
"product": {
    "patterns": [
        "(갤럭시|galaxy)",
        "(아이폰|iphone)",
        "(에어팟|airpods?)",
        "(맥북|macbook)",
        "(PS[345]|엑스박스|xbox|닌텐도|switch)",
        "(스마트폰|태블릿|노트북)",
        "(자급제)",
    ],
    "step1_sections": [
        "## {keyword} — 제품 개요와 핵심 스펙",
        "## {keyword} — 디자인과 주요 특징",
        "## {keyword} — 경쟁 모델과 비교 포인트",
        "## 마무리 — {keyword} 핵심 요약",
    ],
    "step2_sections": [
        "## {keyword} — 스펙 상세 비교와 벤치마크",
        "## {keyword} — 실사용 경험과 장단점",
        "## {keyword} — 가격대와 구매 전략",
        "## 마무리 — {keyword} 비교 분석 정리",
    ],
    "step3_sections": [
        "## {keyword} — 최종 구매 가이드",
        "## {keyword} — 구매처 비교와 할인 혜택",
        "## {keyword} — 초기 설정과 활용 팁",
        "## 마무리 — {keyword} 구매 결정 지원",
    ],
},
```

**Step 2: Add product category tests to `test_chain_deriver.py`**

Add a new test class `TestProductCategory` after the existing `TestMedicineCategory` class (around line 470). Tests MUST use the same pattern as existing category tests (direct `from mc_paths import classify_keyword` inside each test method):

```python
class TestProductCategory:
    """Phase 28: product(전자기기/상품) 카테고리 분류 테스트."""

    def test_product_brand_keywords(self):
        """ REQ-28.1~28.3: 브랜드 키워드 product 분류 """
        from mc_paths import classify_keyword
        assert classify_keyword("갤럭시 폴드8 울트라 자급제") == "product"
        assert classify_keyword("아이폰 16 프로 가격") == "product"
        assert classify_keyword("에어팟 프로 3세대") == "product"
        assert classify_keyword("맥북 프로 M4") == "product"

    def test_product_category_keywords(self):
        """제품 카테고리 키워드 product 분류"""
        from mc_paths import classify_keyword
        assert classify_keyword("PS5 가격") == "product"
        assert classify_keyword("닌텐도 스위치2") == "product"
        assert classify_keyword("갤럭시 S25 울트라 자급제") == "product"

    def test_product_lateral_direction(self):
        """REQ-28.4: product → lateral chain type"""
        from mc_paths import resolve_chain_type
        assert resolve_chain_type("갤럭시 폴드8 울트라 자급제") == "lateral"
        assert resolve_chain_type("아이폰 16 프로 가격") == "lateral"

    def test_product_no_regression_stock(self):
        """삼성전자 주가 → stock (product priority=50 vs stock ~주가 특수 처리)"""
        from mc_paths import classify_keyword
        assert classify_keyword("삼성전자 주가") == "stock"
        assert classify_keyword("삼성전자주가") == "stock"

    def test_product_no_regression_golf(self):
        """골프 키워드 → golf_course (priority=10 > product=50)"""
        from mc_paths import classify_keyword
        assert classify_keyword("제주 골프장 추천") == "golf_course"
        assert classify_keyword("남서울CC 예약") == "golf_course"

    def test_product_no_regression_travel(self):
        """여행 키워드 → travel (regression check)"""
        from mc_paths import classify_keyword
        assert classify_keyword("서울 워터파크") == "travel"
        assert classify_keyword("제주도 여행 코스") == "travel"
```

**Step 3: Run full test suite to confirm no regression**

Execute `pytest` to verify all existing + new tests pass.
  </action>
  <verify>
    <automated>cd /Users/twinssn/projects2/mc && python -m pytest test_chain_deriver.py::TestKeywordClassification test_chain_deriver.py::TestProductCategory -v</automated>
  </verify>
  <done>
- conftest.py sample_prompts contains "derive_user_lateral_product" key and "product" keyword_categories block
- test_chain_deriver.py has new TestProductCategory class with 6 test methods
- All existing classify_keyword/resolve_chain_type tests pass unchanged (zero regression)
- All new product category tests pass
- Full pytest suite exits 0
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Config → Code | prompts.yaml and chain_config.yaml are loaded by mc_paths.py/chain_deriver.py at runtime. Malformed YAML or regex could cause classification errors or ReDoS. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-28-01 | Tampering | keyword_categories.product.patterns regex | mitigate | Use simple alternation patterns only (no nested quantifiers). All patterns are `(A\|B\|C)` form — no ReDoS risk. |
| T-28-02 | Elevation of Privilege | derive_user_lateral_product prompt content | mitigate | Prompt follows existing lateral template structure. CTA leak prevention enforced by draft_system ABSOLUTE BAN rules. |
| T-28-03 | DoS | classify_keyword() priority traversal | accept | With 11 categories (was 10), worst case is 11 pattern iterations per call. Negligible. |
| T-28-SC | Tampering | YAML config file changes | mitigate | Manual human review of final diff before commit. All patterns visually inspected against RESEARCH.md conflict analysis. |
</threat_model>

<verification>
1. **classify_keyword() unit tests:** All 11 assertions pass (7 product + 4 regression)
2. **resolve_chain_type() unit tests:** product keywords return "lateral"
3. **Full pytest suite:** `pytest` exits 0 with no failures
4. **YAML validity:** Both prompts.yaml and chain_config.yaml parse without error (tested via Python yaml.safe_load in classify_keyword)
5. **derive_user_lateral_product exists:** chain_deriver.py _validate_lateral_prompts() produces no warnings for "product"
</verification>

<success_criteria>
- `keyword_categories.product` block in prompts.yaml with 18 patterns, priority=50, 3 step_sections
- `derive_user_lateral_product` prompt in prompts.yaml with product-specific flow
- `product: lateral` in chain_config.yaml keyword_mapping
- conftest.py MOCK_PROMPTS updated with product mock
- test_chain_deriver.py has 6 new test methods in TestProductCategory class
- All existing tests pass (zero regression)
- classify_keyword("갤럭시 폴드8 울트라 자급제") == "product"
- resolve_chain_type("갤럭시 폴드8 울트라 자급제") == "lateral"
</success_criteria>

<output>
Create `.planning/phases/28-product/28-01-SUMMARY.md` when done
</output>
