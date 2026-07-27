---
phase: 25
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - config/prompts.yaml
  - config/chain_config.yaml
  - mc_paths.py
  - chain_deriver.py
  - conftest.py
  - test_chain_deriver.py
autonomous: true
requirements: ["PH25-01", "PH25-02", "PH25-03"]

must_haves:
  truths:
    - "고객센터 키워드(예: 고객센터 전화번호, AS 접수 방법)가 customer_service 카테고리로 분류된다"
    - "customer_service 카테고리는 depth 방향으로 체인이 생성된다"
    - "Depth 0→1→2 H2 가이드라인이 자연스러운 프로그레션(정보→운영→심화)을 보인다"
    - "기존 291개 테스트가 전부 통과한다"
  artifacts:
    - path: "config/prompts.yaml"
      provides: "customer_service 카테고리 정의 (patterns, char_count, step1/2/3_sections)"
      contains: "customer_service"
    - path: "config/prompts.yaml"
      provides: "derive_user_depth_customer_service 프롬프트 템플릿"
      contains: "derive_user_depth_customer_service"
    - path: "config/chain_config.yaml"
      provides: "customer_service: depth 키워드 매핑"
      contains: "customer_service"
    - path: "mc_paths.py"
      provides: "classify_keyword()에서 customer_service 패턴 매칭"
      contains: "customer_service"
  key_links:
    - from: "config/prompts.yaml"
      to: "mc_paths.py"
      via: "keyword_categories.customer_service.patterns → classify_keyword()"
      pattern: "keyword_categories.*customer_service"
    - from: "config/chain_config.yaml"
      to: "mc_paths.py"
      via: "keyword_mapping.customer_service → resolve_chain_type()"
      pattern: "customer_service.*depth"
    - from: "config/prompts.yaml"
      to: "chain_deriver.py"
      via: "derive_user_depth_customer_service → derive_chain() 프롬프트 선택"
      pattern: "derive_user_depth_customer_service"
    - from: "config/prompts.yaml"
      to: "chain_drafter.py"
      via: "keyword_categories.customer_service.stepN_sections → H2 가이드라인 주입"
      pattern: "step[123]_sections.*고객센터"
---

# Phase 25 Plan: "고객센터" 신규 키워드 카테고리 설계

## Overview

| Task | 내용 | 예상 파일 변경 |
|------|------|---------------|
| Task 1 | `prompts.yaml` + `chain_config.yaml`에 customer_service 카테고리 추가 | `config/prompts.yaml`, `config/chain_config.yaml` |
| Task 2 | `mc_paths.py` classify_keyword()에 customer_service 패턴 매칭 추가 + `chain_deriver.py`에 depth category 프롬프트 탐색 분기 추가 | `mc_paths.py`, `chain_deriver.py` |
| Task 3 | 단위 테스트 (패턴 매칭, H2 선택, 체인 방향, 프롬프트 분기, H2 프로그레션 검증) | `conftest.py`, `test_chain_deriver.py` |

---

## Task 1: customer_service 카테고리 YAML 정의

**파일:** `config/prompts.yaml`, `config/chain_config.yaml`

### 1-1. prompts.yaml — keyword_categories.customer_service 추가

`keyword_categories.stock` 블록 다음에 `customer_service` 블록을 추가한다.

**변경 위치:** `config/prompts.yaml`의 `keyword_categories` 섹션. `stock` 블록(344~378행) 다음, `etc` 블록(379행) 앞.

**추가 내용:**

```yaml
  customer_service:
    patterns:
    - (고객센터|고객지원|고객상담|helpdesk|help.desk|서비스센터|서비스데스크)
    - (as\s*(접수|문의|센터|처리)|a/s\s*(접수|문의|센터|처리))
    - (상담원|상담 연결|전화 상담|채팅 상담|메일 상담)
    - (클레임|불만 접수|민원|이의 제기|보증 수리)
    - (상품권|교환|환불|반품|교환 접수)
    - (운영 시간|영업 시간|연락처|전화 번호|대표 번호)
    cta_phrases:
      next_post: "더 알아보기 →"
      entry_funnel: "{{ENTRY_LINK}}"
      fallback: "관련 주제 보기 →"
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
    - '## {keyword} — 개념과 채널별 특징'
    - '## {keyword} — 업종별 운영 방식 비교'
    - '## {keyword} — 이용 전 꼭 알아둘 것'
    - '## 마무리 — {keyword} 핵심 요약'
    step2_sections:
    - '## {keyword} — 운영 비교와 KPI 설정'
    - '## {keyword} — 고객 응대 스킬과 시스템 도입'
    - '## {keyword} — 고객 만족도 높이는 실전 전략'
    - '## 마무리 — {keyword} 운영 효율화하기'
    step3_sections:
    - '## {keyword} — AI 챗봇과 자동화 트렌드'
    - '## {keyword} — CRM 시스템과 데이터 분석'
    - '## {keyword} — 산업별 벤치마크와 미래 전망'
    - '## 마무리 — {keyword} 고객센터 혁신 방향'
```

