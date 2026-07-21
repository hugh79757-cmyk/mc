# Phase 11: HTML 릭 + 광고 겹침 수정

**Goal:** 진단 리포트에서 도출된 HTML 릭 4건 + 광고 겹침 1건을 위험도 낮은 순으로 수정하여, 발행되는 체인 글에 의도치 않은 HTML이 노출되지 않고 광고가 본문과 겹치지 않도록 한다.

**Prerequisite:** Phase 10 완료, 진단 리포트(`docs/diagnostics/2026-07-html-leak-ad-overlap.md`) 확정

**Mode:** Sequential — 각 Wave마다 대표 승인 후 다음 Wave로 진행

---

## Architecture

```
Phase 11: HTML 릭 + 광고 겹침 수정
├── Wave 1: _extract_clean_body() 필터링 강화 [위험도: 낮음]
│   ├── 11-1: re.match → re.search 전환
│   └── 11-2: 허용 HTML 태그 목록 확대
│
├── Wave 2: 프롬프트 HTML 전면 금지 [위험도: 낮음]
│   └── 11-3: prompts.yaml 절대 금지 섹션에 HTML 규칙 추가
│
├── Wave 4: _verify_before_deploy() 검증 강화 [위험도: 낮음]
│   ├── 11-4: HTML 태그 검증 로직 추가
│   └── 11-5: 검증 정규식을 _extract_clean_body()와 통일
│
├── Wave 5: 광고 CSS 방어 broadened [위험도: 낮음]
│   ├── 11-6: rotcha-blog CSS 수정
│   └── 11-7: informationhot/techpawz 전파
│
└── Wave 3: card_injector HTML → shortcode 전환 [위험도: 중간, 마지막]
    ├── 11-8: card.html shortcode 생성
    ├── 11-9: DualCTAInjector shortcode 전환
    └── 11-10: 기존 HTML 카드 패턴 정리
```

---

## Wave 1: _extract_clean_body() 필터링 강화

### Goal
`_extract_clean_body()`가 인라인 HTML 태그도 필터링하도록 수정한다.

### Task 11-1: re.match → re.search 전환
- **파일:** `chain_publisher_core.py:112`
- **변경:** `re.match(r'<(?:div|span|meta|script|ins|link)', stripped)` → `re.search(r'<(?:div|span|meta|script|ins|link)', stripped)`
- **검증:** pytest: 라인 중간에 `<div>` 포함된 draft_md → 정제 후 `<div>` 0건
- **주의:** `is_image`/`is_link` 체크가 필터링보다 앞에 오므로, `![...](https://...)`와 `[...](https://...)`는 오판 필터링되지 않음 확인

### Task 11-2: 태그 목록 확대
- **파일:** `chain_publisher_core.py:112`
- **변경:** 태그 목록에 `<p`, `<a `, `<table`, `<blockquote`, `<figure`, `<ins`, `<del` 추가
- **검증:** pytest: 각 태그 유형별 필터링 테스트 (8건)

### 종료 조건
- [ ] pytest 전체 통과 (50/50)
- [ ] 인라인 HTML이 포함된 테스트 케이스 통과
- [ ] `_extract_clean_body()`가 `![image](url)`과 `[link](url)`은 통과시킴 확인

---

## Wave 2: 프롬프트 HTML 전면 금지

### Goal
GPT가 HTML 태그를 출력하지 않도록 프롬프트 규칙을 강화한다.

### Task 11-3: prompts.yaml HTML 규칙 추가
- **파일:** `config/prompts.yaml:248-254`
- **변경:** 절대 금지 섹션에 다음 규칙 추가:
  ```
  - HTML 태그 사용 절대 금지 (<div>, <p style="...">, <a href="...">, <table>, <img> 등 모든 HTML 인라인 삽입 금지)
  - 본문은 순수 마크다운으로만 작성할 것
  ```
- **검증:** 새 체인 생성 시 GPT 출력에 HTML 태그 0건

### 종료 조건
- [ ] prompts.yaml 수정 완료
- [ ] 새 체인 생성 → `_strip_prompt_leak()` 후 draft_md에 `<div>`/`<p`/`<a ` 미존재

