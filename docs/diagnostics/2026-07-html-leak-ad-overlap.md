# HTML 릭 + 광고 겹침 진단 리포트

**작성일:** 2026-07-21
**프로젝트:** mc (Manual Chain) → rotcha-blog, informationhot-hugo, techpawz-hugo
**진단 범위:** 코드 리뷰 기반 근인 분석 (라이브 재현 미수행)

---

## 1. 재현 스텝

```
# 1. 체인 생성
cd /Users/twinssn/Projects2/mc
python chain_publisher.py --seed "테스트키워드" --publish

# 2. 발행된 파일 확인
grep -n '<div style=' /Users/twinssn/Projects/rotcha-blog/content/posts/{slug}/index.md
grep -n '<p style=' /Users/twinssn/Projects/informationhot-hugo/content/posts/{slug}/index.md
grep -n '<a href=' /Users/twinssn/Projects/techpawz-hugo/content/posts/{slug}/index.md

# 3. 광고 겹침 확인 (브라우저)
# rotcha.kr 접속 → 게시글 상단에 광고 2개 겹쳐 보이는지 확인
```

---

## 2. HTML 릭 근인 분류표

### 릭 유형 A: 의도적 HTML 카드 주입 (chain_card_injector.py)

**위치:** `chain_card_injector.py:93-134` (build_official_card_html, build_card_html)
**메커니즘:** GPT 출력이 아닌 Python 코드가 직접 HTML `<div style="...">` 블록을 생성하여 마크다운 본문에 삽입
**영향:** 3개 사이트 전체. 아까 1,086건 일괄 제거한 바로 그 소스

| 파일 | 생성 HTML | 삽입 위치 |
|------|-----------|-----------|
| `build_card_html()` | `<div style="padding:1em;margin:2em 0;border:1px solid #ddd;border-radius:8px;background:#fafafa">` "다음 글" 카드 | 마지막 H2 섹션 이후 |
| `build_official_card_html()` | `<div style="padding:1em;margin:2em 0;border:1px solid #e5e7eb;border-radius:8px;background:#f0fdf4">` "공식 사이트" 카드 | 본문 맨 마지막 |
| `build_dual_cta_html()` | `<div class="max-w-2xl mx-auto my-8 p-6 bg-neutral-50 ...">` 듀얼 CTA 카드 | 본문 마지막 |

**근인 분류:** (a) LLM 응답이 아님 — Python 코드에서 생성하는 의도적 HTML

### 릭 유형 B: _extract_clean_body() 필터링 사각지대

**위치:** `chain_publisher_core.py:111-116`
**근본 원인:** `re.match()`은 라인 **시작**에서만 매칭. 인라인 HTML은 통과

```python
# 현재 코드 (bag)
is_html_tag = bool(re.match(r'<(?:div|span|meta|script|ins|link)', stripped))
# re.match()는 stripped의 시작 위치에서만 매칭
# "일반 텍스트 <div style='...'>..." → stripped가 "일반"으로 시작 → 매칭 실패 → 통과
```

**수정 방향:**
```python
# 수정 (fix)
is_html_tag = bool(re.search(r'<(?:div|span|meta|script|ins|link|a |p )', stripped))
# re.search()는 문자열 내 임의 위치에서 매칭
```

**영향 범위:** GPT가 본문 중간에 `<div>`, `<p style="...">`, `<a href="...">` 등 HTML을 출력하면 그대로 통과

**근인 분류:** (b) 변환 과정에서 이스케이프 누락 — 정제 함수 존재하나 정규식 범위 부족

### 릭 유형 C: 프롬프트 HTML 금지 가드 불완전

**위치:** `config/prompts.yaml:254`
**현재 상태:**
```yaml
- 본문에 "다음 글", "더 알아보기", "더 깊이 알아보기" 등 CTA 버튼/카드 HTML 삽입 금지
  (카드는 별도 시스템에서 자동 주입됨)
```

