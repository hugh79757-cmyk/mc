# Phase 9 Research: Publish Quality Fix

**Researched:** 2026-07-20 (3 parallel explore agents)
**Scope:** 프롬프트 릭, 이미지 미삽입, 썸네일 가독성 — 3대 결함 분석

---

## 1. 프롬프트 릭 분석

### 1.1 `_strip_prompt_leak()` — 문서 중간 프롬프트 헤더를 절대 제거하지 못함

**파일:** `chain_drafter.py:288-298`

**근본 원인:** `skip = True` 플래그가 문서 **맨 처음**에서만 활성화. frontmatter(`---`)나 본문 첫 줄이 등장하는 순간 `skip = False`로 전환되고, 이후에 나오는 프롬프트 헤더는 영원히 검사 대상에서 제외됨.

```python
def _strip_prompt_leak(text: str) -> str:
    lines = text.splitlines(keepends=True)
    out = []
    skip = True                           # ← 처음만 True
    for ln in lines:
        stripped = ln.strip()
        if skip and (not stripped or _PROMPT_LEAK_RE.match(stripped)):
            continue
        skip = False                      # ← 첫 비어있지 않은 줄 이후 무조건 False
        out.append(ln)
    return "".join(out)
```

GPT 출력은 항상 `---\ntitle: ...\n---` frontmatter로 시작하므로 `skip`은 즉시 `False`가 됨.

**실제 발행 글에서 확인된 증거 (7건):**

| 사이트 | 파일 | 줄 | 누출 내용 |
|--------|------|----|----------|
| rotcha | `2026-02-03-058-cheonhajeppang.../index.md` | 25 | `## 서론` |
| rotcha | `20260503-072403-코레일-고객센터.../index.md` | 24 | `## 서론` |
| techpawz | `20260503-072702-2026-진에어.../index.md` | 25 | `## 서론` |
| techpawz | `20260503-072838-한화생명.../index.md` | 16, 21 | `## 서론`, `## 본론` |
| techpawz | `20260503-073041-기아오토큐.../index.md` | 23 | `## 본론기아오토큐...` (GPT가 본론+제목을 합침) |

### 1.2 `_PROMPT_LEAK_RE` 패턴 누락

현재 regex가 커버하는 패턴과 실제 GPT 출력에서 관찰되는 패턴의 불일치:

| GPT가 생성 가능한 패턴 | regex 커버 여부 |
|----------------------|----------------|
| `## 서론` (프롬프트에 명시) | O (그러나 로직상 무용) |
| `## 본론` (프롬프트에 명시) | O (그러나 동일) |
| `## 본론기아오토큐...` (GPT가 합침) | X |
| `### 서론`, `### 본론`, `### 결론` | X |
| `## 결론 및 핵심 요약` | X |
| `# 이미지 유형 판단` | O |
| `image_type 결정 기준:` | O (그러나 `:` 없는 변형은 X) |
| GPT의 자기 설명 텍스트 | X |

### 1.3 `draft_user` 템플릿의 지시문이 GPT 출력에 전이

**파일:** `config/prompts.yaml:306-312`

```yaml
본문에 아래 형식의 이미지 주석을 2곳에 삽입하세요.
- 썸네일용: <!-- thumbnail: {target_keyword} -->
- 본문 첫 번째 H2 직후: <!-- image: {target_keyword} {angle} -->
```

이 마커들은 `_strip_prompt_leak()` regex에 포함되지 않음.

### 1.4 `draft_single_post()` 들여쓰기 오류

**파일:** `chain_drafter.py:257-260`

```python
    draft_md = _strip_prompt_leak(draft_md)    # line 255 — 함수 내부 (4칸 들여쓰기)

char_count = len(draft_md)                     # line 257 — 모듈 레벨 (들여쓰기 없음!)
print(f" [drafter] Step {post.get('step', '?')} 완료 — {char_count:,}자 (model: {result['model']})")

return draft_md, meta                          # line 260 — 모듈 레벨!
```

`draft_md`, `post`, `result`, `meta`는 `draft_single_post()`의 지역 변수. 모듈 레벨에서 참조하면 `NameError` 발생.

### 1.5 frontmatter에 중복 `---` 삽입

`_ensure_featureimage()` 또는 `_publish_hugo()`의 frontmatter 재조립 로직에서 `---` 닫힘标记을 본문 시작 부분에 중복 삽입.

---

## 2. 이미지 미삽입 분석

### 2.1 `_sanitize_markdown_body()`가 마커를 먼저 삭제 — 치명적

**파일:** `chain_publisher_core.py`

**실행 순서:**
```
line 342: text = _sanitize_markdown_body(text)     ← 1단계: 마커 삭제!
...
line 356: text = re.sub(r"<!--\s*image:...", ...)   ← 2단계: 이미 삭제된 마커를 찾으려 함
line 357: text = re.sub(r"<!--todo:image-->", ...)  ← 절대 매칭 안 됨
line 358: text = re.sub(r"<!--todo:chart-->", ...)  ← 절대 매칭 안 됨
```