**패턴 설계 근거:**

| 패턴 | 매칭 대상 키워드 예시 | 비고 |
|------|---------------------|------|
| `고객센터` | "삼성 고객센터", "네이버 고객센터 전화번호" | 핵심 키워드 |
| `고객지원` | "애플 고객지원", "고객지원 센터" | 영문 매핑 |
| `helpdesk` | "IT helpdesk 구축", "서비스 helpdesk" | 영문 매핑 |
| `AS접수` | "AS 접수 방법", "AS 접수 방법" | 자동차 AS와 구분 — 자동차 키워드가 먼저 매칭 |
| `상담원` | "상담원 연결 방법", "상담원 친절도" | 상담 관련 |
| `클레임` | "클레임 접수", "고객 클레임 처리" | 클레임 관리 |
| `운영 시간` | "고객센터 운영 시간", "영업 시간 문의" | 운영 정보 |

**주의사항:**

- `AS` 패턴은 `automotive` 패턴(하이브리드|전기차|SUV|...)과 겹치지 않음. `classify_keyword()`는 travel→stock→real_estate→automotive→**customer_service**→etc 순서로 매칭하므로, "현대자동차 AS 접수"는 automotive 패턴이 먼저 매칭되어 automotive로 분류됨.
- `고객센터` 패턴이 "여행 호텔 프런트 데스크(고객센터)" 같은 여행 키워드를 가로채지 않음 — travel 패턴이 먼저 매칭됨.
- `상품권|교환|환불|반품` 패턴은 이커머스 CS 관련. 여행 쿠폰/환불은 travel 패턴이 먼저 매칭.

### 1-2. prompts.yaml — derive_user_depth_customer_service 추가

`derive_user_lateral_etc` 블록(53~59행) 다음에 추가한다.

**변경 위치:** `config/prompts.yaml`. `derive_user_lateral_etc` 블록 끝(59행) 다음.

**추가 내용:**

