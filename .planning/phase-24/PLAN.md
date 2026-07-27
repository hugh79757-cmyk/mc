# PLAN.md — Phase 24: 콘텐츠 차별화 + 운영 실증

**Phase:** 24  
**Created:** 2026-07-26  
**Status:** Draft  
**Mode:** execute

---

## Overview

| Task | 내용 | 예상 파일 변경 |
|------|------|----------------|
| **Task 1** | Persona 어조 설계 + 적용 | `config/personas.yaml` (신규), `chain_drafter.py`, `tests/test_persona.py` (신규) |
| **Task 2** | 카테고리별 검색/품질 개선 | `config/prompts.yaml`, `config/chain_config.yaml`, `chain_drafter.py`, `chain_publisher.py`, `tests/test_category_config.py` (신규) |
| **Task 3** | 운영 실증 — 키워드 10개 자동 발행 | `cli/mc.py` (--validate-10 추가), `.planning/phase-24/RESULTS.md` (생성) |

---

## Task 1: Persona 어조 설계 + 적용

### 1.1 `config/personas.yaml` 신규 생성

site×depth (3×3=9개)별 persona 정의. chain_type(swallow/lateral)은 H2 guidelines로 분기하므로 persona에서는 제외.

```yaml
# config/personas.yaml
# 사이트×Depth별 글쓰기 페르소나 — "어떻게 쓸 것인가" (prompts.yaml은 "무엇을 쓸 것인가")

rotcha:
  step1:  # depth 0 — 기초/정보형
    name: "친절한 안내자"
    role: "정보 전달형 콘텐츠 에디터"
    tone: "쉽고 친근한 설명체. 전문 용어를 쓸 때는 반드시 괄호 안에 쉬운 설명 추가. 독자가 처음 접하는 주제라고 가정."
    sentence_style: "짧은 문장 위주. 한 문단 3-4문장. 문장은 '~입니다/~습니다' 체로 통일."
    forbidden: ["심층 분석", "전문가 관점에서", "기술적으로 말하면", "깊이 있게", "고도화", "내재적"]
    focus: "개념 정의, 기본 정보, 소개, 중요성 설명"
  step2:  # depth 1 — 분석/응용형 (rotcha는 step1만 담당, 참고용)
    name: "실용 가이드"
    role: "실용 정보 전달자"
    tone: "실생활에 바로 쓸 수 있는 팁 중심. 구체적 예시와 단계별 안내."
    sentence_style: "중간 길이 문장. 번호 매기기/불렛 적극 활용."
    forbidden: ["이론적 배경", "학술적", "모델링"]
    focus: "방법, 절차, 실전 팁, 체크리스트"
  step3:  # depth 2 — 전문/심화형 (rotcha는 step1만 담당, 참고용)
    name: "심화 해설가"
    role: "전문 지식 전달자"
    tone: "배경 지식 있는 독자 대상. 수치·사례·원인 분석 포함."
    sentence_style: "복합문 허용. 한 문단 4-6문장. 기술 용어 그대로 사용."
    forbidden: ["쉽게 말하면", "간단히", "누구나", "입문"]
    focus: "원리, 분석, 산업 영향, 미래 전망"

issue_techpawz:
  step1:  # depth 0 — 기초/정보형 (issue.techpawz는 step2 담당, 참고용)
    name: "실전 입문자"
    role: "실전형 입문 가이드"
    tone: "실무 관점에서 기초 개념 설명. '왜 이걸 알아야 하는가' 중심."
    sentence_style: "짧은 문장. 액션 아이템 포함."
    forbidden: ["이론만", "추상적", "개념만"]
    focus: "실무 기초, 적용 전제 조건"
  step2:  # depth 1 — 분석/응용형 (주 담당)
    name: "실무 분석가"
    role: "데이터 기반 실무 분석가"
    tone: "데이터와 근거 중심의 분석체. 주장에는 반드시 이유를 함께 제시. 비교와 대조를 활용."
    sentence_style: "중간 길이 문장. 논리적 연결어(따라서, 반면, 그러나) 활용. 표/리스트 적극 활용."
    forbidden: ["~하세요", "꿀팁", "강추", "무조건", "반드시"]
    focus: "비교 분석, 실전 적용 방법, 장단점, 선택 기준"
  step3:  # depth 2 — 전문/심화형 (issue.techpawz는 step2 담당, 참고용)
    name: "전략 컨설턴트"
    role: "전략적 의사결정 지원"
    tone: "의사결정권자 관점. 리스크/기회 정량화. 대안 제시."
    sentence_style: "논리적 흐름. 결론 선행 후 근거 나열."
    forbidden: ["단순 나열", "설명만"]
    focus: "의사결정 프레임워크, 리스크 관리, 장기 전략"

techpawz:
  step1:  # depth 0 — 기초/정보형 (techpawz는 step3 담당, 참고용)
    name: "기술 개요 작성자"
    role: "기술 개요 전문가"
    tone: "기술 용어 정확하게 사용. 전문 독자 대상. 배경 지식 전제."
    sentence_style: "복합문 허용. 전문 용어 노출."
    forbidden: ["쉽게 풀면", "초보자도", "누구나 이해"]
    focus: "기술 스펙, 아키텍처 개요, 핵심 알고리즘"
  step2:  # depth 1 — 분석/응용형 (techpawz는 step3 담당, 참고용)
    name: "기술 심화 분석가"
    role: "기술 심화 분석가"
    tone: "구현 관점 분석. 트레이드오프 명시. 벤치마크/수치 인용."
    sentence_style: "기술 문서 스타일. 코드/설정 예시 포함 가능."
    forbidden: ["개요만", "표면적"]
    focus: "구현 상세, 성능 분석, 트레이드오프"
  step3:  # depth 2 — 전문/심화형 (주 담당)
    name: "테크 리드 / 아키텍트"
    role: "기술 리더십 관점 전문가"
    tone: "깊이 있는 전문 해설체. 배경 지식이 있는 독자 대상. 구체적 수치와 사례 제시. 산업 트렌드와 미래 전망 연결."
    sentence_style: "복합문 허용. 한 문단 4-6문장. 기술 용어 그대로 사용. 인용/레퍼런스 명시."
    forbidden: ["쉽게 말하면", "간단히", "누구나", "입문용", "개요"]
    focus: "산업 영향, 미래 전망, 아키텍처 진화, 기술 부채, 조직/프로세스 함의"
```