`_sanitize_markdown_body()`의 정규식이 `<!-- image: -->`, `<!--todo:image-->`, `<!--todo:chart-->` 마커를 먼저 제거.

### 2.2 `<!-- thumbnail: keyword -->` 마커는 어디서도 처리되지 않음

| 마커 | GPT가 삽입? | drafter가 삽입? | publisher가 치환? | injector가 치환? |
|------|------------|----------------|-------------------|-----------------|
| `<!-- thumbnail: keyword -->` | 예 | 아니오 | 아니오 (sanitize에서 삭제만) | 아니오 |
| `<!-- image: keyword angle -->` | 예 | 아니오 | `_sanitize`에서 삭제됨 | 아니오 |
| `<!--todo:image-->` | 아니오 | 예 | `_sanitize`에서 삭제됨 | 예 |
| `<!--todo:chart-->` | 아니오 | 예 | `_sanitize`에서 삭제됨 | 예 |

**4종 마커 모두 publisher에서 치환되지 않음.**

### 2.3 content image 부재 시 마커 치환 스킵

`_content_img_url`이 None이면 라인 351의 `if` 블록 진입 불가 → 마커 치환 코드 자체가 스킵됨.

### 2.4 R2 업로드 실패 시 모든 이미지 누락

`url_map`이 비면 thumbnail URL도 없고 content image URL도 없음. 로컬 경로 대신 빈 채로 발행.

### 2.5 `injector.py`가 발행 파이프라인에서 호출되지 않음

`inject_images_into_draft()`가 `_publish_hugo()`에서 호출되지 않음. injector가 처리하는 `<!--todo:image-->`/`<!--todo:chart-->` 치환이 파이프라인에서 누락.

### 2.6 발행된 글에서 미해소 마커 확인 (총 15개 파일, 31개)

- rotcha: 4개 파일, 9개 마커
- informationhot: 5개 파일, 9개 마커
- techpawz: 6개 파일, 13개 마커

---

## 3. 썸네일 가독성 분석

### 3.1 폰트 크기 축소 로직의 `elif` 오류

**파일:** `image/thumbnail.py:283-286`

```python
if len(title) > 30:
    title_font_size = 36
elif len(title) > 50:    # ← 절대 도달 불가
    title_font_size = 28
```

`len > 50`이면 항상 `len > 30`도 참이므로 첫 번째 `if`에서 걸림.

### 3.2 기본 폰트 크기 자체가 너무 작음

1024x1024 이미지에서의 비율:

| 크기 | 이미지 대비 비율 | YouTube 모범 사례 |
|---|---|---|
| 28px | 2.73% | — |
| 36px | 3.52% | — |
| **48px (현재)** | **4.69%** | 하한선(5%) 미달 |
| 64px | 6.25% | 적정 범위 |
| 72px | 7.03% | 적정 범위 |

### 3.3 그라데이션 영역과 텍스트 불일치

그라데이션은 y=358px(35%)에서 시작하지만, 텍스트 시작 위치는 y=764px(75%). 텍스트 상단 부분은 그라데이션이 충분히 진하지 않아서 배경 사진과 충돌.

### 3.4 텍스트 그림자가 너무 약함

shadow offset `(2, 2)`px는 48px 폰트의 4.2%에 불과. Pillow 10.x의 `stroke_width` 파라미터가 더 효과적.

### 3.5 `_fit_text()`의 CJK 처리 — 영한 혼합 시 영어 단어 중간 끊김

`list(paragraph)`로 한 글자씩 분해. 순수 한글에서는 동작하지만, 한글+영문 혼합 제목에서 영어 단어가 중간에서 끊김.

### 3.6 Bold 폰트 누락

`NotoSansKR-Bold.otf` 파일이 존재하지 않음. 제목의 시각적 무게감 부족.

### 3.7 config `bg_alpha` 미사용

`chain_config.yaml`의 `text_overlay.bg_alpha: 0.55`가 설정되어 있지만, `thumbnail.py`는 하드코딩된 `alpha = int(t * 180)` 사용.

---

## 4. 권장 수정 전략

### Wave 1: 프롬프트 릭 필터 재작성
- `_strip_prompt_leak()`를 frontmatter 이후에도 동작하도록 재작성
- `draft_single_post()` 들여쓰기 수정
- `_PROMPT_LEAK_RE` 패턴 확장

### Wave 2: 이미지 치환 순서 수정
- `_sanitize_markdown_body()`의 마커 제거 regex를 `_publish_hugo()`의 치환 코드 **이후**로 이동
- 또는 마커 제거 regex를 `_sanitize_markdown_body()`에서 제거하고, 치환 코드에서 실패한 마커만 제거하도록 변경
- `<!-- thumbnail: keyword -->` 마커 처리 로직 추가

### Wave 3: 썸네일 개선
- 폰트 크기 48px → 64px
- `elif` 버그 수정
- 텍스트 위치 중앙~하단 조정
- 그림자 → stroke_width 변경
- `_fit_text()` CJK 처리 개선