```yaml
derive_user_depth_customer_service: "시드 키워드: \"{seed}\"\n키워드 카테고리: {category}\n\n이 키워드는 **깊이 파고들기(Depth)** 방향이 적합합니다.\nStep 1(기초/정보형) → Step 2(분석/응용형) → Step 3(전문/심화형) 순서로 체인을 구성하세요.\n\n고객센터 키워드의 특성:\n- Step 1: 고객센터 개념, 채널별 특징(전화/채팅/메일/카카오톡), 업종별 차이, 핵심 운영 요소 소개\n- Step 2: 운영 비교, KPI/CSAT 설정, 고객 응대 스킬, 시스템 도입 전략, 실전 개선 방법\n- Step 3: AI 챗봇, CRM 트렌드, 자동화, 산업별 벤치마크, 미래 전망, 심층 분석\n\n다음 조건을 만족하는 블로그 체인을 JSON 배열로 생성하세요:\n\n[\n  {{\n    \"step\": 1,\n    \"depth\": 0,\n    \"domain\": \"rotcha.kr\",\n    \"title\": \"시드 키워드에 대한 개요 및 소개 (일반 독자, 기초/정보형)\",\n    \"angle\": \"고객센터 개념과 채널별 특징 소개\",\n    \"target_keyword\": \"메인 키워드\",\n    \"category_guess\": \"비즈니스/서비스\",\n    \"key_points\": [\"핵심 포인트 3-5개\", \"...\"],\n    \"image_prompt\": \"이미지 생성을 위한 영어 프롬프트. 플랫한 스타일의 디지털 일러스트레이션 묘사\",\n    \"image_keyword\": \"이미지 파일명용 영문 키워드 (공백은 - 로)\",\n    \"bridge_logic\": \"Step 2에서 다룰 운영 비교 및 시스템 도입 심화 내용 예고\"\n  }},\n  {{\n    \"step\": 2,\n    \"depth\": 1,\n    \"domain\": \"issue.techpawz.com\",\n    \"title\": \"Step 1 내용을 심화/구체화한 실용 가이드 (실무자, 분석/응용형)\",\n    \"angle\": \"고객센터 운영 비교와 실전 개선 전략\",\n    \"target_keyword\": \"비교 키워드\",\n    \"category_guess\": \"비즈니스/서비스\",\n    \"key_points\": [\"핵심 포인트 3-5개\", \"...\"],\n    \"image_prompt\": \"이미지 생성을 위한 영어 프롬프트\",\n    \"image_keyword\": \"이미지 파일명용 영문 키워드\",\n    \"bridge_logic\": \"Step 3에서 다룰 AI/자동화/CRM 트렌드 심화 내용 예고\"\n  }},\n  {{\n    \"step\": 3,\n    \"depth\": 2,\n    \"domain\": \"techpawz.com\",\n    \"title\": \"Step 2 주제를 기술적/미래지향적으로 확장 (전문가, 전문/심화형)\",\n    \"angle\": \"고객센터 AI 자동화와 산업 트렌드 분석\",\n    \"target_keyword\": \"심화 키워드\",\n    \"category_guess\": \"비즈니스/기술\",\n    \"key_points\": [\"핵심 포인트 3-5개\", \"...\"],\n    \"image_prompt\": \"이미지 생성을 위한 영어 프롬프트\",\n    \"image_keyword\": \"이미지 파일명용 영문 키워드\",\n    \"bridge_logic\": \"AI 챗봇과 CRM 트렌드를 통한 고객센터 혁신 방향 제시\"\n  }}\n]\n\n규칙:\n- 각 step의 title, domain, angle, target_keyword, category_guess, key_points(3-5개), image_prompt, image_keyword, bridge_logic를 반드시 포함\n- 각 step은 이전 단계보다 더 깊이 파고드는 방향\n- Step 1은 \"무엇인가\" (고객센터 개념, 채널, 업종별 차이)\n- Step 2는 \"어떻게 하는가\" (운영 비교, KPI, 응대 스킬, 시스템 도입)\n- Step 3은 \"왜 그런가 / 딥다이브\" (AI, CRM, 트렌드, 미래 전망)\n- bridge_logic: 현재 글의 마무리에서 다음 글(Step+1)로 자연스럽게 연결하는 방법\n"
```

### 1-3. chain_config.yaml — keyword_mapping 추가

`keyword_mapping` 섹션(91~96행)에 `customer_service: depth` 추가.

**변경 위치:** `config/chain_config.yaml` 95행(`stock: depth`) 다음.

**변경 내용:**

```yaml
  customer_service: depth
```

**근거:** CONTEXT.md에서 "점진적 깊이 프로그레션" 명시 → depth 방향. rotcha(기초) → issue.techpawz(운영) → techpawz(심화) 흐름.

### 검증

```bash
python -c "
import yaml
with open('config/prompts.yaml') as f:
    p = yaml.safe_load(f)
kc = p['keyword_categories']
assert 'customer_service' in kc, 'customer_service 키 카테고리 없음'
assert kc['customer_service']['patterns'], 'patterns 비어있음'
assert kc['customer_service']['step1_sections'], 'step1_sections 비어있음'
assert kc['customer_service']['step2_sections'], 'step2_sections 비어있음'
assert kc['customer_service']['step3_sections'], 'step3_sections 비어있음'
assert 'derive_user_depth_customer_service' in p, 'derive 프롬프트 없음'
print('✅ prompts.yaml customer_service 검증 통과')

with open('config/chain_config.yaml') as f:
    c = yaml.safe_load(f)
assert c['keyword_mapping']['customer_service'] == 'depth', 'keyword_mapping customer_service ≠ depth'
print('✅ chain_config.yaml keyword_mapping 검증 통과')
"
```

---

## Task 2: classify_keyword() 패턴 매칭 + chain_deriver.py depth 프롬프트 탐색

**파일:** `mc_paths.py`, `chain_deriver.py`