### 1.2 `chain_drafter.py` 수정 — persona 주입

`draft_single_post()` 함수에서 `system_prompt` 조립 시 persona 주입.

```python
# chain_drafter.py — draft_single_post() 내 프롬프트 조립 부분 수정 (line 289-331 부근)

def draft_single_post(...):
    ...
    # ── 프롬프트 조립 ──
    draft_user = prompts["draft_user"]
    user_prompt = draft_user.format(...)
    
    # NEW: persona 로드 및 주입
    persona_map = _load_personas()  # 신규 헬퍼 함수
    blog_key = chain_cfg.get("chain_blogs", {}).get(post["depth"], "?")
    depth_role = get_chain_direction_role(chain_type, post.get("step", 1))
    # depth_role 예: "기초/정보형", "분석/응용형", "전문/심화형"
    # step 번호로 매핑: step 1→기초/정보형, step 2→분석/응용형, step 3→전문/심화형
    step = post.get("step", 1)
    persona_key = f"step{step}"
    
    site_persona = persona_map.get(blog_key, {}).get(persona_key, {})
    if site_persona:
        persona_injection = (
            f"당신은 {site_persona.get('role', '전문 콘텐츠 에디터')}입니다. "
            f"{site_persona.get('tone', '')} "
            f"문장 스타일: {site_persona.get('sentence_style', '')} "
            f"중점 영역: {site_persona.get('focus', '')} "
            f"금지 표현: {', '.join(site_persona.get('forbidden', []))}"
        )
        system_prompt = prompts["draft_system"].replace(
            "[PERSONA_INJECTION]",
            persona_injection
        )
    else:
        system_prompt = prompts["draft_system"]
    
    # Search context injection...
    result = generate(system_prompt, user_prompt, tier="default", temperature=0.85)
    ...
```