---

## Wave 4: _verify_before_deploy() 검증 강화

### Goal
배포 전 검증 단계에서 HTML 태그도 잡아낸다.

### Task 11-4: HTML 태그 검증 추가
- **파일:** `chain_publisher_core.py:166-174`
- **변경:** `html_comment` 체크 뒤에 HTML 태그 체크 추가:
  ```python
  html_tag = re.search(r'<(?:div|span|meta|script|ins|link|p |a |table|blockquote|figure)', content)
  if html_tag:
      raise DeployValidationError(f"index.md에 HTML 태그 잔류: {html_tag.group()[:60]}")
  ```
- **주의:** card_injector가 의도적으로 삽입한 HTML 카드도 이 검증에 걸림 → W3(card_injector 전환) 완료 후에만 이 검증을 활성화하거나, 카드 패턴은 허용 목록에 넣을 것
- **대안:** W3 완료 전까지 HTML 태그 검증은 WARNING으로만 하고 ERROR로 올리지 않음

### Task 11-5: 정규식 통일
- **파일:** `chain_publisher_core.py`
- **변경:** `_extract_clean_body()`와 `_verify_before_deploy()`의 HTML 감지 정규식을 동일한 상수로 추출
- **검증:** 양쪽에서 동일한 HTML 패턴을 감지

### 종료 조건
- [ ] pytest 전체 통과
- [ ] 의도치 않은 HTML 포함 시 DeployValidationError 발생
- [ ] card_injector가 삽입한 HTML은 검증 통과 (W3 전환 전까지 예외)

---

## Wave 5: 광고 CSS 방어 broadened

### Goal
`adsbygoogle + .adsbygoogle` CSS 방어가 형제 관계 외에도 동작하도록 broadened하고, 3개 사이트에 전파한다.

### Task 11-6: rotcha-blog CSS 수정
- **파일:** `/Users/twinssn/Projects/rotcha-blog/assets/css/extended/custom.css:56`
- **변경:**
  ```css
  /* 기존: 형제 관계만 */
  .adsbygoogle + .adsbygoogle { display: none !important; }
  
  /* broadened: 부모 컨테이너 내 중복 감지 */
  .article-content ins.adsbygoogle + ins.adsbygoogle,
  .article-content ins.adsbygoogle + div.adsbygoogle,
  [data-article-body] ins.adsbygoogle + ins.adsbygoogle { display: none !important; }
  ```
- **검증:** 브라우저에서 광고 2개 겹침 없음 확인

### Task 11-7: 3개 사이트 전파
- **파일:** 
  - `/Users/twinssn/Projects/informationhot-hugo/assets/css/extended/custom.css` — 업데이트
  - `/Users/twinssn/Projects/techpawz-hugo/assets/css/extended/custom.css` — **신규 생성** (현재 파일 없음)
- **검증:** 3개 사이트 Hugo 빌드 성공 + 배포

### 종료 조건
- [ ] 3개 사이트 CSS 적용 완료
- [ ] Hugo 빌드 3/3 성공
- [ ] 브라우저 검증: 광고 겹침 0건

---

## Wave 3: card_injector HTML → shortcode 전환 (위험도: 중간)

### Goal
`chain_card_injector.py`가 생성하는 HTML `<div style="...">` 카드를 Hugo shortcode로 전환하여, 마크다운 본문에 raw HTML이 노출되지 않도록 한다.

**이 Wave는 별도 브랜치에서 실행.**

### Task 11-8: card.html shortcode 생성
- **파일:** NEW `rotcha-blog/layouts/shortcodes/chain-card.html` (동일 파일을 3개 사이트에 복사)
- **내용:**
  ```html
  <div style="padding:1em;margin:2em 0;border:1px solid #ddd;border-radius:8px;background:#fafafa;text-align:center;">
    <p style="font-size:0.9em;color:#666;">다음 글</p>
    <p style="font-size:1.1em;font-weight:bold;">{{ .Get "title" }}</p>
    <a href="{{ .Get "url" }}" style="display:inline-block;padding:0.5em 1.5em;background:#333;color:#fff;border-radius:4px;text-decoration:none;">{{ .Get "cta" | default "계속 읽기 →" }}</a>
  </div>
  ```