### 2-1. mc_paths.py — classify_keyword()에 customer_service 추가

**변경 위치:** `mc_paths.py` 115행.

**현재 코드 (115행):**
```python
for cat_name in ("travel", "stock", "real_estate", "automotive", "etc"):
```

**변경 후:**
```python
for cat_name in ("travel", "stock", "real_estate", "automotive", "customer_service", "etc"):
```

**근거:** `customer_service`를 `etc` 앞에 배치하여, 고객센터 관련 키워드가 `etc`로 fallback되기 전에 매칭되도록 함. `classify_keyword()`의 패턴은 `prompts.yaml`의 `keyword_categories`에서 읽어오므로, YAML에 패턴이 추가되면 자동으로 매칭됨.

### 2-2. mc_paths.py — classify_keyword() docstring 업데이트

**변경 위치:** `mc_paths.py` 102행.

**현재 코드 (102행):**
```python
    Returns: "travel" | "real_estate" | "automotive" | "stock" | "etc"
```

**변경 후:**
```python
    Returns: "travel" | "real_estate" | "automotive" | "stock" | "customer_service" | "etc"
```

### 2-3. conftest.py — sample_prompts에 customer_service 추가

**변경 위치:** `conftest.py` 158행(`derive_user_lateral_etc` 항목) 다음.

**추가 내용:**
```python
        "derive_user_depth_customer_service": "Seed: {seed}\nCategory: {category}\nChain type: depth (customer_service)\nStep 3 angle: AI 챗봇과 CRM 트렌드 분석\nReturn JSON with 3 topics.",
```

`keyword_categories` 딕셔너리에도 customer_service 키 추가 (`stock` 블록 다음, `etc` 블록 앞):

```python
            "customer_service": {
                "patterns": [
                    "(고객센터|고객지원|고객상담|helpdesk|help.desk|서비스센터|서비스데스크)",
                    "(as\s*(접수|문의|센터|처리)|a/s\s*(접수|문의|센터|처리))",
                    "(상담원|상담 연결|전화 상담|채팅 상담|메일 상담)",
                    "(클레임|불만 접수|민원|이의 제기|보증 수리)",
                    "(상품권|교환|환불|반품|교환 접수)",
                    "(운영 시간|영업 시간|연락처|전화 번호|대표 번호)",
                ],
                "step1_sections": [
                    "## {keyword} — 개념과 채널별 특징",
                    "## {keyword} — 업종별 운영 방식 비교",
                    "## {keyword} — 이용 전 꼭 알아둘 것",
                    "## 마무리 — {keyword} 핵심 요약",
                ],
                "step2_sections": [
                    "## {keyword} — 운영 비교와 KPI 설정",
                    "## {keyword} — 고객 응대 스킬과 시스템 도입",
                    "## {keyword} — 고객 만족도 높이는 실전 전략",
                    "## 마무리 — {keyword} 운영 효율화하기",
                ],
                "step3_sections": [
                    "## {keyword} — AI 챗봇과 자동화 트렌드",
                    "## {keyword} — CRM 시스템과 데이터 분석",
                    "## {keyword} — 산업별 벤치마크와 미래 전망",
                    "## 마무리 — {keyword} 고객센터 혁신 방향",
                ],
            },
```

### 2-4. chain_deriver.py — depth category 프롬프트 탐색 분기 추가

**변경 위치:** `chain_deriver.py` 72~78행 (`elif resolved_type == "lateral":` 블록 앞).

**현재 코드 (66~78행):**
```python
category_key = f"derive_user_lateral_{category}"
if category_key in prompts:
    derive_key = category_key
    if resolved_type == "lateral":
        print(f"    [lateral] Using category-specific prompt: {category_key}")
    else:
        print(f"    [{resolved_type}] Using category-specific prompt: {category_key}")
elif resolved_type == "lateral":
    etc_fallback = "derive_user_lateral_etc"
    if etc_fallback in prompts:
        derive_key = etc_fallback
        print(f"[mc] ⚠️ No lateral prompt for category '{category}', falling back to 'etc'")
    # else: keep fallback key (= derive_user_lateral generic)
```