`prompts.yaml`의 `draft_system`에 `[PERSONA_INJECTION]` 플레이스홀더 추가 필요.

### 1.3 `prompts.yaml` 수정 — persona 플레이스홀더 추가

`draft_system` 프롬프트 상단에 플레이스홀더 삽입.

```yaml
# prompts.yaml — draft_system 앞부분 수정
draft_system: |
  [PERSONA_INJECTION]

  당신은 IT·기술·라이프스타일 분야를 아우르는 전문 콘텐츠 에디터입니다.
  ...
```

### 1.4 헬퍼 함수 추가 — `_load_personas()`

`chain_drafter.py` 상단에 추가.

```python
# chain_drafter.py — _load_prompts() 아래에 추가

def _load_personas() -> dict:
    with open(PERSONAS_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)
```

`mc_paths.py`에 `PERSONAS_PATH` 추가 필요.

### 1.5 단위 테스트 작성 — `tests/test_persona.py`

```python
# tests/test_persona.py
import pytest
from chain_drafter import _load_personas, draft_single_post
from unittest.mock import patch, MagicMock

class TestPersona:
    def test_load_personas(self):
        personas = _load_personas()
        assert "rotcha" in personas
        assert "issue_techpawz" in personas
        assert "techpawz" in personas
        for site in personas:
            for step in ["step1", "step2", "step3"]:
                assert step in personas[site]
                p = personas[site][step]
                assert "role" in p
                assert "tone" in p
                assert "sentence_style" in p
                assert "forbidden" in p
                assert "focus" in p

    def test_persona_injection_in_system_prompt(self):
        """persona가 system_prompt에 주입되는지 확인"""
        with patch('chain_drafter.generate') as mock_generate:
            mock_generate.return_value = {"content": "---\ntitle: Test\ndraft: true\n---\n\n## Test\n\nBody."}
            
            # Mock DB calls
            with patch('chain_drafter.get_chain_posts') as mock_posts:
                mock_posts.return_value = [{
                    "id": 1, "depth": 0, "step": 1,
                    "title": "Test", "angle": "기초", "category_guess": "etc",
                    "chain_type": "depth", "target_keyword": "test"
                }]
                with patch('chain_drafter.update_post_draft'):
                    from chain_drafter import draft_single_post
                    draft_md, meta = draft_single_post(
                        {"id": 1, "depth": 0, "step": 1, "title": "Test", "angle": "기초", "category_guess": "etc", "chain_type": "depth", "target_keyword": "test"},
                        [{"id": 1, "depth": 0, "step": 1, "title": "Test", "angle": "기초"}],
                        "test"
                    )
                    # persona injection 확인은 generate 호출 인자로 검증
                    call_args = mock_generate.call_args
                    system_prompt = call_args[0][0]
                    assert "친절한 안내자" in system_prompt or "정보 전달형" in system_prompt
                    assert "심층 분석" in system_prompt  # forbidden 포함 확인

    def test_forbidden_words_not_in_draft(self):
        """금지어가 생성된 draft에 없는지 검증 (통합 테스트)"""
        # 실제 AI 호출 필요하므로 별도 integration test로 분리
        pass
```

---

## Task 2: 카테고리별 검색/품질 개선

### 2.1 `config/prompts.yaml` 수정 — travel compare_sources 추가

`keyword_categories.travel`에 `compare_sources` 필드 추가.

```yaml
# prompts.yaml — keyword_categories.travel 섹션 수정
keyword_categories:
  travel:
    patterns: [...]
    compare_sources:  # NEW
      - name: "야놀자"
        type: "domestic_ota"
        coverage: "펜션/호텔/리조트 예약, 리뷰, 가격비교"
      - name: "여기어때"
        type: "domestic_ota"
        coverage: "숙소/액티비티/렌터카, 실시간 예약"
      - name: "호텔스컴바인"
        type: "meta_search"
        coverage: "글로벌 호텔 가격비교, 국내외 숙소"
      - name: "트립닷컴"
        type: "global_ota"
        coverage: "항공+호텔 패키지, 해외 숙소 강세"
    cta_phrases: {...}
    char_count: {...}
    step1_sections: [...]
    step2_sections:
      - '## {keyword} — {compare_sources[0].name}·{compare_sources[1].name} 가격·리뷰 비교'
      - '## {keyword} — 시즌별 이용 꿀팁'
      - '## {keyword} — 실제 이용 후기로 보는 장단점'
      - '## 마무리 — {keyword} 최상의 경험하기'
    step3_sections: [...]
```

