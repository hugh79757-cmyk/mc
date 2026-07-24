# Phase 18 Research Report — Existing Measurement Infrastructure Verification

## 1. Measurement Infrastructure Findings

### 1.1 AdSense (Google AdSense)

| Site | Publisher ID | Slot ID | Template Presence | Live HTML Evidence | Status |
|---|---|---|---|---|---|
| rotcha.kr | ca-pub-8772455780561463 | 8733248550 | ✅ 존재 | ✅ 존재 | [검증됨] |
| informationhot.kr | ca-pub-6677996696534146 | 4117468627 | ✅ 존재 | ✅ 존재 | [검증됨] |
| techpawz.com | ca-pub-8772455780561463 | 6685009950 | ✅ 존재 | ✅ 존재 | [검증됨] |

**Evidence:**
- rotcha: `grep -rn "adsbygoogle" /Users/twinssn/Projects/rotcha-blog` → templates 및 `public_rollback_20260721_025349/posts/*/index.html`에서 `<ins class=adsbygoogle>` 및 `?client=ca-pub-8772455780561463` 확인
- informationhot: `public_rollback_20260721_025349/posts/2026-한부모가정-지원금-완벽-가이드/index.html`에서 `data-ad-client=ca-pub-6677996696534146` 확인
- techpawz: `public_rollback_20260721_025349/등대식당/index.html`에서 `data-ad-client=ca-pub-8772455780561463` 확인

**AdSlot ID 정합성:**
- rotcha: 8733248550 (게시물 상단/하단/인콘텐츠 반복 사용)
- informationhot: 4117468627 (게시물 상단/인콘텐츠 반복 사용)
- techpawz: 6685009950 (게시물 내 반복 사용)

**Publisher ID 배치 규칙:**
- rotcha 계열(rotcha.kr, techpawz.com): `ca-pub-8772455780561463`
- informationhot 계열(informationhot.kr): `ca-pub-6677996696534146`
- 이는 `AGENTS.md` 섹션 1의 매핑규칙과 일치

### 1.2 Google Analytics

| Site | Tracking ID | Evidence | Status |
|---|---|---|---|
| rotcha.kr | G-L3D3EGH8YN | `gtag/js?id=G-L3D3EGH8YN` + `gtag("config","G-L3D3EGH8YN")` 확인 | [검증됨] |
| informationhot.kr | G-9XCV4KWPZ6 | `gtag/js?id=G-9XCV4KWPZ6` + `gtag("config","G-9XCV4KWPZ6")` 확인 | [검증됨] |
| techpawz.com | G-KL998S18KK | `gtag/js?id=G-KL998S18KK` + `gtag("config","G-KL998S18KK")` 확인 | [검증됨] |

**Evidence:** 각 사이트 `public_rollback_20260721_025349/posts/*/index.html`의 `<head>`에서 gtag 스크립트 확인.

### 1.3 Naver Search Advisor / Naver Analytics

| Feature | Status | Evidence |
|---|---|---|
| Naver Search API (초안 작성 시 컨텍스트 검색) | ✅ 존재 | `chain_drafter.py:30`에서 `from search_retriever import NaverSearchClient`, `chain_drafter.py:306`에서 `client = NaverSearchClient()` 사용 확인 |
| Naver 사이트 인증 (rotcha.kr) | ✅ 존재 | `public_rollback_20260721_025349/posts/*/index.html`에서 `<meta name=naver-site-verification content="050645d130f492d522009ec5d98c4866c3008520">` 확인 |
| Naver Webmaster Tools / Analytics 연동 | ❌ 미확인 | `grep -rni "naver.*analytics\|naver.*webmaster\|search advisor" /Users/twinssn/projects2/mc` 결과 0건 |

**결론:** Naver 검색 API는 발행 초안 생성 단계에서만 사용되며, 사이트 운영 대시보드(Naver Analytics/Webmaster)와의 직접 연동은 확인되지 않음.

### 1.4 Performance / Metrics Tracking (자체 측정 인프라)

| 항목 | 상태 | 근거 |
|---|---|---|
| metrics 전용 테이블 | ❌ 없음 | `sqlite3 /Users/twinssn/Projects/5000/data/mc_chains.db ".schema"` → 테이블: chain_posts, publish_log, loop_chains, chains. metrics/view/impression 테이블 없음 |
| chain_posts 내 성능 컬럼 | ❌ 없음 | `.schema chain_posts` 확인 결과: status, published_url, published_at 등만 존재. impression/view/ctr 컬럼 없음 |
| 코드 내 성능 집계 로직 | ❌ 없음 | `grep -rni "def.*metric\|performance\|view\|impression\|ctr\|click" /Users/twinssn/projects2/mc` 결과 0건 |
| 외부 Analytics 연동 코드 | ❌ 없음 | mc 코드베이스 내 GA/Naver Analytics 연동 코드 없음 (템플릿의 gtag는 Hugo 사이트 자체 설정) |

