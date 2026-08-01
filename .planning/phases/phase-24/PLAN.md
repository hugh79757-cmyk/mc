# PLAN.md — Phase 24: YAML Frontmatter Structural Fix (FM 분리)

## Goal

AI 모델이 YAML frontmatter를 직접 생성하지 않도록 구조를 변경하여, FM 누수(FM leak) 버그를 **근본적으로 제거**한다.

## Background

Threads JSON 해결 사례(`response_format=json_object`)와 동일한 원리:
"모델에게 형식을 맡기지 말고, 형식은 코드가 제어한다."

현재 AI는 `---\ntitle:...\ndescription:...\ndraft: false\ntags:[...]\ncategories:[...]\n---` 형식의 FM을 직접 생성하는데, 이로 인해:
- `---` 닫는 위치 혼동
- YAML 필드가 FM 바깥으로 누출
- `_ensure_frontmatter()`의 복잡한 사후 보정 (90라인)

FM은 발행 시 `_publish_hugo()`에서 **완전히 재생성**되므로 (draft→false, slug, date, featureimage, images 추가), AI가 FM을 생성하는 것은 토큰 낭비 + 버그 원인일 뿐이다.

## Changes Summary

| # | 파일 | 변경 | 영향 |
|---|------|------|------|
| 1 | `config/prompts.yaml` | `draft_system`에서 `[Frontmatter — 필수]` + `[Output Checklist]` FM 항목 제거 | AI가 FM을 출력하지 않음 |
| 2 | `chain_drafter.py` | `_build_frontmatter()` 신규 함수: post dict → FM 문자열 | FM을 코드에서 조립 |
| 3 | `chain_drafter.py` | `_ensure_frontmatter()` 단순화: `---` 이미 있는 경우 보존만, 생성 로직은 `_build_frontmatter()`에 위임 | 복잡도 감소 |
| 4 | `chain_drafter.py` | `draft_chain()`에서 `_ensure_frontmatter()` 대신 `_build_frontmatter()` 사용 | FM을 body 앞에 추가 |
| 5 | `chain_drafter.py` | `describe_body()` 신규 함수: AI body 첫 문단 → description 추출 | description 필드 보존 |
| 6 | `test_chain_drafter.py` | `TestEnsureFrontmatter` 케이스 업데이트 | 단순화된 동작 반영 |

## Task Breakdown

### Task 1: Prompt 변경 (`config/prompts.yaml`)

**1a. `draft_system`에서 `[Frontmatter — 필수]` 섹션 (lines 123-149) 제거**

제거할 내용:
```yaml
  [Frontmatter — 필수]

  반드시 아래 구조로 시작:

  ---

  title: "핵심 검색 키워드 포함 100자 이내"

  description: "글 요약 150자 이내, 키워드 2개 이상"

  draft: false

  tags: ["태그1", "태그2", ...] (한 줄 배열, 5~8개)

  categories: ["카테고리1"] (한 줄 배열, 1~2개)

  ---

  - title: 큰따옴표, 앞 30자에 핵심 키워드, 콜론/하이픈/파이프 금지

  - description: 큰따옴표, 한 줄, 150자 이내

  - tags, categories: 반드시 한 줄 배열 형식

  - date, slug 작성 금지 (자동 생성)
```

**1b. `draft_system`에서 `[Output Checklist]`의 FM 관련 항목 제거**

제거할 항목:
```yaml
  - Frontmatter가 ---로 시작하고 ---로 끝나는가?
```

추가할 항목 (대체):
```yaml
  [IMPORTANT — 출력 형식]
  - YAML frontmatter(--- 블록)를 절대 포함하지 마세요.
  - --- 으로 시작하지 마세요. 본문 내용만 출력하세요.
  - 프론트매터는 자동 생성되므로, 본문(content)만 작성하시면 됩니다.
```

### Task 2: `_build_frontmatter()` 함수 추가 (`chain_drafter.py`)

signal: T2-build-fm