### Task 11-9: DualCTAInjector shortcode 전환
- **파일:** `chain_card_injector.py`
- **변경:** `build_card_html()`과 `build_official_card_html()`의 반환값을 shortcode 마크다운으로 변경
  ```python
  # 기존:
  return '<div style="padding:1em;...">...'
  # 변경:
  return f'{{{{< chain-card title="{title}" url="{url}" cta="{cta}" >}}}}'
  ```
- **DualCTAInjector:** 동일하게 shortcode 마크다운 반환
- **검증:** `chain_publisher.py --seed "테스트" --publish` E2E → 3개 사이트 발행 후 shortcode가 정상 렌더링

### Task 11-10: 기존 HTML 카드 패턴 정리
- **파일:** `chain_card_injector.py`
- **변경:** `inject_dual_cta_into_draft()`의 기존 단일 CTA 카드 제거 regex를 shortcode 패턴에도 적용
- **검증:** 기존에 HTML 카드가 있었던 위치에 shortcode가 렌더링됨

### 종료 조건
- [ ] pytest 전체 통과
- [ ] 3개 사이트 각 1건 라이브 검증 (shortcode 렌더링 정상)
- [ ] `_verify_before_deploy()` HTML 태그 검증 통과 (shortcode는 Hugo가 HTML로 변환하므로 index.md에는 shortcode만 존재)

---

## Verification Criteria

| # | Criterion | Check Method | Wave |
|---|-----------|-------------|------|
| V1 | 인라인 HTML 필터링 | pytest: 인라인 `<div>` 포함 draft_md → 정제 후 0건 | W1 |
| V2 | 기존 마크다운 통과 | pytest: `![img](url)` / `[link](url)` 정상 보존 | W1 |
| V3 | GPT HTML 출력 0건 | 새 체인 생성 → draft_md에 `<div>`/`<p`/`<a ` 미존재 | W2 |
| V4 | 배포 검증 HTML 감지 | _verify_before_deploy()가 HTML 태그 포함 시 ValidationError | W4 |
| V5 | 광고 겹침 0건 | 브라우저: rotcha.kr 게시글 상단 광고 1개만 노출 | W5 |
| V6 | 3사이트 CSS 적용 | hugo build 3/3 성공 | W5 |
| V7 | shortcode 렌더링 | 3개 사이트 라이브: "다음 글" 카드 정상 렌더링 | W3 |
| V8 | pytest 50/50 | `python -m pytest -v` 전체 통과 | 전체 |

---

## Execution Order

| 순서 | Wave | 머지 전 검증 | 대표 승인 |
|------|------|-------------|-----------|
| 1 | W1 | pytest 50/50 | "W1 완료, 검증 2/2, 머지 요청" |
| 2 | W2 | pytest + 새 체인 생성 | "W2 완료, 검증 1/1, 머지 요청" |
| 3 | W4 | pytest + ValidationError 테스트 | "W4 완료, 검증 1/1, 머지 요청" |
| 4 | W5 | pytest + Hugo 3/3 + 브라우저 | "W5 완료, 검증 3/3, 머지 요청" |
| 5 | W3 | pytest + 라이브 3페이지 | "W3 완료, 검증 3/3, 머지 요청" |

---

## Risks

| 리스크 | 영향 | 완화 |
|--------|------|------|
| W1: re.search가 `![img](url)`을 오판 필터링 | 이미지 노출 실패 | `is_image`/`is_link` 체크를 `is_html_tag`보다 앞에 배치 |
| W4: card_injector HTML이 검증에 걸림 | 기존 발행 파이프라인 차단 | W3 완료 전까지 WARNING 모드로 운영 |
| W3: shortcode 미지원 사이트 | 카드 미렌더링 | PaperMod/informationhot에도 shortcode 디렉토리 생성 |

---

*Created: 2026-07-21 | Phase 11 | 5 Waves, 10 Tasks*
