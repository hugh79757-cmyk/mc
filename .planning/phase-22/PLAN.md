# PLAN.md — Phase 22: 콘텐츠 품질 제어

**Phase:** 22  
**Created:** 2026-07-26  
**Status:** Draft  
**Mode:** execute

---

## Overview

3개 Task로 구성된 품질 게이트 파이프라인 구축:

| Task | 내용 | 예상 파일 변경 |
|------|------|----------------|
| **Task 1** | 글자수 기준 정립 + 검증 게이트 | `config/prompts.yaml`, `chain_drafter.py`, `chain_publisher.py` |
| **Task 2** | CTA 코드화 | `config/cta_templates.yaml`, `chain_card_injector.py`, `chain_publisher_core.py` |
| **Task 3** | 릭 방어 패턴 통합 + SEO 메타 보강 | `config/leak_defense.yaml`, `mc/leak_defense.py`, `chain_publisher_core.py` |

---

## Task 1: 글자수 기준 정립 + 검증 게이트

### 1.1 `config/prompts.yaml`에 사이트×Depth별 글자수 기준 추가

`keyword_categories` 하위에 `char_count` 필드 추가:

```yaml
keyword_categories:
  travel:
    patterns: [...]
    cta_phrases: {...}
    char_count:
      rotcha:          # Step 1 (기초/정보형)
        min: 1000
        max: 1500
        target: 1250
      issue_techpawz:  # Step 2 (분석/응용형)
        min: 1500
        max: 2500
        target: 2000
      techpawz:        # Step 3 (전문/심화형)
        min: 1500
        max: 2500
        target: 2000
  real_estate:
    char_count:
      rotcha:
        min: 1000
        max: 1500
      issue_techpawz:
        min: 1500
        max: 2500
      techpawz:
        min: 1500
        max: 2500
  # automotive, stock, etc 동일 구조
```

### 1.2 순수 본문 글자수 측정 함수 작성 (`chain_drafter.py` 또는 `mc/quality.py` 신규)