### 2.2 `chain_drafter.py` 수정 — travel compare_sources 프롬프트 주입

`draft_single_post()`에서 travel 카테고리일 때 H2 guidelines에 compare_sources 포함.

```python
# chain_drafter.py — H2 가이드라인 조립 부분 수정 (line 268-287 부근)

# ── H2 가이드라인 동적 선택 (keyword_categories 기반) ──
kc = prompts.get("keyword_categories", {})
kw_category = classify_keyword(seed_keyword)
cat_config = kc.get(kw_category) or kc.get("etc")
...
raw_sections = cat_config.get(step_key)
if not raw_sections:
    raise ValueError(...)

# NEW: travel 카테고리 step2일 때 compare_sources 치환
h2_lines = []
for i, tmpl in enumerate(raw_sections, 1):
    if kw_category == "travel" and step_key == "step2_sections" and cat_config.get("compare_sources"):
        compare_names = [s["name"] for s in cat_config["compare_sources"][:2]]
        tmpl = tmpl.replace("{compare_sources[0].name}", compare_names[0] if len(compare_names) > 0 else "비교사이트1")
        tmpl = tmpl.replace("{compare_sources[1].name}", compare_names[1] if len(compare_names) > 1 else "비교사이트2")
    h2_lines.append(f"{i}. {tmpl.replace('{keyword}', seed_keyword)}")
h2_guidelines = "\n".join(h2_lines)
```

### 2.3 `config/chain_config.yaml` 수정 — quality_gates.enforce 추가

```yaml
# chain_config.yaml — 품질 게이트 설정 추가 (기존 설정 하단에)
# === 품질 게이트 설정 (Phase 22/24) ===
quality_gates:
  char_count:
    enforce: false  # Phase 24: false 기본, 검증 런 시 --enforce 플래그로 true 오버라이드
    retry_on_fail: 1  # enforce=true일 때 재시도 횟수
  schema:
    enforce: true
  smoke_test:
    enforce: false
```

### 2.4 `chain_publisher.py` 수정 — enforce 토글 적용

`run_chain()`의 검증 게이트에서 `quality_gates.char_count.enforce` 확인.

```python
# chain_publisher.py — run_chain() 내부 검증 루프 수정 (line 845-875 부근)

# 품질 게이트 설정 로드
chain_cfg = _load_chain_cfg()
quality_gates = chain_cfg.get("quality_gates", {})
char_enforce = quality_gates.get("char_count", {}).get("enforce", False)
char_retry = quality_gates.get("char_count", {}).get("retry_on_fail", 1)

for post in posts:
    draft_md = post.get("draft_md", "")
    meta = post.get("meta")
    ...
    result, message = _validate_draft_schema(draft_md, meta)
    if result:
        # Phase 22: 품질 경고가 있으면 DB에 기록
        if message and message.startswith("quality_warning:"):
            warnings = [message.replace("quality_warning: ", "")]
            db.update_quality_warnings(post.get("id"), warnings)
            # NEW: enforce 모드일 때 실패 처리
            if char_enforce:
                print(f"  [ERROR] Quality gate failed (enforce=true): {message}")
                validation_passed = False
                break
    else:
        print(f"  [ERROR] Post {post.get('step', 'N/A')} schema validation failed: {message}")
        validation_passed = False
        break
```

### 2.5 `chain_drafter.py` 수정 — enforce=true일 때 retry 로직

`_validate_draft_schema()`에서 enforce 모드 시 retry 안내 메시지 반환.