**문제점:**
- CTA HTML만 금지, **모든 HTML 태그 사용을 금지하지 않음**
- GPT가 `<table>`, `<blockquote>`, `<figure>`, `<a href>` 등을 자유롭게 출력 가능
- `<div style="...">` 패턴은 금지 목록에 없음

**근인 분류:** (d) 프롬프트 규칙 불완전 — HTML 전면 금지 조항 누락

### 릭 유형 D: _verify_before_deploy() 검증 사각지대

**위치:** `chain_publisher_core.py:166-174`
**현재 상태:**
```python
# HTML 주석만 검사
html_comment = re.search(r'<!--.*?-->', content, re.DOTALL)
if html_comment:
    raise DeployValidationError(...)

# HTML 태그 자체는 검사하지 않음 ← gap
```

**근인 분류:** (b) 검증 단계에서 HTML 태그 검사 누락

---

## 3. 3단계 비교표: LLM → Markdown → HTML

| 단계 | 내용 | HTML 존재? |
|------|------|------------|
| **GPT 원문 출력** | `_strip_prompt_leak()` 후 draft_md에 `<div style="...">` 포함 가능 | O — GPT가 `<p>`, `<a>`, `<div>` 등 출력 가능 |
| **_extract_clean_body() 후** | 라인 시작 `<div\|span\|meta\|script\|ins\|link>`만 필터링. 인라인 HTML은 통과 | Δ — 라인 시작 HTML은 제거, 인라인은 잔존 |
| **Hugo 빌드 후** | Hugo는 마크다운 내 HTML을 그대로 통과시킴. 브라우저에 `<div style="...">`로 렌더링 | O — 인라인 HTML이 그대로 노출 |

---

## 4. 광고 겹침 근인 분석

### B-1. 광고 삽입 위치/방식

| 사이트 | 광고 삽입 위치 | 방식 | 파일 |
|--------|---------------|------|------|
| rotcha-blog | 제목 위 (anchor) | `single.html:18` → `adsense/anchor-above-title.html` | Hugo partial 직접 호출 |
| rotcha-blog | 본문 첫 문단 후 | `content-with-ads.html:2` → `adsense/in-article.html` | partial |
| rotcha-blog | 본문 하단 | `single.html:99-106` | inline HTML |
| rotcha-blog | Auto ads | `extend-head.html:1` → `google-adsense-account` meta | AdSense 자동 |
| rotcha-blog | lazy push | `adsense/lazy-load.html` → IntersectionObserver | JS |

**이전 수정 이력:**
- `single.html:18`에서 `anchor-above-title.html` 중복 호출 제거 완료 (이 세션)
- `anchor-above-title.html`에서 인라인 `push({})` 제거 완료 (이 세션)

### B-2. 광고 겹침 재현 조건

- **모바일 (≤768px):** `mobile-sticky-ad` CSS가 `position:fixed; bottom:0; z-index:9998`로 하단 고정
- **데스크톱:** anchor ad가 `position:static` (고정 아님) — 본문 상단에 렌더링
- **겹침 원인:** AdSense Auto ads가 anchor 형식으로 상단에 광고를 자동 생성 + 수동 anchor-ad + lazy push 중복

### B-3. CSS 분석

```css
/* custom.css:51 — 하프페이지 광고 sticky */
.ad-halfpage { position: sticky; top: 100px; min-height: 600px; }

/* custom.css:52 — 모바일 스티키 하단 고정 */
.mobile-sticky-ad { position: fixed; bottom: 0; left: 0; right: 0; z-index: 9998; }

/* custom.css:56 — 중복 광고 숨김 (CSS 방어) */
.adsbygoogle + .adsbygoogle { display: none !important; }
```

**`adsbygoogle + .adsbygoogle` 규칙이 있으나**, 두 광고가 형제(sibling)가 아닌 경우 적용 안 됨. 예를 들어 하나는 `<header>` 안, 다른 하나는 `<section>` 안이면 CSS 방어 실패.

### B-4. 3개 사이트 광고 설정 비교