```python
def count_body_chars(draft_md: str) -> int:
    """
    마크다운에서 순수 본문 글자수 계산.
    제외: frontmatter(---...---), 마크다운 문법(#, *, -, |, ```, [], (), > 등),
         이미지 마커(<!--todo:image-->, <!--todo:chart-->, <!-- image:... -->),
         HTML 주석, JSON 메타데이터 블록
    포함: 한글, 영문, 숫자, 공백, 문장부호(본문 내용)
    """
```

- 한글/영문/숫자/공백/문장부호를 모두 1자로 카운트 (UTF-8 기준)
- 마크다운 문법 요소 제거 후 남은 텍스트 길이 측정
- 기존 `_extract_clean_body` 로직 재활용 가능

### 1.3 `_validate_draft_schema()` 확장 (`chain_drafter.py:514-568`)

기존 검증(H2, 이미지 마커, image_keyword, frontmatter 필수 필드) 뒤에 추가:

```python
# 5. 글자수 검증
if meta and meta.get('char_count'):
    cc = meta['char_count']
    actual = count_body_chars(draft_md)
    if actual < cc.get('min', 0):
        logger.warning(f"[QUALITY] 글자수 미달: {actual}자 (최소 {cc['min']}자)")
        return True, f"quality_warning: undercount ({actual}/{cc['min']})"  # 통과하되 경고
    if actual > cc.get('max', 999999):
        logger.warning(f"[QUALITY] 글자수 초과: {actual}자 (최대 {cc['max']}자)")
```

- **기준 미달 시:** `False` 반환하지 않고 `True` 반환 + warning 로그 + `quality_warning` 플래그 메시지 포함
- 파이프라인 차단하지 않음 (Phase 24에서 차단 전환 예정)

### 1.4 `draft_chain()` 호출부에 품질 경고 DB 기록 (`chain_drafter.py:435`)

```python
# draft 저장 시 quality_warning 컬럼 추가 (chain_posts 테이블 마이그레이션 필요)
# 또는 image_meta JSON에 quality_warnings 배열로 저장
```

### 1.5 마이그레이션: `chain_posts` 테이블에 `quality_warnings` 컬럼 추가 (`chain_db.py`)

```sql
ALTER TABLE chain_posts ADD COLUMN quality_warnings TEXT  -- JSON array
```

---

## Task 2: CTA 코드화

### 2.1 `config/cta_templates.yaml` 생성 (Phase 17 설계 기반)

```yaml
# CTA 템플릿 — Phase 17 v2 확정안 반영
# 문구는 전 카테고리 "더 알아보기 →" 통일, 링크 목적지만 분기

cta_templates:
  # chain-card (내부이동): 다음 step 포스트 URL
  chain_card:
    text: "더 알아보기 →"
    style: "red-bg"  # #DC2626 배경 / 흰 글씨
    # 링크는 주입 시점에 next_post_url로 치환

  # hub CTA (Step 3 하단): rotcha hub 유입
  hub_cta:
    text: "전체 글 모아보기 →"
    style: "red-bg"
    placeholder: "{{ENTRY_LINK}}"  # 발행 시 hub URL로 치환

  # dual CTA 정보성 (Step 2 중간 카드 등)
  dual_info:
    text: "이 시리즈 보기 →"
    style: "red-bg"

# 카테고리별 링크 목적지 분기 (문구는 동일, URL만 다름)
# 현재는 모든 카테고리 동일: chain-card → 다음 step, hub → rotcha.kr/hub/{slug}
link_destinations:
  chain_card:
    travel:        {next_step: true}      # 다음 step 포스트 URL
    real_estate:   {next_step: true}
    automotive:    {next_step: true}
    stock:         {next_step: true}
    etc:           {next_step: true}
  hub_cta:
    all: rotcha_hub  # rotcha.kr/hub/{slug}
```

### 2.2 `get_cta(category, depth, next_url, hub_url)` 함수 작성 (`chain_card_injector.py` 또는 `mc/cta.py` 신규)

```python
def get_cta(
    category: str,      # keyword_categories 키 (travel, real_estate 등)
    depth: int,         # 0, 1, 2 (step = depth + 1)
    next_post_url: str = None,   # chain-card용
    hub_url: str = None,         # hub CTA용
) -> dict:
    """
    Returns:
        dict: {
            'html': '...',           # 최종 렌더링될 HTML/shortcode
            'text': '더 알아보기 →',  # 표시 문구
            'style': 'red-bg',
            'url': 'https://...',    # 실제 링크
            'type': 'chain_card' | 'hub' | 'dual_info'
        }
    """
    # depth 0,1 → chain_card (다음 step)
    # depth 2 → hub_cta (hub URL)
    # 중간 카드(H2 3개 이상) → dual_info
```

### 2.3 `chain_card_injector.py` 수정

- `get_cta(blog_key, direction)` → `get_cta(category, depth, next_url, hub_url)` 시그니처 변경 (하위호환: 기존 호출부 래퍼 유지)
- `inject_cards_into_draft()`에서 카테고리/Depth 정보 전달받아 `get_cta` 호출
- `DualCTAInjector` 전환성 CTA(`conv_cta`) 완전 제거 (Phase 17 결정)
- `{{ENTRY_LINK}}` 플레이스홀더 → `hub_url`로 치환 로직 추가

### 2.4 `_sanitize_markdown_body` / D8-GATE에 CTA 필터 추가 (`chain_publisher_core.py`)

```python
# AI가 생성한 임의 CTA 감지 패턴 (CTA-SCENARIO.md §3.3 금지표현 + 일반적 유도문구)
_CTA_LEAK_PATTERNS = [
    r'더\s*(?:깊이\s*)?알아보기', r'계속\s*읽기', r'관련\s*주제',
    r'아래\s*버튼', r'링크를\s*클릭', r'관련\s*글', r'시리즈\s*보기',
    r'이\s*시리즈\s*보기', r'전체\s*글\s*모아보기', r'모아보기',
    r'지금\s*(?:구매|매수|계약|청약|예약)', r'한정\s*수량', r'마감\s*임박',
    r'최저가\s*보장', r'오늘만\s*특가', r'곤두박질', r'오늘\s*계약',
]

def _strip_ai_cta(text: str) -> tuple[str, list]:
    """
    본문에서 AI 생성 CTA 문구 검출 → 제거 → 공식 CTA로 교체 안내
    Returns: (cleaned_text, removed_matches[])
    """
```

- 감지 시 WARNING 로그 + 자동 제거
- 제거 후 해당 위치에 "다음 글로 자연스럽게 연결" 안내 주석 삽입 (선택)

### 2.5 최종 마크다운 CTA 블록 정확히 1개 존재 검증

`_verify_before_deploy()` 또는 별도 `_verify_cta_count()` 추가:

```python
def _verify_cta_count(content: str, slug: str) -> None:
    """
    chain-card / dual-cta shortcode 개수 검증.
    Step 1,2: chain-card 1개 (하단) + 중간 카드(선택) = 1~2개
    Step 3: hub CTA 1개
    그 외 shortcode/HTML CTA 금지
    """
    chain_card_count = len(re.findall(r'chain-card', content))
    dual_cta_count = len(re.findall(r'dual-cta', content))
    html_cta_count = len(re.findall(r'<div[^>]*class="[^"]*cta[^"]*"', content))
    
    # 검증 로직...
```

---

## Task 3: 릭 방어 패턴 통합 + SEO 메타 보강

### 3.1 `config/leak_defense.yaml` 생성 — 모든 blocklist/regex 통합

```yaml
# 통합 릭 방어 설정 — 단일 소스
# 기존: chain_drafter.py, chain_publisher_core.py, audit/audit_chain.py, conftest.py

prompt_leak:
  # chain_drafter.py _PROMPT_LEAK_RE 패턴들
  patterns:
    - "^#\\s*Role:"
    - "^#\\s*SEO\\s*기본\\s*원칙"
    - "^##\\s*서론"
    - "^##\\s*본론"
    - "^##\\s*결론"
    - "이전\\s*포스트\\s*\\("
    - "다음\\s*포스트\\s*\\("
    - "{{.*ENTRY_LINK.*}}"
    - "{{.*FUNNEL_LINK.*}}"
    - "{{.*CPA_LINK.*}}"
    - "\\[citation:\\d+\\]"
    - "참고\\s*자료\\s*:"
    - "출처\\s*:"
  action: "remove_block"  # 헤더부터 다음 헤더까지 블록 제거

cta_leak:
  # chain_publisher_core.py D8-GATE + audit + conftest 통합
  patterns:
    - "더\\s*(?:깊이\\s*)?알아보기"
    - "계속\\s*읽기"
    - "관련\\s*주제"
    - "아래\\s*버튼"
    - "링크를\\s*클릭"
    - "관련\\s*글"
    - "시리즈\\s*보기"
    - "이\\s*시리즈\\s*보기"
    - "전체\\s*글\\s*모아보기"
    - "모아보기"
    - "이어서\\s*(?:실전\\s*)?적용법"
    - "관련\\s*주제\\s*보기"
    - "더\\s*자세히\\s*보기"
    - "더\\s*깊이\\s*알아보기"
  action: "remove_inline"  # 매칭된 문자열만 제거
  forbidden_cta:
    - "지금\\s*(?:구매|매수|계약|청약|예약)"
    - "한정\\s*수량"
    - "마감\\s*임박"
    - "최저가\\s*보장"
    - "오늘만\\s*특가"
    - "곤두박질"
    - "오늘\\s*계약"
    - "아래\\s*버튼"
    - "링크를\\s*클릭"
  action: "warn_only"  # 발견 시 WARNING만

placeholder_leak:
  # {{...}} 패턴 (shortcode {{< >}} 제외)
  pattern: r'\{\{(?!<|%)([^}]+)\}\}'
  action: "remove_inline"

html_tag_leak:
  # 허용되지 않은 HTML 태그
  tags: ["div", "span", "meta", "script", "ins", "link", "p", "a", "table", "blockquote", "figure", "del"]
  action: "remove_block"

json_leak:
  # raw JSON 객체 (image_type, chart_type 포함)
  pattern: r'(?<!`)\n\s*\{\s*"(?:image_type|chart_type|image_keyword)"'
  action: "remove_block"
```

### 3.2 `mc/leak_defense.py` 신규 모듈 생성

```python
"""
통합 릭 방어 모듈 — config/leak_defense.yaml 기반
기존 4개 파일의 개별 leak 방어 호출을 이 모듈로 교체
"""

def strip_leaks(text: str, context: str = "body") -> tuple[str, dict]:
    """
    통합 릭 제거 함수.
    
    Args:
        text: 원본 텍스트
        context: "draft" | "body" | "html" | "test" — 컨텍스트별 규칙 적용
    
    Returns:
        (cleaned_text, report_dict)
        report_dict: {
            "prompt_leak": {"removed": int, "matches": [...]},
            "cta_leak": {"removed": int, "matches": [...]},
            "placeholder_leak": {"removed": int, "matches": [...]},
            "html_leak": {"removed": int, "matches": [...]},
            "json_leak": {"removed": int, "matches": [...]},
        }
    """
    # config/leak_defense.yaml 로드
    # context에 따라 적용할 규칙 필터링
    # 순차 적용: prompt_leak → cta_leak → placeholder_leak → html_leak → json_leak
    # 각 단계별 제거 내역 리포트 누적
```

### 3.3 기존 코드 교체

| 파일 | 기존 함수/코드 | 교체 대상 |
|------|---------------|-----------|
| `chain_drafter.py:352` | `draft_md = _strip_prompt_leak(draft_md)` | `draft_md, _ = strip_leaks(draft_md, "draft")` |
| `chain_publisher_core.py:622-647` | D8-GATE CTA/placeholder 스캐너 | `text, report = strip_leaks(text, "body")` |
| `audit/audit_chain.py:91, 122` | `check_prompt_leak`, `check_cta_leak` | `strip_leaks(content, "test")` 결과 활용 |
| `conftest.py:367, 398` | `assert_no_prompt_leak`, `assert_no_cta_leak` | `strip_leaks(text, "test")` 기반 헬퍼로 재작성 |

### 3.4 SEO 메타 보강 (`chain_publisher_core.py` `_publish_hugo`)

**Frontmatter `description` 150자 강제 제한:**

```python
# _publish_hugo 내부에서 draft_md 파싱 후
desc_match = re.search(r'description:\s*["\']?([^"\']+)["\']?', frontmatter)
if desc_match:
    desc = desc_match.group(1)
    if len(desc) > 150:
        logger.warning(f"[SEO] description 150자 초과 ({len(desc)}자): {slug} — 잘라서 저장")
        desc = desc[:147] + "..."
        # frontmatter 교체
```

**이미지 `alt` 텍스트 자동 추가:**

```python
# 본문 이미지 마크다운에서 alt 비어있으면 채우기
# ![](url) → ![{title[:30]}](url)
def _ensure_image_alt(text: str, title: str) -> str:
    def repl(m):
        alt = m.group(1)
        url = m.group(2)
        if not alt or alt.strip() == "":
            alt = (title or "image")[:30]
        return f"![{alt}]({url})"
    return re.sub(r'!\[([^\]]*)\]\((https?://[^)]+)\)', repl, text)
```

**Frontmatter `images` 필드에 og:image URL 포함 (이미 있으면 확인만):**

```python
# featureimage가 R2 URL이면 images 배열에도 추가
if featureimage and featureimage.startswith("http"):
    # images: [featureimage] 형태로 추가 (Blowfish 테마 호환)
```

---

## File Changes Summary

| 파일 | 변경 유형 | Task |
|------|-----------|------|
| `config/prompts.yaml` | 수정 (char_count 추가) | 1 |
| `chain_drafter.py` | 수정 (count_body_chars, _validate_draft_schema 확장) | 1 |
| `chain_db.py` | 수정 (quality_warnings 컬럼 마이그레이션) | 1 |
| `config/cta_templates.yaml` | 신규 생성 | 2 |
| `mc/cta.py` | 신규 생성 (get_cta 함수) | 2 |
| `chain_card_injector.py` | 수정 (get_cta 시그니처 변경, DualCTAInjector conv 제거) | 2 |
| `chain_publisher_core.py` | 수정 (CTA 필터 추가, SEO 메타 보강, _verify_cta_count) | 2, 3 |
| `config/leak_defense.yaml` | 신규 생성 | 3 |
| `mc/leak_defense.py` | 신규 생성 (strip_leaks) | 3 |
| `chain_drafter.py` | 수정 (_strip_prompt_leak → strip_leaks 교체) | 3 |
| `audit/audit_chain.py` | 수정 (check_prompt_leak/cta_leak → strip_leaks) | 3 |
| `conftest.py` | 수정 (assert 헬퍼 재작성) | 3 |

---

## Dependencies Between Tasks

- Task 1 독립 수행 가능
- Task 2: `chain_card_injector.py` 수정 시 Task 3의 `strip_leaks` 사용 안 함 (별도 CTA 필터)
- Task 3: Task 1, 2와 독립적이나 `chain_publisher_core.py` 공통 수정 영역 있음 → 순차 수행 권장

---

## Rollout Strategy

1. Task 1 완료 → 단위 테스트 작성 → pytest 통과 확인
2. Task 2 완료 → 단위 테스트 작성 → pytest 통과 확인 → 통합 테스트(`mc "테스트" --draft`)
3. Task 3 완료 → 기존 leak 테스트(`test_prompt_leak.py`, `test_chain_drafter.py`) 통과 확인 → 전체 pytest 통과 확인