```python
# chain_drafter.py — _validate_draft_schema() 글자수 검증 부분 수정 (line 566-579)

# 5. 글자수 검증 (meta에 char_count가 있는 경우)
if meta and isinstance(meta, dict) and meta.get('char_count'):
    cc = meta['char_count']
    actual = count_body_chars(draft_md)
    if actual < cc.get('min', 0):
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"[QUALITY] 글자수 미달: {actual}자 (최소 {cc['min']}자)")
        # enforce 모드면 retry 필요 신호
        if meta.get('enforce_char_count', False):
            return False, f"quality_enforce_retry: undercount ({actual}/{cc['min']})"
        return True, f"quality_warning: undercount ({actual}/{cc['min']})"
    if actual > cc.get('max', 999999):
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"[QUALITY] 글자수 초과: {actual}자 (최대 {cc['max']}자)")
        if meta.get('enforce_char_count', False):
            return False, f"quality_enforce_retry: overcount ({actual}/{cc['max']})"
        return True, f"quality_warning: overcount ({actual}/{cc['max']})"
```

`draft_chain()`에서 meta에 `enforce_char_count` 플래그 설정.

```python
# chain_drafter.py — draft_chain() 내부 (line 379-380 부근)

for post in posts:
    ...
    # enforce 플래그 meta에 전달
    draft_md, meta = draft_single_post(post, posts, seed_keyword, use_context=use_context)
    meta['enforce_char_count'] = quality_gates.get("char_count", {}).get("enforce", False)
    ...
```

### 2.6 Automotive/Real Estate grounding 설정

`prompts.yaml` `keyword_categories`에 `grounding` 필드 추가.

```yaml
# prompts.yaml — automotive, real_estate에 grounding 추가
keyword_categories:
  automotive:
    patterns: [...]
    grounding: false  # NEW: Naver 검색 비활성화, AI 지식 + 가드로 작성
    cta_phrases: {...}
    char_count: {...}
    step1_sections: [...]
    step2_sections: [...]
    step3_sections: [...]
  
  real_estate:
    patterns: [...]
    grounding: false  # NEW: 실측 후 결정, 일단 false
    cta_phrases: {...}
    char_count: {...}
    step1_sections: [...]
    step2_sections: [...]
    step3_sections: [...]
```

`chain_drafter.py`에서 `use_context` 결정 시 grounding 확인.

```python
# chain_drafter.py — draft_single_post() 검색 컨텍스트 주입 부분 (line 305-329)

# ── Search context injection (Phase 7) ──
if use_context:
    # NEW: 카테고리별 grounding 설정 확인
    cat_config = cat_config or {}
    grounding = cat_config.get("grounding", True)
    if not grounding:
        print(f"  [drafter] ⚠️ {kw_category} 카테고리: grounding 비활성화 (검색 스킵)")
    else:
        try:
            client = NaverSearchClient()
            ...
```

### 2.7 단위 테스트 작성 — `tests/test_category_config.py`

```python
# tests/test_category_config.py
import pytest
import yaml
from mc_paths import PROMPTS_PATH, CHAIN_CONFIG_PATH

class TestCategoryConfig:
    def test_travel_compare_sources_exists(self):
        with open(PROMPTS_PATH, encoding="utf-8") as f:
            prompts = yaml.safe_load(f)
        travel = prompts["keyword_categories"]["travel"]
        assert "compare_sources" in travel
        assert len(travel["compare_sources"]) >= 3
        for src in travel["compare_sources"]:
            assert "name" in src
            assert "type" in src
            assert "coverage" in src

    def test_automotive_grounding_false(self):
        with open(PROMPTS_PATH, encoding="utf-8") as f:
            prompts = yaml.safe_load(f)
        auto = prompts["keyword_categories"]["automotive"]
        assert auto.get("grounding") is False

    def test_real_estate_grounding_false(self):
        with open(PROMPTS_PATH, encoding="utf-8") as f:
            prompts = yaml.safe_load(f)
        re = prompts["keyword_categories"]["real_estate"]
        assert re.get("grounding") is False

    def test_quality_gates_enforce_config(self):
        with open(CHAIN_CONFIG_PATH, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        qg = cfg.get("quality_gates", {})
        assert "char_count" in qg
        assert qg["char_count"].get("enforce") is False  # Phase 24 기본값
        assert "retry_on_fail" in qg["char_count"]

    def test_enforce_toggle_in_publisher(self):
        """chain_publisher가 enforce 설정을 읽는지 확인"""
        from chain_publisher import run_chain
        import chain_publisher as cp
        # 설정 로드 로직 검증
        chain_cfg = cp._load_chain_cfg() if hasattr(cp, '_load_chain_cfg') else None
        # 실제 테스트는 integration test에서
        pass
```