```python
def _build_frontmatter(post: dict, body: str) -> str:
    """post dict + body로 완전한 Hugo 마크다운 문자열 조립.
    
    frontmatter를 코드에서 직접 생성하여 AI의 FM 누수 문제를 구조적으로 방지.
    """
    title = (post.get("title") or "").replace('"', '\\"')
    tags = post.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    tags_str = ", ".join(f'"{t}"' for t in (tags or []))
    cats = (post.get("category_guess") or post.get("category") or "일반").replace('"', '\\"')
    
    # description: body 첫 1-2문장에서 추출 (AI가 생성한 description 보존)
    desc = _extract_description(body)
    
    fm = (
        f"---\n"
        f'title: "{title}"\n'
        f'description: "{desc}"\n'
        f"draft: true\n"
        f"tags: [{tags_str}]\n"
        f'categories: ["{cats}"]\n'
        f"featureimage: \"\"\n"
        f"---\n\n"
    )
    return fm + body


def _extract_description(body: str, max_len: int = 150) -> str:
    """body 첫 문단에서 description 추출, 150자 제한."""
    body = body.strip()
    if not body:
        return ""
    # 첫 번째 문단 (빈 줄 또는 H2 전까지)
    para = body.split("\n\n")[0].strip()
    # 첫 1-2 문장 (마침표/물음표/느낌표로 분리)
    sentences = re.split(r'(?<=[.!?])\s+', para)
    desc = sentences[0] if sentences else para
    if len(desc) < 30 and len(sentences) > 1:
        desc = " ".join(sentences[:2])
    # 따옴표 이스케이프
    desc = desc.replace('"', '\\"').replace("'", "\\'")
    # 150자 제한
    if len(desc) > max_len:
        desc = desc[:max_len - 3] + "..."
    return desc
```

**Implementation notes:**
- `featureimage: ""`를 포함하여 `_ensure_featureimage()` 호출을 대체
- `_extract_description()`는 body에서 자연어 description을 추출하여, 기존 AI 생성 description과 동등한 수준 유지
- 150자 초과 시 `_publish_hugo()`에서 추가로 트리밍하지만, 여기서도 1차 제한

### Task 3: `_ensure_frontmatter()` 단순화 (`chain_drafter.py`)

signal: T3-simplify-fm

**변경 전:** 91라인 (FM 생성 + FM 보존 + FM 병합 + closer 보정)

**변경 후:** 20라인 이내 (FM 생성만 — 사후 보정은 제거)

```python
def _ensure_frontmatter(draft_md: str, post: dict) -> str:
    """
    draft_md에 frontmatter가 없으면 title/tags/categories로 생성.
    ---가 있는 경우는 AI가 FM을 생성한 경우 → 그대로 보존 (fallback).
    """
    if not draft_md or not draft_md.strip():
        return draft_md
    
    # 이미 frontmatter가 있으면 (---로 열리고 닫힘) 보존
    if draft_md.strip().startswith("---"):
        end = draft_md.find("---", 3)
        if end != -1 and "title:" in draft_md[3:end]:
            return draft_md  # 정상 FM → 보존
        # FM이 있지만 꺠진 경우 → body로 간주하고 _build_frontmatter로 재생성
        body = draft_md
        if end != -1:
            # ---...--- 블록 제거
            body = draft_md[end + 3:].lstrip("\n")
        return _build_frontmatter(post, body)
    
    # FM 없음 → _build_frontmatter로 생성
    return _build_frontmatter(post, draft_md)
```

**핵심 변경:**
- "닫는 --- 없는 FM" 처리 제거 (`_ensure_frontmatter_closer`가 아직 별도로 존재)
- "더블 FM 병합" 로직 완전 제거 (이제 AI가 FM을 생성하지 않으므로)
- `---` 있는 경우: 정상 FM 보존, 깨진 FM은 `_build_frontmatter()`로 재생성
- `---` 없는 경우: `_build_frontmatter()`로 생성
- `_ensure_frontmatter()`는 순수 안전장치(safety net) 역할만 수행

### Task 4: `draft_chain()`에서 FM 조립 순서 변경 (`chain_drafter.py`)

signal: T4-reorder-fm

**변경 전 (lines 447-456):**
```python
draft_md = _ensure_featureimage(draft_md)
if image_type == "photo":
    draft_md = _insert_body_image_marker(draft_md)
elif image_type == "chart":
    draft_md = _insert_chart_marker(draft_md)
draft_md = _ensure_frontmatter(draft_md, post)
```

**변경 후:**
```python
# Phase 24: FM은 코드에서 직접 조립 (AI가 생성하지 않음)
# body에 marker를 먼저 삽입한 후 FM을 앞에 추가
if image_type == "photo":
    draft_md = _insert_body_image_marker(draft_md)
elif image_type == "chart":
    draft_md = _insert_chart_marker(draft_md)

# FM 조립 (build_frontmatter 내부에 featureimage: "" 포함)
draft_md = _build_frontmatter(post, draft_md)

# 안전장치: AI가 여전히 FM을 출력한 경우 등 예외 처리
draft_md = _ensure_frontmatter(draft_md, post)
```

**변경 사항:**
- `_ensure_featureimage()` 호출 제거 (이제 `_build_frontmatter()` 내부에서 `featureimage: ""` 포함)
- marker 삽입 → `_build_frontmatter()` 순서로 변경 (FM 전에 body 먼저 준비)
- `_ensure_frontmatter()`는 안전장치로 유지 (AI가 지시 무시하고 FM 출력한 경우 대비)

### Task 5: `_extract_body_from_raw()` FM 제거 기능 추가

signal: T5-strip-ai-fm