**변경 후:**
```python
category_key = f"derive_user_lateral_{category}"
if category_key in prompts:
    derive_key = category_key
    if resolved_type == "lateral":
        print(f"    [lateral] Using category-specific prompt: {category_key}")
    else:
        print(f"    [{resolved_type}] Using category-specific prompt: {category_key}")
elif resolved_type == "depth":
    # Phase 25: depth 방향 카테고리 전용 프롬프트 탐색
    depth_cat_key = f"derive_user_depth_{category}"
    if depth_cat_key in prompts:
        derive_key = depth_cat_key
        print(f"    [depth] Using category-specific prompt: {depth_cat_key}")
elif resolved_type == "lateral":
    etc_fallback = "derive_user_lateral_etc"
    if etc_fallback in prompts:
        derive_key = etc_fallback
        print(f"[mc] ⚠️ No lateral prompt for category '{category}', falling back to 'etc'")
    # else: keep fallback key (= derive_user_lateral generic)
```

**근거:** 현재 코드는 `derive_user_lateral_{category}`만 탐색한다. `customer_service`는 `depth` 방향이므로 `derive_user_depth_customer_service` 프롬프트가 prompts.yaml에 있어도 탐색되지 않는다. 이 분기를 추가해야 Phase 25의 고객센터 전용 프롬프트가 실제로 사용된다.

### 검증

```bash
# classify_keyword 테스트
python -c "
from mc_paths import classify_keyword
assert classify_keyword('삼성 고객센터 전화번호') == 'customer_service'
assert classify_keyword('AS 접수 방법') == 'customer_service'
assert classify_keyword('고객지원 센터') == 'customer_service'
assert classify_keyword('helpdesk 구축') == 'customer_service'
assert classify_keyword('클레임 처리 방법') == 'customer_service'
assert classify_keyword('상담원 연결') == 'customer_service'
# 기존 카테고리 영향 없음 확인
assert classify_keyword('제주도 여행') == 'travel'
assert classify_keyword('ETF 투자') == 'stock'
assert classify_keyword('Python 프로그래밍') == 'etc'
print('✅ classify_keyword customer_service 테스트 통과')
"

# resolve_chain_type 테스트
python -c "
from mc_paths import resolve_chain_type
assert resolve_chain_type('삼성 고객센터') == 'depth'
assert resolve_chain_type('고객센터 전화번호') == 'depth'
print('✅ resolve_chain_type customer_service → depth 테스트 통과')
"
```

---

## Task 3: 단위 테스트

**파일:** `test_chain_deriver.py`

### 3-1. TestClassifyKeyword — customer_service 패턴 매칭 테스트

`test_chain_deriver.py`의 `TestClassifyKeyword` 클래스(8~118행)에 메서드 추가.

```python
    def test_customer_service_keyword_returns_customer_service(self):
        """고객센터 키워드 → customer_service."""
        from mc_paths import classify_keyword

        assert classify_keyword("삼성 고객센터 전화번호") == "customer_service"

    def test_customer_service_helpdesk(self):
        """helpdesk 키워드 → customer_service."""
        from mc_paths import classify_keyword

        assert classify_keyword("IT helpdesk 구축") == "customer_service"

    def test_customer_service_as_keyword(self):
        """AS 접수 키워드 → customer_service (automotive와 구분)."""
        from mc_paths import classify_keyword

        assert classify_keyword("AS 접수 방법") == "customer_service"
        # 자동차 키워드는 automotive로 분류 (automotive 패턴이 먼저 매칭)
        assert classify_keyword("현대자동차 AS") == "automotive"

    def test_customer_service_claims(self):
        """클레임/민원 키워드 → customer_service."""
        from mc_paths import classify_keyword

        assert classify_keyword("고객 클레임 처리") == "customer_service"
        assert classify_keyword("민원 접수 방법") == "customer_service"

    def test_customer_service_does_not_affect_travel(self):
        """여행 키워드가 customer_service로 분류되지 않음."""
        from mc_paths import classify_keyword

        assert classify_keyword("제주도 여행 코스") == "travel"
        assert classify_keyword("서울 호텔") == "travel"
```

### 3-2. TestResolveChainType — customer_service 방향 테스트

`test_chain_deriver.py`의 `TestResolveChainType` 클래스(121~164행)에 메서드 추가.