---

## Task 3: 운영 실증 — 키워드 10개 자동 발행

### 3.1 `cli/mc.py` 수정 — `--validate-10` 플래그 추가

```python
# cli/mc.py — main_parser에 플래그 추가 (line 745-780 부근)

main_parser.add_argument("--validate-10", action="store_true",
                        help="실제 키워드 10개로 end-to-end 검증 실행 (품질 게이트 enforce)")

main_parser.add_argument("--enforce", action="store_true",
                        help="품질 게이트 enforce 모드 강제 활성화 (--validate-10과 함께 사용)")
```

### 3.2 검증용 키워드 10개 큐 등록 함수

```python
# cli/mc.py — _run_validate_10() 함수 신규 추가

def _run_validate_10(args, logger: logging.Logger) -> int:
    """실제 키워드 10개로 end-to-end 검증 실행."""
    from mc.queue import add_keyword, get_next_keyword, mark_done, mark_failed
    from chain_publisher import run_chain
    import time
    import json
    from datetime import datetime
    
    # 검증용 키워드 10개 (카테고리별 분산)
    validation_keywords = [
        {"keyword": "제주도카페", "category": "travel", "priority": 2},
        {"keyword": "강릉맛집", "category": "travel", "priority": 2},
        {"keyword": "부산해수욕장", "category": "travel", "priority": 3},
        {"keyword": "삼성갤럭시S26", "category": "tech", "priority": 3},
        {"keyword": "아이폰17프로", "category": "tech", "priority": 3},
        {"keyword": "전기차보조금2026", "category": "automotive", "priority": 3},
        {"keyword": "서울아파트시세", "category": "real_estate", "priority": 4},
        {"keyword": "코딩독학방법", "category": "education", "priority": 3},
        {"keyword": "다이어트식단", "category": "health", "priority": 3},
        {"keyword": "주식초보투자", "category": "finance", "priority": 4},
    ]
    
    # 큐에 등록
    for kw in validation_keywords:
        add_keyword(kw["keyword"], kw["category"], kw["priority"])
    
    logger.info(f"Validation queue populated with {len(validation_keywords)} keywords")
    
    results = []
    enforce = args.enforce or getattr(args, 'validate_10', False)
    
    for i in range(10):
        item = get_next_keyword()
        if not item:
            logger.warning("Queue empty before 10 iterations")
            break
        
        keyword = item["keyword"]
        queue_id = item["id"]
        logger.info(f"[validate-10] [{i+1}/10] Processing: {keyword}")
        
        start = time.time()
        try:
            # enforce 모드면 품질 게이트 활성화
            chain_id = run_chain(
                keyword, 
                publish_mode="auto", 
                use_context=True,
                enforce_quality=enforce  # run_chain에 전달 필요
            )
            elapsed = time.time() - start
            
            if chain_id:
                mark_done(queue_id, chain_id)
                # 품질 경고 수집
                from chain_db import get_chain_posts
                posts = get_chain_posts(chain_id)
                quality_warnings = []
                smoke_results = []
                for p in posts:
                    if p.get("quality_warnings"):
                        quality_warnings.extend(p["quality_warnings"])
                    if p.get("smoke_test_result"):
                        smoke_results.append(p["smoke_test_result"])
                
                results.append({
                    "keyword": keyword,
                    "chain_id": chain_id,
                    "duration_sec": round(elapsed, 1),
                    "success": True,
                    "quality_warnings": quality_warnings,
                    "smoke_test": smoke_results
                })
                logger.info(f"[validate-10] ✅ {keyword} — Chain #{chain_id} ({elapsed:.1f}s)")
            else:
                mark_failed(queue_id, "run_chain returned None")
                results.append({
                    "keyword": keyword,
                    "duration_sec": round(elapsed, 1),
                    "success": False,
                    "error": "run_chain returned None"
                })
                logger.error(f"[validate-10] ❌ {keyword} — run_chain returned None")
                
        except Exception as e:
            elapsed = time.time() - start
            error_msg = f"{type(e).__name__}: {e}"
            mark_failed(queue_id, error_msg)
            results.append({
                "keyword": keyword,
                "duration_sec": round(elapsed, 1),
                "success": False,
                "error": error_msg
            })
            logger.error(f"[validate-10] ❌ {keyword} — {error_msg}")
    
    # 결과 저장
    results_path = Path("/Users/twinssn/projects2/mc/.planning/phase-24/RESULTS.md")
    results_path.parent.mkdir(parents=True, exist_ok=True)
    
    success_count = sum(1 for r in results if r["success"])
    total_count = len(results)
    avg_duration = sum(r["duration_sec"] for r in results) / total_count if total_count else 0
    slowest = max(results, key=lambda r: r["duration_sec"]) if results else None
    
    # 품질 경고 분포
    warning_counts = {}
    for r in results:
        for w in r.get("quality_warnings", []):
            warning_counts[w] = warning_counts.get(w, 0) + 1
    
    with open(results_path, "w", encoding="utf-8") as f:
        f.write(f"# Phase 24 Validation Results\n\n")
        f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Enforce mode:** {enforce}\n\n")
        f.write(f"## Summary\n\n")
        f.write(f"- **Total:** {total_count}\n")
        f.write(f"- **Success:** {success_count} ({success_count/total_count*100:.1f}%)\n")
        f.write(f"- **Failed:** {total_count - success_count}\n")
        f.write(f"- **Avg Duration:** {avg_duration:.1f}s\n")
        if slowest:
            f.write(f"- **Slowest:** {slowest['keyword']} ({slowest['duration_sec']}s)\n\n")
        
        f.write(f"## Quality Warnings Distribution\n\n")
        for w, c in sorted(warning_counts.items(), key=lambda x: -x[1]):
            f.write(f"- {w}: {c}\n")
        f.write(f"\n")
        
        f.write(f"## Per-Keyword Results\n\n")
        for r in results:
            status = "✅" if r["success"] else "❌"
            f.write(f"### {status} {r['keyword']}\n")
            f.write(f"- Chain ID: {r.get('chain_id', 'N/A')}\n")
            f.write(f"- Duration: {r['duration_sec']}s\n")
            if r["success"]:
                f.write(f"- Quality Warnings: {r.get('quality_warnings', [])}\n")
                f.write(f"- Smoke Test: {r.get('smoke_test', [])}\n")
            else:
                f.write(f"- Error: {r.get('error', 'Unknown')}\n")
            f.write(f"\n")
    
    logger.info(f"Validation complete: {success_count}/{total_count} success")
    logger.info(f"Results saved to {results_path}")
    
    # mc status --json 실행해서 추가 기록
    import subprocess
    subprocess.run(["python", "-m", "cli.mc", "status", "--json"], 
                   cwd="/Users/twinssn/projects2/mc")
    
    return 0 if success_count >= 7 else 1  # 70% 성공 기준
```