**Checker 발견:** `_extract_body_from_raw()`가 AI가 출력한 `---` FM 블록을 제거하지 않음. AI가 프롬프트 지시를 무시하고 FM을 출력한 경우, body에 FM이 포함되어 "이중 FM(double FM)" 발생 가능.

**수정:** `_extract_body_from_raw()`에 FM 블록 제거 로직 추가.

```python
def _extract_body_from_raw(raw: str) -> str:
    """raw에서 JSON 코드블록 및 raw JSON을 제거한 깨끗한 본문만 추출"""
    
    # Phase 24: AI가 출력한 FM 블록(---로 열고 닫힘) 제거
    # AI가 프롬프트 지시를 무시하고 FM을 출력한 경우 대비
    _raw_cleaned = raw.lstrip()
    if _raw_cleaned.startswith("---"):
        _end = _raw_cleaned.find("---", 3)
        if _end != -1:
            _raw_cleaned = _raw_cleaned[_end + 3:].lstrip("\n")
        else:
            _raw_cleaned = _raw_cleaned[3:].lstrip("\n")
    raw = _raw_cleaned
    
    # 기존 로그 유지 (아래부터는 기존과 동일)
    cleaned = raw
    ...
```

이 변경으로:
- AI가 지시대로 body만 출력 → FM 없음 → `.lstrip()` 후 `---`으로 시작 안 함 → 통과 (no-op)
- AI가 지시 무시하고 FM 출력 → `_raw_cleaned.startswith("---")` True → FM 블록 제거 → 순수 body만 남음
- JSON metadata (` ```json `) 추출은 FM과 무관하게 계속 동작

**참고:** 이 로직은 `chain_models.py`의 `_extract_body_from_raw()`에 위치하므로 `chain_drafter.py`뿐 아니라 모든 `parse_ai_output()` 호출에 일괄 적용됨.

### Task 6: Test 업데이트 (`test_chain_drafter.py`)

signal: T6-update-tests

**6a. `TestEnsureFrontmatter` 케이스 업데이트**

| 테스트 | 변경 전 기대값 | 변경 후 기대값 |
|--------|--------------|--------------|
| `test_ensure_frontmatter_adds_when_missing` | FM 생성 + body | `_build_frontmatter()`로 FM 생성 + body (내부 동일) |
| `test_ensure_frontmatter_preserves_existing` | 그대로 보존 | 그대로 보존 (변경 없음) |
| `test_ensure_frontmatter_partial_opening_only` | `---`만 있고 closer 없음 → closer 추가 | `---` opener 처리 → `_build_frontmatter()`로 재생성 |
| `test_ensure_frontmatter_empty_draft` | 빈 값 반환 | 빈 값 반환 (변경 없음) |
| `test_ensure_frontmatter_tags_string_not_list` | FM 생성 | `_build_frontmatter()`로 FM 생성 (동일) |
| `test_ensure_frontmatter_tags_empty` | FM 생성 | `_build_frontmatter()`로 FM 생성 (동일) |

**6b. 기존 Mock 업데이트 — `test_draft_chain_creates_three_posts`**

**Checker 발견:** 현재 mock이 FM을 포함한 AI 출력을 반환하여, Phase 24 이후로는 "AI가 지시를 무시한 fallback 경로"만 테스트하게 됨.

수정:
```python
# 변경 전: FM 포함
mock_generate.return_value = {
    "content": """---
title: "Test Post"
...
---
## 서론
...
```json
{"image_type": "photo", ...}
```""",
}

# 변경 후: FM 없이 body만
mock_generate.return_value = {
    "content": """## 서론

본문 내용입니다.

## 본론

더 자세한 내용...

```json
{"image_type": "photo", "image_keyword": "test-keyword"}
```

## 결론

마무리 내용입니다.""",
}
```

단, 기존 테스트가 `"draft_md.startswith('---')"`를 assert하는 경우 → `_build_frontmatter()`가 FM을 앞에 추가하므로 여전히 통과.

**6c. 신규 테스트 추가**

- `test_build_frontmatter_creates_valid_yaml` — `_build_frontmatter()` 출력이 유효한 YAML인지 검증
- `test_build_frontmatter_includes_featureimage` — `featureimage: ""` 포함 확인
- `test_build_frontmatter_extracts_description` — description이 body 첫 문장에서 추출되는지 확인
- `test_ensure_frontmatter_fallback_on_ai_fm` — AI가 FM을 출력했을 때 fallback 처리 확인
- `test_ensure_frontmatter_handles_broken_fm` — 깨진 FM → `_build_frontmatter()`로 재생성 확인
- `test_extract_body_from_raw_strips_ai_fm` — AI가 출력한 FM 블록이 body에서 제거되는지 확인
- `test_extract_description_edge_cases` — 빈 body, H2-only, CJK 문장 처리 확인

### Task 7: 전체 회귀 테스트

- `python -m pytest test_chain_drafter.py test_chain_publisher_core.py test_chain_db.py -v` 전부 통과
- `python -m pytest test_*.py -v` 전부 통과 (362개)

### Task 8: 실제 발행 테스트

1. `python -m cli.mc run "테스트 키워드" --dry-run` → schema validation 통과 확인
2. 생성된 draft 파일 검사: FM이 정상 형식인지 확인
3. `_build_frontmatter()`가 생성한 FM을 `hugo`가 정상 파싱하는지 확인

## Verification Criteria

1. [ ] 모든 pytest 통과 (기존 362개 + 신규 7개 = 369개)
2. [ ] `_ensure_frontmatter()`가 20라인 이내로 단순화되었음 (기존 91라인)
3. [ ] `_build_frontmatter()` 출력 YAML 검증 통과
4. [ ] `_extract_description()`가 body에서 description을 올바르게 추출
5. [ ] `draft_system` 프롬프트에 `[Frontmatter — 필수]` 섹션이 없음
6. [ ] AI가 생성한 draft에 `---` 블록이 포함되어도 `_ensure_frontmatter()`가 안전하게 fallback 처리
7. [ ] `_extract_body_from_raw()`가 AI의 FM 블록을 body에서 제거하는지 확인 (체커 Warning 1 해소)
8. [ ] `test_draft_chain_creates_three_posts` mock이 body-only AI 출력으로 업데이트되었는지 확인 (체커 Warning 2 해소)
9. [ ] 실제 chain draft 생성 시 schema validation 통과
10. [ ] 발행된 글의 FM 정상 (`draft: false`, `slug`, `date`, `featureimage`, `images` 포함)

## File Impact Map

```
config/prompts.yaml
  └─ draft_system: lines 123-149 제거 + lines 152-175 FM 항목 제거 + 새 출력 형식 지시 추가

chain_drafter.py
  ├─ _build_frontmatter(post, body) → str          [신규, ~25라인]
  ├─ _extract_description(body) → str              [신규, ~15라인]
  ├─ _ensure_frontmatter(draft_md, post) → str      [단순화, 91→20라인]
  └─ draft_chain() → list[dict]                     [수정, ~5라인 변경]

test_chain_drafter.py
  ├─ TestEnsureFrontmatter                           [업데이트, 6개 케이스]
  └─ 신규 테스트 클래스                              [추가, 5개 케이스]

chain_models.py                                     [변경 없음, 확인 완료]
chain_publisher_core.py                             [변경 없음, 확인 완료]
```

## Execution Order

```
Task 1 (Prompt 변경)
    │
    ▼
Task 2 (_build_frontmatter + _extract_description 추가)
    │
    ▼
Task 3 (_ensure_frontmatter 단순화)
    │
    ▼
Task 4 (draft_chain FM 조립 순서 변경)
    │
    ▼
Task 5 (parse_ai_output 호환성 확인) ─── 병렬 가능
    │
    ▼
Task 6 (Test 업데이트)
    │
    ▼
Task 7 (전체 회귀 테스트) ─── 반복
    │
    ▼
Task 8 (실제 발행 테스트)
```

## Rollback Plan

변경 전 `chain_drafter.py`와 `config/prompts.yaml`의 전체 내용을 git으로 보존:

```bash
git diff config/prompts.yaml chain_drafter.py
```

실패 시:
```bash
git checkout -- config/prompts.yaml chain_drafter.py
```

## Risk Mitigation

| 리스크 | 확률 | 영향 | 대응 |
|--------|------|------|------|
| AI가 지시 무시하고 FM 계속 출력 | 낮음 | 낮음 | `_extract_body_from_raw()`가 FM 블록 제거 (Task 5) → `_build_frontmatter()`로 정상 FM 생성 |
| `_extract_description()`가 빈 문자열 반환 | 중간 | 낮음 | `_publish_hugo()`에서 빈 description 처리 가능 (기존 동작) |
| `_ensure_frontmatter()` 단순화로 기존 FM 케이스 누락 | 낮음 | 중간 | `test_ensure_frontmatter_preserves_existing` 테스트로 보장 |
| `strip_leaks()`가 FM 없는 body에서 이상 동작 | 낮음 | 중간 | Task 5에서 사전 확인, 필요 시 대응 |
| 기존 테스트 mock이 FM 포함 출력 → 신규 코드 경로 미검증 | 중간 | 낮음 | `test_draft_chain_creates_three_posts` mock 업데이트 (Task 6b) |
| `_extract_description()`의 CJK 문장 분할 오류 | 낮음 | 낮음 | `re.split(r'(?<=[.!?])\s+', ...)`가 한국어에도 적용됨. 한글 문장 부호는 마침표임. |
