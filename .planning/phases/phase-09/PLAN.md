# Phase 9: Publish Quality Fix

**Goal:** 발행 품질 3대 결함(프롬프트 릭, 이미지 미삽입, 썸네일 가독성)을 일괄 수정한다.

**Prerequisite:** Phase 8 complete (chart generation operational).

**Scope (locked):** 기존 코드 수정만. 새 프로바이더/아키텍처 변경 없음.

**Reference:**
- `RESEARCH.md` — 3대 결함 분석 결과 (프롬프트 릭 5경로, 이미지 5경로, 썸네일 7문제)
- `CONTEXT.md` — scope summary and key constraints

---

## Wave 1: 프롬프트 릭 필터 재작성 (2 files)

### Task 9-1: `chain_drafter.py` — `_strip_prompt_leak()` 재작성

**문제:** `skip = True` 플래그가 frontmatter 이후에 False로 전환되어, 본문 중간의 프롬프트 헤더를 제거하지 못함.

**수정:** frontmatter를 먼저 건너뛰고, 그 이후 본문에서 프롬프트 헤더를 모두 제거하도록 로직 변경.

```python
_PROMPT_SECTION_RE = re.compile(
    r"^(?:"
    r"#\s*Role\s*\(역할\)|"
    r"#\s*SEO\s*기본\s*원칙|"
    r"#\s*Frontmatter\s*Rules|"
    r"##\s*title\s*규칙|"
    r"##\s*description\s*규칙|"
    r"##\s*tags\s*규칙|"
    r"##\s*categories\s*규칙|"
    r"#\s*Content\s*Structure|"
    r"##\s*서론|"
    r"##\s*본론|"
    r"##\s*결론|"
    r"#\s*Formatting\s*Rules|"
    r"##\s*절대\s*금지|"
    r"##\s*링크|"
    r"#\s*H2\s*제목\s*SEO\s*규칙|"
    r"#\s*Tone\s*&\s*Manner|"
    r"#\s*Output\s*Checklist|"
    r"#\s*Chain\s*Context|"
    r"#\s*이미지\s*플레이스홀더|"
    r"#\s*이미지\s*유형\s*판단|"
    r"image_type\s*결정\s*기준|"
    r"다음은\s*요청하신|"
    r"아래는\s*.*블로그\s*포스트|"
    r"이전\s*포스트\s*\(|"
    r"다음\s*포스트\s*\("
    r")"
)

def _strip_prompt_leak(text: str) -> str:
    """프롬프트 릭 제거 — frontmatter 이후 본문에서 프롬프트 헤더를 모두 제거."""
    lines = text.splitlines(keepends=True)

    # 1단계: frontmatter 건너뛰기
    start = 0
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                start = i + 1
                break

    # 2단계: frontmatter 이후 본문에서 프롬프트 헤더 제거
    out = lines[:start]
    for ln in lines[start:]:
        stripped = ln.strip()
        if stripped and _PROMPT_SECTION_RE.match(stripped):
            continue
        out.append(ln)
    return "".join(out)
```

### Task 9-2: `chain_drafter.py` — 들여쓰기 수정

**위치:** `chain_drafter.py:257-260`

**문제:** `_strip_prompt_leak()` 호출 이후 코드가 모듈 레벨(들여쓰기 없음)에 있음. `draft_single_post()` 함수 내부에 있어야 함.

**수정:** 4칸 들여쓰기 적용.

```python
    draft_md = _strip_prompt_leak(draft_md)

    char_count = len(draft_md)
    print(f"  [drafter] Step {post.get('step', '?')} 완료 — {char_count:,}자 (model: {result['model']})")

    return draft_md, meta
```

---

## Wave 2: 이미지 치환 순서 수정 (2 files)

### Task 9-3: `chain_publisher_core.py` — `_sanitize_markdown_body()`에서 마커 제거 regex 분리