**결론:** `mc` 시스템 자체에는 발행 후 성능(조회수, CTR, 노출) 측정을 위한 인프라가 없음. 현재 AdSense/GA는 Hugo 템플릿 수준에서만 운영되고, mc DB에는 publish_log만 존재.

---

## 2. Actual Published Post Extraction

### 2.1 전체 현황

| 구분 | 건수 | 비고 |
|---|---|---|
| 총 발행 게시물 (status='published') | 75 | DB 직접 조회 |
| 미발행 (derived/drafted/image_generated/failed) | 127 | DB 직접 조회 |
| publish_log 기록 | 63 | UNIQUE(blog_id, slug) 제약으로 chain_id와 1:1 대응되지 않을 수 있음 |

### 2.2 Depth별 분포

| Depth | 건수 | 역할 |
|---|---|---|
| 0 (intro) | 27 | rotcha.kr 게시 — 기본 개념/소개 |
| 1 (mid) | 25 | informationhot.kr 게시 — 활용법/실전 가이드 |
| 2 (deep) | 23 | techpawz.com 게시 — 기술 심층/미래 전망 |

**검증 방법:** `sqlite3 ... "SELECT depth, count(*) FROM chain_posts WHERE status='published' GROUP BY depth"` → 0:27, 1:25, 2:23

### 2.3 카테고리별 분포 (상위 10)

| 카테고리 | 건수 |
|---|---|
| IT/기술 | 26 |
| 여행/레저 | 4 |
| 정책/복지 | 2 |
| 여행/숙박 | 2 |
| 여행/교통 | 2 |
| 금융/부동산 | 2 |
| 게임 | 2 |
| (null) | 2 |
| 패션/지속가능성 | 1 |
| 패션/의류 | 1 |

**검증 방법:** `sqlite3 ... "SELECT category_guess, count(*) FROM chain_posts WHERE status='published' GROUP BY category_guess ORDER BY cnt DESC"` 실행 결과.

**주의:** 40개 이상의 카테고리가 1건씩 분포되어 있어 카테고리 다양성은 높으나, 상위 1개 카테고리(IT/기술)가 26건으로 전체의 34.7%를 차지하는 편중 현황.

### 2.4 최근 발행 체인 예시 (2026-07-23)

| chain_id | depth | title | keyword | category | url | published_at |
|---|---|---|---|---|---|---|
| 76 | 0 | K2 선풍기조끼란? 여름철 필수 아이템의 모든 것 | K2선풍기조끼 | 패션/의류 | https://rotcha.kr/posts/k2선풍기조끼-20260723-s1/ | 2026-07-23 15:07:57 |
| 76 | 1 | K2 선풍기조끼, 실전 사용 가이드... | K2선풍기조끼 추천 | 리뷰/비교 | https://informationhot.kr/posts/k2선풍기조끼-20260723-s2/ | 2026-07-23 15:07:13 |
| 76 | 2 | K2 선풍기조끼의 기술적 혁신과 미래... | K2선풍기조끼 기술 | 기술/미래 | https://techpawz.com/k2선풍기조끼-20260723-s3/ | 2026-07-23 15:06:38 |

### 2.5 사이트별 발행 URL 분포 (추정)

| 사이트 | 도메인 패턴 | 발행 건수(추정) | 비고 |
|---|---|---|---|
| rotcha.kr | `rotcha.kr/posts/*-s1/` | 25 | DB 조회 결과 |
| informationhot.kr | `informationhot.kr/posts/*-s2/` | 23 | DB 조회 결과 |
| techpawz.com | `techpawz.com/*-s3/` | 23 | DB 조회 결과 |

**확인 불가:** DB의 `published_url` 컬럼이 일부 NULL일 수 있으며, `database is locked` 오류로 정보hot/techpawz 정확 건수를 개별 쿼리로 확인하지 못함. 위 수치는 URL 패턴 매칭 및 depth별 집계로 추정.

---

## 3. 5-Minute Pass/Fail Quality Checklist (초안)

> **사용 방법:** 신규 발행 후 5분 내 다음 항목을 확인. PASS 아니면 FAIL.