### 3.3 `chain_publisher.py` 수정 — `enforce_quality` 파라미터 추가

```python
# chain_publisher.py — run_chain() 시그니처에 enforce_quality 추가

def run_chain(
    seed: str,
    dry_run: bool = False,
    draft_only: bool = False,
    image_only: bool = False,
    publish_mode: str = "auto",
    blog_overrides: dict = None,
    theme_override: str = None,
    cf_project_override: str = None,
    use_context: bool = True,
    enforce_quality: bool = False,  # NEW
) -> int:
    ...
    # 검증 게이트에서 enforce_quality 전달
    # _validate_draft_schema 호출 시 meta에 enforce 플래그 설정
```

---

## File Changes Summary

| 파일 | 변경 유형 | Task |
|------|-----------|------|
| `config/personas.yaml` | 신규 생성 | 1 |
| `mc_paths.py` | 수정 (PERSONAS_PATH 추가) | 1 |
| `chain_drafter.py` | 수정 (persona 주입, travel compare_sources, grounding 체크, enforce 플래그) | 1, 2 |
| `prompts.yaml` | 수정 (draft_system 플레이스홀더, travel compare_sources, automotive/real_estate grounding) | 1, 2 |
| `config/chain_config.yaml` | 수정 (quality_gates.enforce) | 2 |
| `chain_publisher.py` | 수정 (enforce 토글 적용, enforce_quality 파라미터) | 2, 3 |
| `cli/mc.py` | 수정 (--validate-10, --enforce 플래그, _run_validate_10) | 3 |
| `tests/test_persona.py` | 신규 생성 | 1 |
| `tests/test_category_config.py` | 신규 생성 | 2 |