**문제:** `_sanitize_markdown_body()`가 이미지 마커를 먼저 삭제한 후, `_publish_hugo()`의 치환 코드가 매칭할 대상을 찾지 못함.

**수정:** `_sanitize_markdown_body()`에서 이미지 마커 제거 regex를 제거하고, `_publish_hugo()`의 치환 코드에서 실패한 마커만 제거하도록 변경.

```python
def _sanitize_markdown_body(body: str) -> str:
    """발행 전 마크다운 본문의 흔한 문법 오류를 자동 교정"""
    body = re.sub(
        r'\]\(\[\[(https?://[^\]]+)\]\]\)',
        r'](\1)',
        body
    )
    body = re.sub(r'(?<=\S)\n(#+ )', r'\n\n\1', body)
    body = re.sub(r'(#+ .+)\n(?=\S)', r'\1\n\n', body)
    body = re.sub(r'^-([|].+)$', r'\1', body, flags=re.MULTILINE)
    body = re.sub(r'^([|][-|:\s]+)$', r'\1', body, flags=re.MULTILINE)
    # NOTE: 이미지 마커 제거는 _publish_hugo()의 치환 이후에 수행됨
    return body
```

### Task 9-4: `chain_publisher_core.py` — `_publish_hugo()` 치환 순서 수정

**수정:** 치환 코드 실행 후, 남아있는 미해소 마커를 제거하는 cleanup 단계 추가.

```python
# 4. 본문 이미지 경로 R2 URL로 교체
text = index_md.read_text(encoding="utf-8")
if url_map:
    for local_name, r2_url in url_map.items():
        text = text.replace("/images/" + local_name, r2_url)
        text = text.replace("assets/" + local_name, r2_url)

# 마크다운 본문 정제
text = _sanitize_markdown_body(text)

# 본문 이미지 placeholder 교체
_content_img_url = None
if url_map:
    for _ln, _ru in url_map.items():
        _low = _ln.lower()
        if "thumb" not in _low and _ln.endswith((".jpg", ".jpeg", ".png", ".webp")):
            _content_img_url = _ru
            break
if _content_img_url:
    _alt_prefix = (title or "image")[:30]
    def _img_repl(m):
        _d = m.group(1).strip() if m.lastindex else _alt_prefix
        return f"![{_d}]({_content_img_url})"
    text = re.sub(r"<!--\s*image:\s*(.*?)\s*-->", _img_repl, text)
    text = re.sub(r"<!--todo:image-->", f"![{_alt_prefix}]({_content_img_url})", text)
    text = re.sub(r"<!--todo:chart-->", f"![{_alt_prefix}]({_content_img_url})", text)

# 미해소 마커 cleanup (치환되지 않은 마커 제거)
text = re.sub(r'<!--\s*(thumbnail|image)\s*:\s*.*?-->', '', text)
text = re.sub(r'<!--\s*todo:\s*(image|chart)\s*-->', '', text)

index_md.write_text(text, encoding="utf-8")
```

---

## Wave 3: 썸네일 개선 (1 file)

### Task 9-5: `image/thumbnail.py` — 폰트 크기 및 위치 조정

**수정 항목:**

1. **기본 폰트 크기:** 48px → 64px (이미지 대비 6.25%)
2. **subtitle 크기:** 28px → 36px
3. **`elif` 버그 수정:** `if/elif` → `if/if`로 변경
4. **그라데이션 시작점:** 35% → 45%로 올림
5. **텍스트 위치:** 하단 25% → 하단 35%로 조정

```python
# 폰트 크기
title_font_size = 64
subtitle_font_size = 36

if len(title) > 30:
    title_font_size = 52
if len(title) > 50:    # elif → if (버그 수정)
    title_font_size = 40
```

### Task 9-6: `image/thumbnail.py` — 그림자 → stroke_width 변경

**수정:** `draw.text()`의 shadow offset 대신 `stroke_width` 파라미터 사용.