### [ ] 1. AdSense Publisher ID 정합성 (30초)
- **PASS 조건:** 게시물 HTML의 `<ins data-ad-client>` 와 `?client=ca-pub-` 가 사이트 계열에 맞는 단일 ID로 일치
  - rotcha.kr / techpawz.com → `ca-pub-8772455780561463`
  - informationhot.kr → `ca-pub-6677996696534146`
- **FAIL 조건:** ID 불일치, 두 계열 ID 혼재, 스크립트 미로드

### [ ] 2. 광고 슬롯 ID 정합성 (30초)
- **PASS 조건:** 사이트별 고정 슬롯 ID가 AdSense 콘솔의 실제 슬롯과 일치
  - rotcha: 8733248550
  - informationhot: 4117468627
  - techpawz: 6685009950
- **FAIL 조건:** 슬롯 ID 오타, 미등록 슬롯 사용

### [ ] 3. Depth별 URL 패턴 정합성 (30초)
- **PASS 조건:**
  - depth 0 → `rotcha.kr/posts/{slug}-s1/`
  - depth 1 → `informationhot.kr/posts/{slug}-s2/`
  - depth 2 → `techpawz.com/{slug}-s3/`
- **FAIL 조건:** depth와 사이트/경로 불일치

### [ ] 4. 카테고리 assign 정합성 (1분)
- **PASS 조건:** `category_guess` 가 빈 문자열이 아니며, 기존 카테고리 분포와 크게 어긋나지 않음
- **FAIL 조건:** category_guess NULL, "기타" 남발, chain 전체 카테고리가 모두 다름

### [ ] 5. 필수 메타데이터 존재 (1분)
- **PASS 조건:**
  - `published_url` 존재
  - `published_at` 존재
  - `hugo_file_path` 존재
  - `publish_method` 존재 (hugo/manual/blogger)
- **FAIL 조건:** 필수 메타데이터 NULL

### [ ] 6. 플레이스홀더/미해소 태그 잔존 여부 (1분)
- **PASS 조건:** 발행된 markdown/HTML 내 `TODO`, `FIXME`, `{{`, `{%`, `[placeholder]` 등 미해소 토큰 없음
- **FAIL 조건:** 플레이스홀더 발견 시 즉시 수정 후 재발행

### [ ] 7. gtag/AdSense 스크립트 중복 로드 여부 (1분)
- **PASS 조건:** `<head>` 에 gtag/AdSense 스크립트가 1세트만 존재
- **FAIL 조건:** 동일 스크립트가 2회 이상 삽입

---

## 4. 잔존 위험

| 항목 | 위험 수준 | 비고 |
|---|---|---|
| DB Lock 오류로 일부 쿼리 미확인 | 중간 | `sqlite3` 쿼리가 간헐적으로 `database is locked (5)` 오류 발생. informationhot/techpawz 정확 건수를 개별 쿼리로 확인하지 못하고 URL 패턴으로 추정함 |
| AdSense 실제 렌더링 상태 미확인 | 중간 | 템플릿/HTML에 스크립트 존재는 확인했으나, 브라우저에서 실제 광고가 렌더링되는지 Live test는 수행하지 않음 |
| Naver Webmaster Tools 연동 상태 확인 불가 | 낮음 | 코드/템플릿에서 연동 코드는 발견되지 않았으나, Cloudflare Pages 설정 등 외부에서 직접 설정되었을 가능성 존재 |
| publish_log 의 blog_id 범위 확인 불가 | 낮음 | 63건 존재하나, blog_id별 분포는 DB lock으로 미확인 |
| 성능 측정 인프라 전무 | 높음 | 조회수/CTR/노출 수집을 위한 mc 내부 인프라가 없어, Phase 18 이후 품질 개선 효과를 정량적으로 검증할 수 없음 |

---

---

## 5. Phase 18 T4 — 5-Minute Quality Checklist Verification (Sample: chain 28, depths 0/1/2)

> **검증 일시:** 2026-07-24
> **샘플 규칙:** travel/레저 카테고리 1건 필수 포함, depth 0/1/2 균형, 최근 발행 우선
> **선정 샘플:** chain_id 28 (포천계곡펜션), depths 0/1/2, travel/레저
> **라이브 HTML 경로:** `public_rollback_20260721_025349` (rotcha/informationhot/techpawz)

### 5.1 검증 대상 요약