| 설정 | rotcha-blog | informationhot-hugo | techpawz-hugo |
|------|-------------|---------------------|---------------|
| 테마 | Blowfish | PaperMod | Blowfish |
| adsense partials | 존재 (adsense/ 디렉토리) | 없음 (테마 기본) | 없음 (테마 기본) |
| anchor-ad partial | `adsense/anchor-above-title.html` | 없음 | 없음 |
| custom.css 광고 규칙 | 존재 | 없음 | 없음 |
| Auto ads meta tag | `extend-head.html` | 없음 | 없음 |

**rotcha-blog만** 광고 partial이 존재. informationhot/techpawz는 AdSense Auto ads에 의존.

### B-5. 광고 겹침 패턴

- 겹침은 **rotcha-blog에서만** 발생 — 수동 광고 슬롯 + Auto ads 중복
- informationhot/techpawz는 Auto ads 단일이라 겹침 없음
- 본문 특정 요소(이미지, 코드블록)보다는 **페이지 상단 영역**에서 집중 발생

---

## 5. 두 문제의 교차점 (C 항목)

### C-1. HTML 릭 → 광고 렌더링 영향

**직접적 영향: 없음.** HTML 릭(카드/프롬프트)과 광고 겹침은 독립적 원인.

간접적 영향:
- `chain_card_injector`가 삽입한 `<div style="padding:1em;margin:2em 0">` 카드가 본문 하단에 공간을 차지 → Lazy push 타이밍 변화 → 간헐적 광고 배치 변화 가능
- 그러나 겹침의 주원인은 **rotcha-blog의 anchor-ad 중복 호출** (이미 수정됨)

### C-2. 37건 고아(NULL content_image_path) 영향

**광고 렌더링에 영향 없음.** 이미지 미존재는 광고 위치/레이아웃과 무관.
단, 이미지가 없으면 해당 영역 높이 0 → 본문이 위로 끌어올려져 광고와 간격이 좁아질 수 있음.

---

## 6. 수정 계획서

### Wave 1: _extract_clean_body() 필터링 강화 (위험도: 낮음, 공수: 0.5일)

| Task | 파일 | 수정 내용 | 검증 |
|------|------|-----------|------|
| 11-1 | `chain_publisher_core.py:112` | `re.match()` → `re.search()` + 허용 HTML 확대 (`<p`, `<a`, `<table`, `<blockquote`, `<figure`) | pytest: 인라인 HTML 포함 draft_md → 정제 후 HTML 0건 |
| 11-2 | `chain_publisher_core.py:115` | 필터링된 태그 목록에 `<p`, `<a`, `<table`, `<blockquote`, `<figure`, `<ins`, `<del` 추가 | pytest: 각 태그별 필터링 테스트 |

**회귀 리스크:** `_extract_clean_body()`가 이미지 링크(`![...](https://...)`)와 마크다운 표를 허용하므로, 이들에 대한 오판 필터링 방지 필요. `is_image`/`is_link` 체크가 필터링보다 앞에 오도록 순서 보장.

### Wave 2: 프롬프트 HTML 전면 금지 (위험도: 낮음, 공수: 0.5일)

| Task | 파일 | 수정 내용 | 검증 |
|------|------|-----------|------|
| 12-1 | `config/prompts.yaml:254` | CTA HTML 금지 → **모든 HTML 태그 사용 금지**로 확대 | 새 체인 생성 시 GPT 출력에 HTML 태그 0건 |
| 12-2 | `config/prompts.yaml:248` | 절대 금지 섹션에 `<div>`, `<p style>`, `<a href>` 명시적 추가 | — |

**회귀 리스크:** 없음. GPT 출력 품질에 부정적 영향 없음 (순수 마크다운만 출력하도록 유도).

### Wave 3: chain_card_injector HTML 카드 개선 (위험도: 중간, 공수: 1일)