---

## Dependencies Between Tasks

- Task 1 독립 수행 가능
- Task 2: `prompts.yaml` 수정이 Task 1의 `draft_system` 플레이스홀더와 충돌하지 않게 순차 수행
- Task 3: Task 1, 2 완료 후 수행 (품질 게이트가 정상 동작해야 검증 의미 있음)
- Task 1, 2는 병렬 가능 (파일 겹침 최소화: personas.yaml vs prompts.yaml/chain_config.yaml)

---

## Verification Plan (VERIFICATION.md에 기록될 내용)

### Task 1 검증:
- [ ] `config/personas.yaml` 로드 + 파싱 테스트 통과
- [ ] `chain_drafter`에서 persona가 system message에 포함되는지 확인
- [ ] 동일 키워드, 다른 step에서 생성된 draft의 어조 차이 확인 (수동 검토)
- [ ] persona forbidden 단어가 해당 step의 draft에 없는지 검증
- [ ] 단위 테스트: persona 로드, 프롬프트 조립, forbidden 필터

### Task 2 검증:
- [ ] `travel.compare_sources` 로드 테스트 통과
- [ ] travel 카테고리 키워드의 프롬프트에 compare_sources 포함 확인
- [ ] automotive/real_estate grounding: false 설정 시 Naver 검색 스킵 확인
- [ ] `quality_gates.char_count.enforce` 설정이 동작하는지 (enforce=true일 때 retry 로직)
- [ ] 단위 테스트: 카테고리 config 조회, enforce retry 로직

### Task 3 검증:
- [ ] 10개 키워드 전체 큐 등록 확인
- [ ] `mc --validate-10` 실행 후 큐 비어있음 확인
- [ ] 성공률 70% 이상 (7/10 이상 성공)
- [ ] `mc status --json`로 전체 현황 정상 출력
- [ ] `RESULTS.md`에 실증 데이터 기록

### 전체:
- [ ] pytest 전체 통과 (286 + Phase 24 신규 테스트)

---

## Rollout Strategy

1. **Task 1 완료** → 단위 테스트 작성 → `pytest tests/test_persona.py -x -q` 통과 확인
2. **Task 2 완료** → 단위 테스트 작성 → `pytest tests/test_category_config.py -x -q` 통과 확인
3. **Task 1+2 통합 테스트** → `mc "테스트키워드" --draft`로 3개 step draft 생성 → persona 차이 수동 확인
4. **Task 3 완료** → `mc --validate-10 --enforce` 실행 → 70% 이상 성공 확인
5. **전체 회귀 테스트** → `pytest -x -q` 전체 통과 확인

---

## Success Criteria

1. **Persona**: rotcha/issue.techpawz/techpawz 각각 Step 1/2/3에서 다른 어조로 생성 확인 (금지어 미포함)
2. **Travel 비교**: Step 2 포스트에 비교 대상 사이트명(야놀자/여기어때/호텔스컴바인) 명시적 언급
3. **Automotive**: Naver 검색 없이도 프롬프트 가드 준수하여 작성 (품질 경고 없음)
4. **품질 게이트**: `quality_gates` 설정 추가, enforce 토글 동작 확인
5. **운영 실증**: 10개 키워드 중 7개 이상 성공 (70% 이상), 평균 소요 시간 기록, RESULTS.md 완성
6. **테스트**: 전체 pytest 통과 (286 + Phase 24 신규)