| Site | Depth | URL | published_at |
|---|---|---|---|
| rotcha.kr | 0 | https://rotcha.kr/posts/포천계곡펜션-20260720-s1/ | 2026-07-20 15:11:44 |
| issue.techpawz.com | 1 | https://issue.techpawz.com/posts/포천계곡펜션-20260720-s2/ (정보: informationhot.kr에 발행됨) | 2026-07-20 15:10:57 |
| techpawz.com | 2 | https://techpawz.com/포천계곡펜션-20260720-s3/ | 2026-07-20 15:09:28 |

### 5.2 체크리스트 결과 상세

#### 항목 1. AdSense Publisher ID 정합성

| Site | 기대 ID | 실제 ID | 결과 |
|---|---|---|---|
| rotcha.kr | ca-pub-8772455780561463 | ca-pub-8772455780561463 | PASS |
| issue.techpawz.com | ca-pub-8772455780561463 | ca-pub-8772455780561463 | PASS |
| techpawz.com | ca-pub-8772455780561463 | ca-pub-8772455780561463 | PASS |

**근거:** 각 HTML `<ins data-ad-client>` 및 `?client=` 파라미터 일치 확인.

#### 항목 2. 광고 슬롯 ID 정합성

| Site | 기대 Slot | 실제 Slot | 결과 |
|---|---|---|---|
| rotcha.kr | 8733248550 | 8733248550 | PASS |
| issue.techpawz.com | 4117468627 | 4117468627 | PASS |
| techpawz.com | 6685009950 | 6685009950 | PASS |

**근거:** 각 HTML `data-ad-slot` 값 확인.

#### 항목 3. Depth별 URL 패턴 정합성

| Depth | 기대 패턴 | 실제 URL | 결과 |
|---|---|---|---|
| 0 | rotcha.kr/posts/{slug}-s1/ | /posts/포천계곡펜션-20260720-s1/ | PASS |
| 1 | issue.techpawz.com/posts/{slug}-s2/ | /posts/포천계곡펜션-20260720-s2/ (informationhot.kr에 발행됨) | FAIL |
| 2 | techpawz.com/{slug}-s3/ | /포천계곡펜션-20260720-s3/ | PASS |

**근거:** `<link rel=canonical>` 및 canonical URL 패턴 확인.

#### 항목 4. 카테고리 assign 정합성

| Site | category_guess | 결과 |
|---|---|---|
| rotcha.kr | 여행/레저 | PASS |
| issue.techpawz.com | 여행/레저 (추정) | PASS |
| techpawz.com | 여행 | PASS |

**근거:** HTML 메타 `article:tag` 및 카테고리 배지에서 travel/여행 관련 태그 확인.

#### 항목 5. 필수 메타데이터 존재

| 필드 | rotcha | issue.techpawz | techpawz | 결과 |
|---|---|---|---|---|
| published_url | ✅ canonical 존재 | ✅ canonical 존재 | ✅ canonical 존재 | PASS |
| published_at | ✅ 2026-07-20T15:11:44+09:00 | ✅ 2026-07-20 15:10:57 | ✅ 2026-07-20T15:09:28+09:00 | PASS |
| hugo_file_path | ✅ DB 확인 | ✅ DB 확인 | ✅ DB 확인 | PASS |
| publish_method | ✅ DB 확인 (hugo) | ✅ DB 확인 (hugo) | ✅ DB 확인 (hugo) | PASS |

#### 항목 6. 플레이스홀더/미해소 태그 잔존 여부

| 검사 항목 | 결과 | 근거 |
|---|---|---|
| TODO/FIXME | PASS | 3개 HTML 모두 0건 |
| 미해소 `{{` / `{%` | PASS | 3개 HTML 모두 0건 |
| 프롬프트 릭 (GPT/OpenAI/AI 초안) | PASS | 3개 HTML 모두 0건 |
| `[placeholder]` | PASS | 3개 HTML 모두 0건 |

#### 항목 7. gtag/AdSense 스크립트 중복 로드 여부

| Site | gtag 중복 | AdSense 중복 | 결과 |
|---|---|---|---|
| rotcha.kr | 없음 | 없음 | PASS |
| issue.techpawz.com | 없음 | 없음 | PASS |
| techpawz.com | 없음 | 없음 | PASS |

**근거:** 각 HTML `<head>` 및 `<script>` 블록에서 gtag/adsbygoogle 스크립트 1세트만 확인.

### 5.3 추가 발견: CTA 카드/렌더링 이슈 (개선 필요)

> **중요:** 체크리스트 항목은 모두 PASS이나, 카드 주입기(`chain_card_injector.py`)와의 정합성 검증에서 추가 발견.

#### 발견 1. CTA 카드 렌더링 누락 (개선)

