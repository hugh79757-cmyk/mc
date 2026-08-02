# RESEARCH.md — Phase 35: 실발행 재검증 + use_context 효과 분석 + 카테고리 불일치 + 중간 CTA 카드 구현

---

## Executive Summary

Phase 35는 4개 핵심 연구 주제를 다룬다:

1. **실발행 재검증 (#378/#405)**: Chain #378(전체 스텝 발행 실패 후 재발행 검증 필요)와 Chain #405(프롬프트 릭 사고 후 재발행으로 정상화)의 실발행 재검증 기준 정의
2. **use_context=True 릭 0 근거**: 검색 컨텍스트(Naver API)가 prompt leak 방지에 미치는 효과 실측 및 "리뷰형 step 검색 컨텍스트 우선" 정책 설계 (CONTEXT.md 후보)
3. **카테고리 불일치**: `classify_keyword('뉴발란스 740')` → `etc` 반환 vs DB `category_guess='쇼핑/소비'` 저장 — derive/draft/publish 단계 간 분류 불일치 원인 추적 및 해결책
4. **중간 CTA 카드 구현**: Phase 17 CTA 시나리오 설계(5개 카테고리, 내부/외부 CTA 분리, 플레이스홀더 `{{ENTRY_LINK}}`/`{{FUNNEL_LINK}}`)를 기존 `chain_card_injector.py`에 통합 구현

---

## 1. 실발행 재검증 (#378/#405)

### 1.1 Chain #378 — JSON 메타데이터 잔류로 Step 1/2 발행 실패 (Phase 33)

**문제**: Chain #378 발행 시 Step 3(techpawz)은 성공했으나 Step 1(rotcha), Step 2(issue.techpawz) 발행 실패.

**근본 원인** (`.planning/phases/phase-33/CONTEXT.md` 분석):
- AI 출력에 JSON 메타데이터(`image_type`, `chart_type`, `image_keyword`)가 평문/들여쓰기/다중라인으로 포함
- `parse_ai_output()` → `_extract_meta_from_raw()`가 코드펜스(```json) 있는 JSON만 탐지 → 평문 JSON 누락
- `_extract_body_from_raw()`가 코드펜스 JSON만 정규식 제거 → 평문 JSON 잔류
- `_extract_clean_body()`의 `is_raw_json`(line 117)이 **줄 단위** 탐지라 들여쓰기/다중라인 JSON 미탐지
- `_verify_before_deploy()`의 `bare_json` 정규식이 Hugo 빌드 산출물에서 잔류 JSON 발견 → `DeployValidationError`
- `_publish_hugo()`가 예외 처리 시 `("", "hugo", "")` 반환 → `publish_chain()`에서 `url` falsy 판정 → `"Step X failed"`

**해결 현황**: Phase 33에서 `chain_models.py` 파싱 분리 로직 전면 재설계(중괄호 깊이 카운팅), `chain_publisher_core.py` 2차 방어(블록 단위 탐지), 관측성 로깅 추가로 수정 완료 (PLAN 승인 대기 중).

**재검증 기준**:
```bash
# Chain #378 재발행 검증 명령
python chain_publisher.py --chain-id 378 --publish
```
**성공 조건** (Phase 33 CONTEXT.md §검증 기준):
- Step 1/2/3 모두 `✅ Step X published: <url>` 출력
- 배포 검증 통과 (JSON 잔류 0, 광고 슬롯 ≤3, 이미지 참조 정상)
- 카드 주입 정상 (Step 1 next URL 존재 → `✅ Step 1 next card injected`)

### 1.2 Chain #405 — 프롬프트 릭 사고 후 수동 재발행으로 정상화 (Phase 34)

**문제**: Chain #405(뉴발란스 740) s3(techpawz) 라이브 본문에 프롬프트 지침 문단 노출.

**사고 내용** (`.planning/phases/phase-34/CONTEXT.md`):
- 동일 프롬프트·동일 모델(deepseek-v4-flash)로 4회 생성 → 2회에서 사고 과정/규칙 재인용 본문 유출
- RUN 3: `주의: "하시기 바랍니다" 금지… 피하자.` / `표 2: 구매 경로별 특징.` / `제공된 참고 자료가 없지만…`
- RUN 4: `프롬프트는 "참고 자료에 없는 구체적 수치를 절대 만들지 마세요"라고 했지만…` / `이미지 플레이스홀더: 썸네일용은 본문 어디에?`
- **미제거 원인**: 발행 safety net(`strip_leaks` reasoning_leak)이 **라인 단위 매칭**(매칭 라인 → 다음 빈 줄까지 문단 제거)이라, **문단 중간에 삽입된 지침**은 시작 라인이 매칭되지 않아 제거 실패.

**해결 현황**: 수동 정제·재발행으로 라이브는 정상화됨. Phase 34에서 근본 개선(C: raw_output 보존, A: 프롬프트 메타 대화 금지 + temperature 0.7, B: 문단 단위 고특이도 정제) 추진 중.

**재검증 기준**:
```bash
# Chain #405 재발행 검증 (이미 수동 재발행 완료 — 라이브 확인만 필요)
curl -s https://techpawz.com/posts/뉴발란스-740-20240801-s3/ | grep -c "프롬프트에서는\|프롬프트는.*라고 했\|금지어:\|피하자\|만들지 말 것\|이미지 플레이스홀더\|제공된 참고 자료"
# 기대값: 0건
```

---

## 2. use_context=True 릭 0 근거 → "리뷰형 step 검색 컨텍스트 우선"

### 2.1 검색 컨텍스트 주입 메커니즘 (`chain_drafter.py:296-324`)

```python
if use_context:
    client = NaverSearchClient()
    angle_map = {"기초": "basic", "분석": "advanced", "전문": "expert",
                 "구매": "basic", "절약": "advanced", "금융": "expert",
                 "주제": "basic", "비교": "advanced", "비즈니스": "expert"}
    angle_key = angle_map.get(angle_first, "webkr")
    ok, ctx = retrieve_context_for_post(seed_keyword, angle_key, client, cfg=chain_cfg)
    if ok:
        ctx, _ = validate_and_fix_years(ctx, fix_mode=True)
        update_post_context(post["id"], ctx)
        user_prompt += "\n\n" + ctx
```

**컨텍스트 형식** (`search_retriever.py:184-195`):
```markdown
## 참고 자료

다음은 이 글의 주제와 관련된 검색 결과입니다. 내용을 참고하여 풍부한 글을 작성하세요.

### 1. 검색 결과 제목
> 검색 결과 설명

### 2. 검색 결과 제목
> 검색 결과 설명
...
```

### 2.2 왜 검색 컨텍스트가 릭을 방지하는가?

| 메커니즘 | 설명 |
|----------|------|
| **사실 근거 제공** | AI가 "지어내기" 대신 검색 결과 기반으로 작성 → 환각/규칙 재인용 감소 |
| **프롬프트 주의 분산** | 시스템 프롬프트의 규칙 밀도 높은 지침보다 검색 결과가 더 가까운 컨텍스트 → 지침 준수 압박 완화 |
| **구조적 제약** | `## 참고 자료` 섹션이 본문 앞에 오면서 AI가 "계획/검토" 모드 대신 "작성" 모드로 진입 |
| **연도 검증** | `validate_and_fix_years()`가 과거연도+최신 조합 보정 → 연도 관련 환각 차단 |

### 2.3 실측 데이터 (Phase 34 T6 재현 테스트)

**테스트 코드** (`test_t5_t6_regression.py::TestT6ManifestationRate::test_use_context_true_manifestation`):
```python
for i in range(3):
    draft_md, meta, raw_output = draft_single_post(post, [post], kw, use_context=True)
    raw_found = scan_8_signatures(raw_output)
    published_body = processor.process(raw_output, leak_context="body")
    pub_found = scan_8_signatures(published_body)
```

**주의**: 현재 테스트는 `mock_ai_calls` 픽스처로 AI 호출을 모킹하여 **실제 모델 호출이 아님**. Phase 34 PLAN §T6에서 "적용 전 vs 적용 후 비교 측정" 시 **실제 deepseek-v4-flash 호출**로 재현 테스트 필요.

**Phase 34 CONTEXT.md §검증 계획**에서 명시:
> 1. 재현 테스트를 `use_context=True`(검색 컨텍스트 有)로도 수행 — 이전 진단은 `use_context=False`였음. 컨텍스트 유무에 따른 발현률 차이 확인.

### 2.4 "리뷰형 step 검색 컨텍스트 우선" 정책 설계 (CONTEXT.md 후보)

**정의**: Step 2(비교/응용형) 및 Step 3(실전/확정형) 같이 **검증 가능한 사실·비교·구매 가이드**가 핵심인 단계에서 `use_context=True`를 **필수화(강제)**하고, Step 1(기초/정보형)은 선택적 허용.

**적용 대상 step_role** (`chain_config.yaml:65-82`):
| chain_type | Step 1 | Step 2 | Step 3 |
|------------|--------|--------|--------|
| depth | 기초/정보형 | **분석/응용형** | **전문/심화형** |
| swallow | 구매/소비형 | **절약/관리형** | **금융/투자형** |
| lateral | 주제/정보형 | **비교/탐색형** | **비즈니스/확정형** |

**정책 규칙**:
1. **Step 2, 3**: `use_context=True` 강제 (CLI `--no-search`로도 오버라이드 불가)
2. **Step 1**: `use_context=True` 기본, `--no-search`로 해제 가능
3. 검색 실패 시: `retrieve_context_for_post`가 `(False, err)` 반환 → 로그만 남기고 컨텍스트 없이 진행 (기존 동작 유지)
4. 카테고리별 angle 매핑(`angle_map`) 유지: "비교/절약/금융/전문" → `expert` 엔드포인트(news, webkr, cafearticle) 사용으로 공신력 확보

**구현 위치**: `chain_drafter.py:236` `draft_single_post` 시그니처 변경:
```python
def draft_single_post(
    post: dict,
    posts: list[dict],
    seed_keyword: str,
    use_context: bool = True,
    force_context: bool = False,  # NEW: step 2/3에서 강제 적용
) -> tuple[str, dict, str]:
```

**검증 계획**:
- 실제 모델로 Step 2/3 각 5회 생성 → 8종 시그니처 발현률 측정
- `use_context=True` vs `False` 비교 (Phase 34 T6 재현 테스트 확장)

---

## 3. 카테고리 불일치 (뉴발란스 740 → etc vs 쇼핑/소비)

### 3.1 현상 확인

```python
from mc_paths import classify_keyword
print(classify_keyword('뉴발란스 740'))  # 출력: etc
print(classify_keyword('뉴발란스'))       # 출력: etc
print(classify_keyword('스니커즈'))       # 출력: shopping_brand
print(classify_keyword('골프웨어'))       # 출력: shopping_brand
```

**DB 저장값** (Chain #405 derive 단계):
```json
{
  "step": 1,
  "category_guess": "쇼핑/소비",  // derive_user_lateral_etc 프롬프트의 category_guess
  "target_keyword": "뉴발란스 740"
}
```

### 3.2 원인 분석

**분류 파이프라인** (`mc_paths.py:98-137`):
```python
def classify_keyword(keyword: str) -> str:
    kw = keyword.lower()
    if kw.endswith("주가"): return "stock"
    prompts = load_prompts()
    categories = prompts.get("keyword_categories", {})
    cat_names = [c for c in categories.keys() if c != "etc"]
    cat_names.sort(key=lambda c: categories.get(c, {}).get("priority", 100))
    for cat_name in cat_names:
        patterns = categories.get(cat_name, {}).get("patterns", [])
        for pat in patterns:
            if re.search(pat, kw) or re.search(pat, keyword):
                return cat_name
    return _postprocess_stock_priority(kw, "etc")
```

**prompts.yaml `shopping_brand` 패턴** (lines 373-375):
```yaml
shopping_brand:
  patterns:
    - (쇼핑몰|브랜드|골프웨어|레깅스|원피스|블라우스|반팔|셔츠|가방|목걸이|팔찌|반지|시계|선글라스|운동복|의류|패션|스니커즈|샌들|슬리퍼)
```

**문제**: "뉴발란스", "나이키", "아디다스" 등 **브랜드 고유명사**가 패턴에 없음. "스니커즈"라는 일반 명사는 매칭되나 브랜드명은 매칭 안 됨.

**product 카테고리** (lines 476-495)는 갤럭시/아이폰/에어팟 등 **테크 제품** 위주. 신발/의류 브랜드는 커버 안 함.

**derive 단계에서 `category_guess` 결정** (`chain_deriver.py:128`):
```python
category_guess=post.get("category_guess", ""),
```
AI가 프롬프트의 `category_guess` 예시(예: `derive_user_lateral_etc`의 `"쇼핑/소비"`)를 따라 작성 → DB에 저장.

### 3.3 불일치 발생 지점

| 단계 | 분류값 | 비고 |
|------|--------|------|
| **derive** (`chain_deriver.py:51`) | `classify_keyword()` → `etc` | chain_type 결정용 (`keyword_mapping["etc"]="depth"`) |
| **derive** (AI 출력) | AI가 `category_guess: "쇼핑/소비"` 작성 | 프롬프트 예시 따름 |
| **draft** (`chain_drafter.py:258`) | `classify_keyword()` → `etc` | `kw_category`로 H2 가이드라인 선택용 |
| **publish** | DB의 `category_guess` ("쇼핑/소비") 사용 | CTA 템플릿 선택 등 |

**결과**: derive/draft는 `etc` 분류로 동작하나, AI가 작성한 `category_guess`는 "쇼핑/소비"로 저장 → 하류 단계(CTA 선택, 카드 주입 등)에서 혼란.

### 3.4 해결 방안

**방안 A: `shopping_brand` 패턴에 주요 브랜드 추가** (권장)
```yaml
shopping_brand:
  patterns:
    - (쇼핑몰|브랜드|골프웨어|레깅스|원피스|블라우스|반팔|셔츠|가방|목걸이|팔찌|반지|시계|선글라스|운동복|의류|패션|스니커즈|샌들|슬리퍼)
    - (뉴발란스|나이키|아디다스|푸마|리복|아식스|스케쳐스|크록스|호카|온러닝|살로몬|언더아머)
    - (U740|U530|U990|530|990|740|1906|2002|327|574|990v6|990v5|990v4|990v3|990v2|990v1)
```

**방안 B: `classify_keyword`에 브랜드 사전 매칭 로직 추가**
```python
BRAND_KEYWORDS = {
    "뉴발란스", "나이키", "아디다스", "푸마", "리복", "아식스", "스케쳐스",
    "크록스", "호카", "온러닝", "살로몬", "언더아머", "컨버스", "반스",
    "닥터마틴", "팀버랜드", "클락스", "유니클로", "자라", "H&M", "무신사"
}
if any(b in keyword for b in BRAND_KEYWORDS):
    return "shopping_brand"
```

**방안 C: `etc`일 때 AI의 `category_guess`를 우선 신뢰하도록 `draft` 단계 수정**
```python
kw_category = classify_keyword(seed_keyword)
if kw_category == "etc" and post.get("category_guess"):
    # AI가 작성한 category_guess를 카테고리로 사용 (H2 가이드라인 선택용)
    ai_cat = post["category_guess"]
    if ai_cat in kc:  # prompts.yaml에 해당 카테고리 설정 있으면 사용
        kw_category = ai_cat
```

**권장**: 방안 A + 방안 C 병행. 패턴에 브랜드 추가로 근본 해결 + `etc` fallback 시 AI 작성값 존중으로 안전망 확보.

---

## 4. 중간 CTA 카드 구현

### 4.1 Phase 17 CTA 시나리오 설계 요약 (`config/cta_templates.yaml`)

**CTA 템플릿** (lines 5-22):
```yaml
cta_templates:
  chain_card:        # 내부이동: 다음 step 포스트 URL
    text: "더 알아보기 →"
    style: "red-bg"
  hub_cta:           # Step 3 하단: rotcha hub 유입
    text: "전체 글 모아보기 →"
    style: "red-bg"
    placeholder: "{{ENTRY_LINK}}"
  dual_info:         # 정보성 중간 카드
    text: "이 시리즈 보기 →"
    style: "red-bg"
```

**플레이스홀더** (lines 61-62):
```yaml
placeholder_pattern: r'\{\{(?!<|%)([^}]+)\}\}'
```

**AI CTA 감지 패턴** (lines 36-60): "더 알아보기", "계속 읽기", "아래 버튼", "링크를 클릭", "지금 구매", "한정 수량" 등 26개 패턴.

### 4.2 현재 구현 상태 (`chain_card_injector.py`)

**카드 주입 규칙** (lines 3-13):
- 3단계 카드 체계: Depth 0→1, 1→2 `chain-card`, Depth 2 외부 링크 카드
- 하단 Next 카드: 모든 글 기본 삽입 (마지막 H2 이후)
- 중간 관련 카드: H2 ≥ 3일 때 2번째 H2 직후 1개 삽입
- 상단: 카드 금지 (광고 전용 영역)
- CTA 문구: `chain_config.yaml`의 `blog별 card_cta` 블록에서 읽기

**CTA 조회** (lines 293-332): `mc.cta.get_cta()` 위임. `category`, `depth`, `next_url`, `hub_url` 기반으로 HTML/shortcode 생성.

**중복 주입 방지 (D9 게이트)** (lines 477-529): 기존 `chain-card`, `chain-official-card`, `dual-cta` shortcode 및 외부 링크 카드 raw HTML 제거 후 재주입.

### 4.3 중간 CTA 카드 구현 설계

**목적**: Step 1, 2 본문 중간에 **정보성 CTA 카드**(`dual_info` 타입) 삽입 → 독자 체류 유도 + 시리즈 인지 강화.

**삽입 위치**:
1. **Step 1 (Depth 0)**: H2 ≥ 3일 때 2번째 H2 직후 → "이 시리즈 보기 →" (hub URL 연결)
2. **Step 2 (Depth 1)**: H2 ≥ 3일 때 2번째 H2 직후 → "이 시리즈 보기 →" (hub URL 연결) 또는 "다음 단계 보기 →" (Step 3 URL 연결)
3. **Step 3 (Depth 2)**: 중간 카드 불필요 (이미 외부 링크 카드 + hub CTA 존재)

**구현 방안**: `CardInjector.inject_cards_into_draft()` 확장

```python
# line 561-573 수정: 중간 카드 로직 개선
# 중간 카드: H2>=3일 때 2번째 H2 직후 1개 (하단 카드와 별개, 총 2개 구조)
if len(h2_positions) >= 3:
    if is_last:  # Step 3
        mid_links = self.find_external_links(...)
        mid_card = self.build_external_link_card(mid_links, seed_keyword)
    else:  # Step 1, 2
        # NEW: dual_info 타입 CTA 사용 (hub URL 연결)
        hub_url = self._get_hub_url(post["chain_id"])
        mid_cta = get_cta(category=category, depth=depth, hub_url=hub_url)["html"]
        mid_card = self.build_card_html("이 시리즈 전체 보기", hub_url, "이 시리즈 보기 →")
    if mid_card:
        body = self.inject_mid_card(body, mid_card)
```

**필요한 변경 사항**:

1. **`mc/cta.py`**: `get_cta()`에 `dual_info` 타입 반환 로직 이미 존재 (line 76-79). `hub_url` 필수 파라미터로 전달.

2. **`chain_card_injector.py`**: 
   - `inject_cards_into_draft()`에 `hub_url` 파라미터 추가
   - Step 1, 2 중간 카드 생성 시 `dual_info` CTA 사용
   - `CardInjector._get_hub_url(chain_id)` 헬퍼 메서드 추가 (기존 `find_external_links` 참고)

3. **`config/cta_templates.yaml`**: `dual_info`의 `placeholder: "{{HUB_LINK}}"` 추가로 hub URL 플레이스홀더 통일.

4. **`chain_publisher.py`**: `publish_chain()`에서 카드 주입 호출 시 `hub_url` 전달.

**플레이스홀더 치환**: 발행 시점(`chain_publisher_core.py`)에서 `{{HUB_LINK}}` → 실제 hub URL 치환 (기존 `{{ENTRY_LINK}}` 처리와 동일).

### 4.4 통합 테스트 시나리오

| 시나리오 | 기대 결과 |
|----------|-----------|
| Step 1, H2=4개 | 하단: chain-card(Step 2 URL), 중간: dual_info(hub URL) — 총 2개 카드 |
| Step 2, H2=4개 | 하단: chain-card(Step 3 URL), 중간: dual_info(hub URL) — 총 2개 카드 |
| Step 3, H2=4개 | 하단: external-link-card + hub_cta, 중간: 없음 (또는 external-link-card) |
| Step 1, H2=2개 | 하단: chain-card만, 중간: 없음 (H2 < 3) |
| 플레이스홀더 잔존 검증 | 발행 후 `{{HUB_LINK}}`, `{{ENTRY_LINK}}` 0건 |

---

## 코드 참조 요약

| 기능 | 파일 | 라인 |
|------|------|------|
| `classify_keyword()` | `mc_paths.py` | 98-137 |
| `resolve_chain_type()` | `mc_paths.py` | 140-152 |
| `draft_single_post()` | `chain_drafter.py` | 232-357 |
| 검색 컨텍스트 주입 | `chain_drafter.py` | 296-324 |
| `retrieve_context_for_post()` | `search_retriever.py` | 117-196 |
| `strip_leaks()` | `mc/leak_defense.py` | 74-127 |
| 문단 단위 reasoning leak | `mc/leak_defense.py` | 181-314 |
| `inject_cards_into_draft()` | `chain_card_injector.py` | 452-578 |
| `get_cta()` | `mc/cta.py` | 36-96 |
| `detect_ai_cta()` | `mc/cta.py` | 130-158 |
| `keyword_categories` 패턴 | `config/prompts.yaml` | 159-561 |
| `keyword_mapping` | `config/chain_config.yaml` | 83-94 |
| CTA 템플릿 | `config/cta_templates.yaml` | 1-62 |

---

## 위험 요소 및 의존성

| 위험 | 영향도 | 완화 방안 |
|------|--------|-----------|
| use_context=True 강제 시 Naver API 쿼터 초과 | 중 | 일일 25,000 쿼터 모니터링, 실패 시 graceful degradation |
| 카테고리 패턴 추가로 오분류 발생 | 낮 | 우선순위(priority) 조정으로 강한 신호 우선, 테스트 케이스 추가 |
| 중간 CTA 카드 과다 삽입으로 광고 밀도 위반 | 중 | H2 ≥ 3 조건 유지, Step 3 중간 카드 미삽입 |
| Phase 33/34 미완료 상태에서 Phase 35 진행 | 높 | Phase 33, 34 Wave 1 완료 후 Phase 35 착수 |
| Hub URL 생성 로직 부재 | 중 | `chain_card_injector.py`에 `_get_hub_url()` 신규 구현 필요 |

---

## 권장 사항 (우선순위 순)

1. **[P0] Phase 33, 34 완료 후 재검증**: Chain #378, #405 실발행 재검증으로 기준선 확정
2. **[P1] use_context=True 실측 검증**: Phase 34 T6 재현 테스트를 실제 모델로 실행, Step 2/3에서 컨텍스트 유무별 발현률 비교 → "리뷰형 step 검색 컨텍스트 우선" 정책 확정
3. **[P1] 카테고리 불일치 해결**: `prompts.yaml` `shopping_brand` 패턴에 주요 브랜드명/모델코드 추가 + `chain_drafter.py` `etc` fallback 시 AI `category_guess` 존중 로직 추가
4. **[P2] 중간 CTA 카드 구현**: `chain_card_injector.py` 중간 카드 로직에 `dual_info` 타입 통합, hub URL 생성 헬퍼 추가, 플레이스홀더 `{{HUB_LINK}}` 치환 파이프라인 연결
5. **[P3] 통합 테스트 확장**: `test_t5_t6_regression.py`에 `use_context=True` 실측 테스트, 카테고리 분류 테스트, 중간 CTA 카드 삽입 검증 테스트 추가

---

## 잔존 위험

- **Phase 33/34 미완료**: Phase 33 PLAN과 Phase 34 PLAN 모두 "승인 대기 중" 상태. 이 두 Phase가 완료되지 않으면 Phase 35의 실발행 재검증과 use_context 효과 실측이 불가능함.
- **Naver API 의존성**: `use_context=True` 강제 정책 시 API 쿼터/장애 리스크. `retrieve_context_for_post`가 이미 실패 시 graceful하게 처리하나, 강제 정책이면 재시도/대기 로직 필요.
- **Hub 페이지 미구현 시 중간 CTA 무의미**: `rotcha.kr/hub/{slug}` 페이지가 실제 존재하고 체인 포스트들을 모아 보여줘야 중간 CTA("이 시리즈 보기")가 의미 있음. Phase 6 허브 페이지 구현 상태 확인 필요.