```python
    def test_customer_service_maps_to_depth(self):
        """customer_service → depth (keyword_mapping)."""
        from mc_paths import resolve_chain_type

        assert resolve_chain_type("삼성 고객센터") == "depth"
        assert resolve_chain_type("고객센터 전화번호") == "depth"
        assert resolve_chain_type("helpdesk 구축") == "depth"
```

### 3-3. TestDeriveLateralCategoryDispatch — depth 방향 프롬프트 분기 테스트

`test_chain_deriver.py`의 `TestDeriveLateralCategoryDispatch` 클래스(272~341행) 다음에 새 클래스 추가.

```python
class TestDeriveDepthCategoryDispatch:
    """category별 depth 프롬프트 분기 검증."""

    DEPTH_ANGLES = {
        "customer_service": "고객센터 개념과 채널별 특징 소개",
    }

    @pytest.mark.parametrize("keyword,expected_category", [
        ("삼성 고객센터", "customer_service"),
        ("helpdesk 구축", "customer_service"),
    ])
    @patch("chain_deriver.generate")
    @patch("chain_deriver.load_config")
    @patch("chain_deriver.load_prompts")
    @patch("chain_deriver.db.create_chain")
    @patch("chain_deriver.db.create_chain_post")
    def test_depth_category_uses_correct_angle(
        self,
        mock_create_post,
        mock_create_chain,
        mock_load_prompts,
        mock_load_config,
        mock_generate,
        sample_chain_config,
        sample_prompts,
        keyword,
        expected_category,
    ):
        """category별 depth derive prompt에 올바른 angle 포함."""
        mock_load_config.return_value = sample_chain_config
        mock_load_prompts.return_value = sample_prompts
        mock_create_chain.return_value = 42

        mock_generate.return_value = {
            "content": json.dumps([
                {"title": "Step 1", "depth": 0, "step": 1, "angle": "기초", "category_guess": "일반", "bridge_logic": "다음"},
                {"title": "Step 2", "depth": 1, "step": 2, "angle": "비교", "category_guess": "일반", "bridge_logic": "다음"},
                {"title": "Step 3", "depth": 2, "step": 3, "angle": "실전", "category_guess": "일반", "bridge_logic": "완결"},
            ]),
            "model": "test-model",
            "provider": "test",
            "tier": "default",
            "tokens_used": 100,
        }

        from chain_deriver import derive_chain
        derive_chain(keyword)  # chain_type 미지정 → resolve_chain_type으로 depth 결정

        user_prompt = mock_generate.call_args.kwargs["user_prompt"]

        expected_angle = self.DEPTH_ANGLES[expected_category]
        assert expected_angle in user_prompt, (
            f"[{expected_category}] '{expected_angle}' not in prompt:\n{user_prompt}"
        )
```

### 3-4. TestKeywordCategoriesH2E2E — H2 가이드라인 E2E 테스트

`test_chain_drafter.py`의 `TestKeywordCategoriesH2E2E` 클래스(727행)에 메서드 추가.

```python
    @patch("chain_drafter._load_chain_cfg")
    @patch("chain_drafter._load_prompts")
    @patch("chain_drafter.generate")
    def test_customer_service_keyword_uses_cs_h2_template(
        self,
        mock_gen,
        mock_prompts,
        mock_cfg,
        sample_chain_config,
        sample_prompts,
    ):
        """customer_service 키워드 → user_prompt에 customer_service H2 템플릿 포함."""
        mock_cfg.return_value = sample_chain_config
        mock_prompts.return_value = sample_prompts
        mock_gen.return_value = {
            "content": "---\ntitle: Mock\n---\n\n## Mock heading\nbody",
            "model": "test",
            "provider": "test",
        }

        from chain_drafter import draft_single_post

        # step=1, seed="삼성 고객센터" → classify_keyword → customer_service
        post = {
            "step": 1,
            "depth": 0,
            "title": "삼성 고객센터 안내",
            "angle": "기초 정보",
            "target_keyword": "삼성 고객센터",
            "category_guess": "비즈니스/서비스",
            "key_points": ["핵심 1", "핵심 2"],
            "chain_type": "depth",
        }

        draft_md, meta = draft_single_post(
            post,
            [post],
            "삼성 고객센터",
        )

        user_prompt = mock_gen.call_args[0][1]

        assert "개념과 채널별 특징" in user_prompt, (
            f"customer_service step1 H2 누락. prompt:\n{user_prompt[:500]}"
        )
        assert "업종별 운영 방식 비교" in user_prompt, (
            "customer_service step1 H2 #2 누락"
        )
```