| Task | 파일 | 수정 내용 | 검증 |
|------|------|-----------|------|
| 13-1 | `chain_card_injector.py` | HTML `<div style="...">` → **Hugo shortcode** 또는 **순수 마크다운**으로 전환 | Hugo 빌드 후 렌더링 확인 |
| 13-2 | `chain_card_injector.py` | 공식 안내 링크 카드도 마크다운 링크 형식으로 전환 | — |

**대안:**
- **방안 A:** 카드 HTML을 Hugo shortcode `{{< card >}}`로 변환 (테마 지원 시)
- **방안 B:** 카드 HTML을 `layouts/shortcodes/card.html`에 정의하고 본문에는 `{{< card title="..." url="..." >}}`만 삽입
- **방안 C:** 카드 주입 자체를 폐기하고 Hugo 템플릿에서 동적으로 렌더링

**회귀 리스크:** `_NON_INTENDED_CHAINS={19,27}` 가드와 무관. 카드 주입 로직 변경은 기존 발행 글에 영향 없음 (재발행 시에만 적용).

### Wave 4: _verify_before_deploy() 검증 강화 (위험도: 낮음, 공수: 0.5일)

| Task | 파일 | 수정 내용 | 검증 |
|------|------|-----------|------|
| 14-1 | `chain_publisher_core.py:166-174` | HTML 태그 검증 추가 (`<div`, `<p style`, `<a href` 패턴) | 의도치 않은 HTML 포함 시 DeployValidationError 발생 |
| 14-2 | `chain_publisher_core.py` | `is_html_tag` 정규식을 `_extract_clean_body()`와 동일 패턴으로 통일 | — |

**회귀 리스크:** 기존 발행된 글의 HTML 카드(`chain_card_injector` 삽입분)가 검증에 걸릴 수 있으므로, 카드 주입이 완료된 후 검증하도록 순서 확인 필요.

### Wave 5: rotcha-blog 광고 중복 방지 강화 (위험도: 낮음, 공수: 0.5일)

| Task | 파일 | 수정 내용 | 검증 |
|------|------|-----------|------|
| 15-1 | `single.html` | anchor-ad 호출 위치 확인 (이미 수정됨 — 추가 확인) | 1개만 호출되는지 grep 확인 |
| 15-2 | `adsense/anchor-above-title.html` | 인라인 push 제거 확인 (이미 수정됨) | — |
| 15-3 | `custom.css` | `adsbygoogle + .adsbygoogle` CSS 방어가 형제 관계 외에도 동작하도록 broadened | 브라우저 검증 |

---

## 7. 요약: 근인 분류표

| 릭 유형 | 분류 | 심각도 | 상태 |
|---------|------|--------|------|
| A. card_injector HTML 카드 | 의도적 주입 | 중간 | 이전 세션에서 1,086건 제거 완료, 코드 미수정 |
| B. _extract_clean_body() 인라인 HTML 사각지대 | 정제 누락 | 높음 | 미수정 |
| C. 프롬프트 HTML 금지 불완전 | 프롬프트 규칙 누락 | 중간 | 미수정 |
| D. _verify_before_deploy() HTML 검증 누락 | 검증 누락 | 낮음 | 미수정 |
| 광고 겹침 | anchor-ad 중복 호출 | 중간 | 이전 세션에서 수정 완료 |

---

## 8. 잔존 위험

1. **_extract_clean_body() 인라인 HTML 사각지대** — GPT가 본문 중간에 HTML 태그를 출력하면 그대로 통과. 다음 체인 생성 시 재현 가능.
2. **chain_card_injector HTML 카드** — 코드가 아직 HTML `<div>`를 생성. 새 체인 발행 시 다시 카드 삽입됨 (이전 세션에서 기존 글만 제거, 코드 미수정).
3. **37건 고아(NULL content_image_path)** — P1(A) 잔여. 이미지 미삽입 시 본문 높이 0 → 간접적 레이아웃 영향 가능.
4. **slug 고유화 미해결** — `_NON_INTENDED_CHAINS` 하드코딩. 신규 비의도 체인 발생 시 수동 갱신 필요.