```python
# 기존 (약한 그림자)
draw.text((x + 2, y + 2), line, font=title_font, fill=(0, 0, 0, 200))
draw.text((x, y), line, font=title_font, fill=(255, 255, 255))

# 변경 (stroke 테두리)
draw.text((x, y), line, font=title_font, fill=(255, 255, 255),
          stroke_width=3, stroke_fill=(0, 0, 0))
```

### Task 9-7: `image/thumbnail.py` — `_fit_text()` CJK 처리 개선

**수정:** 한글+영문 혼합 텍스트에서 영어 단어를 단위로 끊도록 변경.

```python
def _fit_text(draw, text, font, max_width):
    lines = []
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append("")
            continue
        # CJK 문자와 비CJK 문자를 분리하여 처리
        tokens = re.findall(r'[\uac00-\ud7af\u1100-\u11ff\u3130-\u318f]+|[a-zA-Z0-9]+|[^\uac00-\ud7af\u1100-\u11ff\u3130-\u318fa-zA-Z0-9]+', paragraph)
        current_line = ""
        for token in tokens:
            test_line = current_line + token
            bbox = draw.textbbox((0, 0), test_line, font=font)
            w = bbox[2] - bbox[0]
            if w > max_width and current_line:
                lines.append(current_line)
                current_line = token
            else:
                current_line = test_line
        if current_line:
            lines.append(current_line)
    return "\n".join(lines)
```

---

## Wave 4: 프롬프트 마커 지시문 수정 (1 file)

### Task 9-8: `config/prompts.yaml` — 이미지 마커 지시문 수정

**문제:** GPT에게 `<!-- thumbnail: keyword -->`와 `<!-- image: keyword angle -->` HTML 주석을 본문에 삽입하도록 지시하지만, 이 마커를 처리하는 코드가 없음.

**수정:** GPT에게 이미지 플레이스홀더 삽입 지시를 제거. 대신 `_insert_body_image_marker()`와 `_insert_chart_marker()`가 자동으로 삽입하는 `<!--todo:image-->`/`<!--todo:chart-->` 마커만 사용.

```yaml
# 이미지 플레이스홀더 (삭제 — drafter가 자동 삽입)
# 기존:
# 본문에 아래 형식의 이미지 주석을 2곳에 삽입하세요.
# - 썸네일용: <!-- thumbnail: {target_keyword} -->
# - 본문 첫 번째 H2 직후: <!-- image: {target_keyword} {angle} -->
# 변경: 이 섹션 전체 삭제
```

---

## Verification Criteria

| # | Criterion | Check |
|---|-----------|-------|
| V1 | 프롬프트 릭 제거 | 새 체인 생성 시 `## 서론`, `## 본론`, `# Role` 등이 본문에 없음 |
| V2 | 이미지 마커 치환 | `<!--todo:image-->`가 R2 URL로 교체되어 발행 |
| V3 | 미해소 마커 제거 | `<!-- thumbnail: -->`, `<!-- image: -->`가 본문에 없음 |
| V4 | 썸네일 폰트 가독성 | 1024x1024 썸네일에서 제목 텍스트가 선명하게 보임 |
| V5 | `elif` 버그 수정 | 51자+ 제목이 40px 폰트로 렌더링 |
| V6 | 영한 혼합 줄바꿈 | "ChatGPT를 활용한..."이 단어 단위로 끊김 |
| V7 | E2E 발행 | `python chain_publisher.py --seed "테스트" --draft --image --publish` → 3개 사이트 깔끔 발행 |

---

## File Summary

| File | Action | Tasks |
|------|--------|-------|
| `chain_drafter.py` | MODIFY | 9-1, 9-2 |
| `chain_publisher_core.py` | MODIFY | 9-3, 9-4 |
| `image/thumbnail.py` | MODIFY | 9-5, 9-6, 9-7 |
| `config/prompts.yaml` | MODIFY | 9-8 |

**Total:** 4 files, 8 tasks, 4 waves.