### 3-5. TestCustomerServiceH2Progression — H2 프로그레션 구조 검증

`test_chain_drafter.py`에 새 클래스 추가. Depth 0→1→2 H2 가이드라인이 자연스러운 프로그레션을 보이는지 검증.

```python
class TestCustomerServiceH2Progression:
    """고객센터 카테고리 Depth별 H2 프로그레션 검증."""

    def test_step1_h2_has_concept_keywords(self):
        """Depth 0 (step1) H2에 '개념', '채널', '특징' 등 기초 키워드 포함."""
        import yaml
        with open("config/prompts.yaml", encoding="utf-8") as f:
            prompts = yaml.safe_load(f)
        step1 = prompts["keyword_categories"]["customer_service"]["step1_sections"]
        step1_text = " ".join(step1)
        assert "개념" in step1_text or "채널" in step1_text or "특징" in step1_text, (
            f"step1 H2에 기초 키워드 누락: {step1}"
        )

    def test_step2_h2_has_operation_keywords(self):
        """Depth 1 (step2) H2에 '운영', 'KPI', '시스템' 등 운영 키워드 포함."""
        import yaml
        with open("config/prompts.yaml", encoding="utf-8") as f:
            prompts = yaml.safe_load(f)
        step2 = prompts["keyword_categories"]["customer_service"]["step2_sections"]
        step2_text = " ".join(step2)
        assert "운영" in step2_text or "KPI" in step2_text or "시스템" in step2_text, (
            f"step2 H2에 운영 키워드 누락: {step2}"
        )

    def test_step3_h2_has_advanced_keywords(self):
        """Depth 2 (step3) H2에 'AI', 'CRM', '트렌드' 등 심화 키워드 포함."""
        import yaml
        with open("config/prompts.yaml", encoding="utf-8") as f:
            prompts = yaml.safe_load(f)
        step3 = prompts["keyword_categories"]["customer_service"]["step3_sections"]
        step3_text = " ".join(step3)
        assert "AI" in step3_text or "CRM" in step3_text or "트렌드" in step3_text, (
            f"step3 H2에 심화 키워드 누락: {step3}"
        )

    def test_h2_progression_depth_increases(self):
        """Depth 0→1→2로 갈수록 H2 키워드가 심화됨 (정보→운영→심화 흐름)."""
        import yaml
        with open("config/prompts.yaml", encoding="utf-8") as f:
            prompts = yaml.safe_load(f)
        cs = prompts["keyword_categories"]["customer_service"]
        s1 = " ".join(cs["step1_sections"])
        s2 = " ".join(cs["step2_sections"])
        s3 = " ".join(cs["step3_sections"])
        # step1은 기초, step2는 운영, step3은 심화 키워드를 포함해야 함
        basic_kw = {"개념", "채널", "특징", "기초", "소개"}
        ops_kw = {"운영", "KPI", "시스템", "전략", "실전"}
        adv_kw = {"AI", "CRM", "트렌드", "자동화", "미래"}
        assert any(k in s1 for k in basic_kw), f"step1에 기초 키워드 없음: {s1}"
        assert any(k in s2 for k in ops_kw), f"step2에 운영 키워드 없음: {s2}"
        assert any(k in s3 for k in adv_kw), f"step3에 심화 키워드 없음: {s3}"
```

### 검증

```bash
# 기존 테스트 회귀 확인 (291개 전부 통과)
pytest test_chain_deriver.py -x -v

# customer_service 신규 테스트만 실행
pytest test_chain_deriver.py -x -v -k "customer_service"

# H2 E2E 테스트
pytest test_chain_drafter.py -x -v -k "customer_service"

# 전체 테스트 회귀 확인
pytest --tb=short 2>&1 | tail -5
```

---

## Task 의존도

```
Task 1 (YAML 정의)
  ↓
Task 2 (Python 코드 변경)
  ↓
Task 3 (테스트)
```

Task 1 → Task 2 순서 필수 (prompts.yaml에 패턴이 있어야 classify_keyword가 매칭).
Task 2 → Task 3 순서 필수 (코드 변경 후 테스트 실행).

---

## 검증 계획