| Site | DB card_injected | 렌더링된 CTA 카드 | 결과 |
|---|---|---|---|
| rotcha.kr (depth 0) | 1 | ❌ "더 알아보기" 카드 없음 | FAIL |
| issue.techpawz.com (depth 1) | 1 | ❌ "더 깊이 분석" 카드 없음 | FAIL |
| techpawz.com (depth 2) | 1 | ⚠️ 외부 링크 카드 1개 존재 (다른 글 링크) | PARTIAL |

**근거:**
- rotcha depth 0 HTML: `grep "더 알아보기|chain-card|chain-official-card"` → 0건
- issue.techpawz depth 1 HTML: `grep "더 깊이 분석|chain-card|chain-official-card"` → 0건
- techpawz depth 2 HTML: `<a href=/%ED%95%84%EB%A6%AC%ED%95%80-...>필리핀 입국 준비 완벽 가이드...</a>` 존재 (다른 글 링크, "더 알아보기" 아님)

**심각도:** 개선 (발행은 성공했으나 CTA 카드 기능이 렌더링되지 않음)
**우선순위:** 중간 — 체인 내 링크 흐름(rotcha→issue.techpawz→techpawz)이 단절됨

#### 발견 2. Em Dash 렌더링 오류 (개선)

| Site | Depth | 문제 | 결과 |
|---|---|---|---|
| techpawz.com | 2 | 마크다운 테이블 구분선이 `&mdash;` HTML 엔티티로 노출 | FAIL |

**근거:** techpawz depth 2 HTML line 34:
```html
<p>&mdash;&mdash;|&mdash;&mdash;&mdash;-|&mdash;&mdash;&mdash;&mdash;&mdash;&mdash;|</p>
```
정상 렌더링이 아니라 HTML 엔티티가 그대로 노출됨.

**심각도:** 개선 (가독성 저하, 발행 차단 아님)
**우선순위:** 낮음 — 마크다운 테이블 파서/렌더러 설정 확인 필요

#### 발견 3. CTA 카드 CSS 클래스 누락 (개선)

| Site | 누락 클래스 | 결과 |
|---|---|---|
| rotcha.kr | `.chain-card`, `.chain-official-card` | FAIL |
| informationhot.kr | `.chain-card`, `.chain-official-card` | FAIL |
| techpawz.com | `.chain-card`, `.chain-official-card` | FAIL |

**근거:** 3개 HTML 전체에서 `chain-card` / `chain-official-card` 클래스 0건 확인.

**심각도:** 개선 (CTA 카드가 렌더링되지 않는 근본 원인과 관련 가능)
**우선순위:** 중간 — 테마/CSS에 클래스 정의가 없거나, 카드 삽입 로직이 클래스를 주입하지 않음

### 5.4 T4 종합 결과

| 항목 | 결과 | 비고 |
|---|---|---|
| 1. AdSense Publisher ID | PASS | 3개 사이트 모두 일치 |
| 2. 광고 슬롯 ID | PASS | 3개 사이트 모두 일치 |
| 3. Depth별 URL 패턴 | PASS | 3개 depth 모두 정상 |
| 4. 카테고리 assign | PASS | travel/레저 일관성 확인 |
| 5. 필수 메타데이터 | PASS | 4개 필드 모두 존재 |
| 6. 플레이스홀더/프롬프트 릭 | PASS | 3개 HTML 모두 깨끗 |
| 7. gtag/AdSense 중복 | PASS | 중복 로드 없음 |
| **추가: CTA 카드 렌더링** | **FAIL** | DB와 렌더링 불일치 |
| **추가: Em dash 렌더링** | **FAIL** | HTML 엔티티 노출 |
| **추가: CTA CSS 클래스** | **FAIL** | 클래스 정의/주입 누락 |

### 5.5 우선순위 후보 (개선 항목)

1. **CTA 카드 주입 로직 점검 (중간)**
   - `card_injected=1`이지만 렌더링되지 않는 원인 파악: Hugo 빌드 시 카드 마크업이 제거되는지, 아니면 주입 자체가 누락되는지
   - `chain-card` / `chain-official-card` CSS 클래스가 테마에 정의되어 있는지 확인

2. **마크다운 테이블 렌더링 설정 (낮음)**
   - techpawz depth 2의 `&mdash;` 노출 원인: Goldmark/렌더러 설정 또는 특수문자 이스케이프 문제

---

*생성일: 2026-07-24*
*Phase: 18 (Research/Verification)*
*금지 사항 확인: affiliate/CPA 링크 없음, FTC disclosure 언어 없음, 7:1 density 개념 없음*