| 검증 항목 | 검증 방법 | 기대 결과 |
|-----------|----------|----------|
| prompts.yaml customer_service 카테고리 존재 | `python -c "import yaml; ..."` | 키 존재, patterns非空, step1/2/3非空 |
| derive_user_depth_customer_service 프롬프트 존재 | `python -c "import yaml; ..."` | 프롬프트 키 존재 |
| chain_config.yaml keyword_mapping | `python -c "import yaml; ..."` | `customer_service: depth` |
| classify_keyword("삼성 고객센터") | `python -c "from mc_paths import classify_keyword; ..."` | `"customer_service"` |
| classify_keyword("AS 접수 방법") | `python -c` | `"customer_service"` |
| classify_keyword("현대자동차 AS") | `python -c` | `"automotive"` (기존 영향 없음) |
| classify_keyword("제주도 여행") | `python -c` | `"travel"` (기존 영향 없음) |
| resolve_chain_type("고객센터") | `python -c` | `"depth"` |
| 기존 291개 테스트 회귀 | `pytest --tb=short` | 291 passed |
| 신규 customer_service 테스트 | `pytest -k customer_service` | all passed |
| H2 가이드라인 E2E | `pytest -k customer_service_keyword_uses` | "개념과 채널별 특징" 포함 |
| H2 프로그레션 구조 | `pytest -k TestCustomerServiceH2Progression` | step1 기초, step2 운영, step3 심화 키워드 포함 |

---

## 성공 기준

1. **[검증불가] 패턴 매칭:** `customer_service` 키워드 패턴이 prompts.yaml에 올바르게 추가됨. 검증 수단: `python -c` 스크립트로 classify_keyword() 호출하여 customer_service 반환 확인
2. **[검증불가] 키워드 분류:** "고객센터 전화번호", "AS 접수 방법" 같은 키워드가 `customer_service`로 분류됨. 검증 수단: `python -c` 스크립트
3. **[검증불가] 체인 방향:** `customer_service`는 depth 방향으로 설정됨. 검증 수단: `python -c` 스크립트로 resolve_chain_type() 호출
4. **[검증불가] H2 프로그레션:** Depth 0→1→2 H2 가이드라인이 자연스러운 프로그레션(정보→운영→심화)을 보임. 검증 수단: prompts.yaml 직접 확인
5. **[검증불가] 기존 테스트 회귀:** 기존 291개 테스트가 전부 통과. 검증 수단: `pytest`
6. **[검증불가] 신규 테스트:** 5개 이상 신규 테스트 추가 통과. 검증 수단: `pytest -k customer_service`
7. **[검증불가] 프롬프트 분기:** `derive_user_depth_customer_service` 프롬프트가 depth 방향 customer_service 키워드에 선택됨. 검증 수단: `pytest -k test_depth_category_uses_correct_angle`

---

## 롤아웃 전략

1. **Task 1 먼저:** YAML 설정 변경 (prompts.yaml + chain_config.yaml)
2. **Task 2 다음:** Python 코드 변경 (mc_paths.py + conftest.py)
3. **Task 3 마지막:** 테스트 작성 + 실행
4. **전체 회귀:** `pytest --tb=short`로 291개 기존 테스트 + 신규 테스트 전부 통과 확인
5. **라이브 테스트 (선택):** `python chain_publisher.py --seed "삼성 고객센터"`로 실제 체인 생성 확인

---

## 잔존 위험

- **[부분검증] `as\s*(접수|문의|센터|처리)` 패턴 정규식:** `as` 소문자 매칭 + 그룹 구조로 수정됨. `AS접수`, `as 접수`, `A/S 접수` 등 다양한 표현 매칭 검증 필요.
- **[검증불가] `상품권|교환|환불|반품` 패턴과 travel 키워드 충돌:** "여행 상품권 환불"은 travel 패턴이 먼저 매칭되어 travel로 분류됨. 그러나 "고객센터 상품권 환불"은 customer_service로 분류될 수 있음 — 의도된 동작인지 추가 확인 필요.
- **[부분검증] conftest.py sample_prompts의 keyword_categories 패턴이 실제 prompts.yaml과 100% 일치하지 않음:** 테스트 fixture는 실제 설정과 다를 수 있으나, classify_keyword()는 실제 prompts.yaml을 읽으므로 테스트 결과에 영향 없음.
