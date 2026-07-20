# Phase 10: Phase 9 Aftermath — 회귀 방지 및 잔여 이슈 해결

**Goal:** Phase 9에서 발견·수정된 모든 fix의 회귀를 방지하고, 3개 사이트에 CSS/SRI 수정을 전파하며, R2 썸네일 업로드 실패의 근본 원인을 수정한다.

**Prerequisite:** Phase 9 완료 (프롬프트 릭, 이미지 치환 순서, 썸네일 개선, JSON 릭, CTA 릭, SRI/CORS rotcha 적용 완료).

**Scope (locked):** R2 업로드 디버깅, CSS/SRI 3개 사이트 전파, audit_posts.py, E2E 검증. KREA AI는 무기한 연기.

**Reference:**
- `CONTEXT.md` — 7개 이슈 분류표 (Already Fixed / Needs Propagation / Unresolved / Missing)

---

## Phase 9 Gap Analysis — 이슈 발굴 배경

Phase 9 PLAN은 원래 4개 Wave 8개 Task (프롬프트 릭, 이미지 치환, 썸네일, 마커 지시문)로 구성됐으나, 실행 중 4개 추가 이슈 발견:

| # | Issue | Discovered During | Missing from Plan? |
|---|-------|-------------------|--------------------|
| G1 | JSON metadata prompt leak (`_parse_meta()` → `text[pos:]`) | Phase 9 테스트 중 | ✅ 누락 |
| G2 | CTA 인라인 블록 릭 ("더 깊이 알아보기") | Phase 9 테스트 중 | ✅ 누락 |
| G3 | SRI/CORS CSS 렌더링 (pages.dev integrity 속성) | Phase 9 배포 후 발견 | ✅ 누락 |
| G4 | R2 썸네일 업로드 실패 | Phase 9 검증 중 발견 | ✅ 누락 |

G1~G3은 이미 수정 완료. G4는 원인 불명 — Phase 10에서 수정.

---

## Architecture

```
Phase 10 Fix Propagation
├── Wave 1: R2 업로드 디버깅
│   ├── 10-1: r2_uploader.py upload_all_images() credentials 검증
│   └── 10-2: chain_publisher_core.py upload 호출 체인 디버깅
│
├── Wave 2: CSS/SRI 3개 사이트 전파
│   ├── 10-3: informationhot-hugo head.html + fixed-fill-blur.html SRI/CORS 적용
│   └── 10-4: techpawz-hugo head.html + fixed-fill-blur.html SRI/CORS 적용
│
├── Wave 3: 회귀 방지 audit 체계
│   └── 10-5: audit_posts.py 전수검사 도구 생성
│
└── Wave 4: E2E 통합 검증
    └── 10-6: 3사이트 Hugo 빌드 + CF Pages 배포 + audit 통과
```

---

## Wave 1: R2 썸네일 업로드 실패 수정 (2 files)

### Background

`chain_publisher_core.py`의 `publish_chain()` → `_publish_hugo()` → `upload_all_images()` 호출 체인에서 R2 업로드가 실패하고 있음. 신규 포스트(20260720 체인)의 썸네일이 R2에 전혀 존재하지 않음. 로컬 `output/images/thumb_pexels_*.webp`는 정상 생성됨.

**가설:**
1. `get_r2_client()`가 R2 credentials를 로드하지 못함 (env 미설정 또는 .env.common 미로드)
2. `upload_all_images()` 호출 시점에 R2 키나 prefix가 제대로 전달되지 않음
3. `upload_all_images()`가 `output/images/`만 스캔하지만 실제 업로드할 경로가 다름
4. R2 연결 자체는 성공하나 권한 부족 (InvalidAccessKeyId 등)

### Task 10-1: `mde2/app/services/r2_uploader.py` — R2 credentials 검증

**파일:** `/Users/twinssn/Projects/mde2/app/services/r2_uploader.py`

**목적:** R2 업로드 실패의 1차 원인 — credentials 로딩 방식 확인

**검증 항목:**
1. `get_r2_client()` 함수에서 R2 credentials를 어떻게 로드하는가?
   - 환경변수: `R2_ENDPOINT`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME` 등
   - `.env.common` 파일을 로드하는가?
   - `chain_publisher.py` 실행 시점에 이 env들이 설정되어 있는가?
2. `upload_all_images()`의 시그니처와 호출 방식
   - 어떤 파라미터를 받는가? (chain_id? base_path? site?)
   - 내부에서 `get_r2_client()`를 호출하는가, 외부에서 주입받는가?

**수정 (필요시):**
- credentials 로딩 실패 시 명확한 에러 메시지 출력
- `.env.common` 로드 실패 시 fallback 로직
- R2 업로드 성공/실패 로깅 추가 (파일명, 성공 여부, HTTP status)

**가설 불일치 시 escalation:**
4개 가설 모두 원인이 아닌 경우, `upload_all_images()` 함수 내부에 `--verbose` 수준의 디버그 로깅을 추가하고 실제 R2 응답(HTTP status, error body)을 캡처. `chain_publisher.py --image --verbose` 실행 결과를 바탕으로 추가 가설 수립.

**성공 기준:** `get_r2_client()`가 유효한 R2 client 반환, `upload_all_images()` 호출 시 R2에 파일 업로드 성공

### Task 10-2: `chain_publisher_core.py` — R2 upload 호출 체인 검증

**파일:** `chain_publisher_core.py`

**목적:** `publish_chain()` → `_publish_hugo()` 경로에서 `upload_all_images()`가 올바르게 호출되는지 검증

**검증 항목:**
1. `publish_chain()`에서 `upload_all_images()`를 호출하는가?
   - 호출 조건은? (--image 플래그? publish 플래그?)
   - 호출 전에 R2 env가 설정되어 있는지 확인하는 코드가 있는가?
2. `_publish_hugo()`에서 이미지 경로 교체 전에 R2 업로드가 완료되는가?
3. `--image` 단계에서 생성된 `output/images/` 파일 목록과 R2 업로드 대상 목록이 일치하는가?

**수정 (필요시):**
- `upload_all_images()` 호출 전 R2 client health check 추가
- 업로드 성공/실패를 `chain_db`에 기록 (추후 audit 용이)
- 실패 시 재시도 로직 (최대 3회)

**성공 기준:** `--publish` 실행 시 모든 `thumb_*.webp`가 R2에 업로드되고, Hugo index.md의 이미지 URL이 R2 URL로 교체됨

---

## Wave 2: CSS/SRI 3개 사이트 전파 (2 files × 2 sites = 4 files)

### Background

rotcha-blog에 SRI/CORS 대응을 위해 2개 파일 수정 완료:
- `rotcha-blog/layouts/partials/head.html` — 6개 `<link>` 태그에 `integrity` + `crossorigin="anonymous"` 추가
- `rotcha-blog/layouts/partials/header/fixed-fill-blur.html` — `background-blur.js`에 `crossorigin="anonymous"` 추가

informationhot-hugo와 techpawz-hugo는 동일 Blowfish 테마를 사용하므로 같은 수정이 필요. 단, 사이트별로 `head.html`이 다를 수 있으므로 diff를 확인한 후 적용.

### Task 10-3: `informationhot-hugo` SRI/CORS 적용

**파일:**
- `informationhot-hugo/layouts/partials/head.html` (없으면 `layouts/partials/head.html`)
- `informationhot-hugo/layouts/partials/header/fixed-fill-blur.html` (없으면 생성)

**수정:**
1. `head.html`의 6개 `<link rel="stylesheet" ...>` 태그에 `crossorigin="anonymous"` 속성 추가
2. `fixed-fill-blur.html`의 `<script src="/js/background-blur.js" ...>`에 `crossorigin="anonymous"` 추가

**주의:** rotcha-blog와 동일한 Blowfish 테마지만 partial 구조나 테마 오버라이드가 다를 수 있음. 먼저 파일 존재 여부 확인 후 diff 적용.

**성공 기준:** Hugo 빌드 시 SRI/CORS 관련 경고 0건, pages.dev에서 CSS 정상 렌더링

### Task 10-4: `techpawz-hugo` SRI/CORS 적용

**파일:**
- `techpawz-hugo/layouts/partials/head.html`
- `techpawz-hugo/layouts/partials/header/fixed-fill-blur.html`

**수정:** informationhot-hugo와 동일

**성공 기준:** Hugo 빌드 시 SRI/CORS 관련 경고 0건, pages.dev에서 CSS 정상 렌더링

---

## Wave 3: 회귀 방지 Audit 체계 (1 file new)

### Background

현재 Phase 9 fix(프롬프트 릭, JSON 릭, CTA 릭, 마커 처리)가 차기 체인에서 제대로 동작하는지 확인할 자동화된 검증 도구가 없음. 체인 생성 후 발행 전에 audit을 돌려 0건을 확인하는 프로세스 필요.

### Task 10-5: NEW `audit/audit_chain.py` — 체인 발행 품질 audit 도구

**파일:** `/Users/twinssn/projects2/mc/audit/audit_chain.py`

**목적:** 체인 발행 전/후 품질 감사 — 프롬프트 릭, 미해소 마커, CTA 블록, CSS 경고를 전수검사

**인터페이스:**
```
python -m audit.audit_chain --chain-id N          # 특정 체인 audit
python -m audit.audit_chain --all                  # 모든 체인 전수검사
python -m audit.audit_chain --chain-id N --fix     # 발견된 문제 자동 수정
```

**검사 항목:**

1. **프롬프트 릭 검사** (`check_prompt_leak`)
   - Hugo index.md 본문에서 Phase 9 `_PROMPT_SECTION_RE` 패턴 검색
   - `## 서론`, `## 본론`, `# Role (역할)`, `# Chain Context`, `절대 금지`, `이미지 플레이스홀더` 등
   - 적발 시: 파일 경로 + 매칭 패턴 + 라인 번호 출력

2. **미해소 마커 검사** (`check_unresolved_markers`)
   - `<!-- thumbnail: ... -->`, `<!-- image: ... -->` (레거시 마커)
   - `<!-- todo:image -->`, `<!-- todo:chart -->` (미해소 플레이스홀더)
   - `<!--todo:image-->`, `<!--todo:chart-->` (공백 없는 variant)
   - 적발 시: 파일 경로 + 마커 종류 + 라인 번호 출력

3. **CTA 인라인 블록 검사** (`check_cta_leak`)
   - `더 깊이 알아보기` 텍스트가 본문에 삽입되었는지 확인
   - `<div class="cta-...">` 인라인 CTA HTML 블록 확인
   - 적발 시: 파일 경로 + 라인 번호 출력

4. **featureimage URL 검사** (`check_featureimage_url`)
   - frontmatter의 `featureimage`가 `thumb_thumb_` 이중 접두사인지 확인
   - `images/` 상대경로가 아닌 R2 전체 URL(`https://...r2.dev/...`)인지 확인

5. **이미지 존재 검사** (`check_images_exist`)
   - frontmatter의 `featureimage` URL이 실제 R2에 존재하는지 HEAD 요청으로 확인
   - 본문 이미지 URL도 동일 확인
   - 404/403 발생 시 경고 출력

6. **Hugo 빌드 검사** (`check_hugo_build`)
   - 각 사이트별 Hugo 빌드 실행 (`hugo --gc --minify`)
   - 빌드 에러/경고 출력 (특히 CSS/SRI 관련 경고)

**출력 포맷:**
```
audit_chain.py — Chain #29 (seed: "테스트 키워드")

◆ Prompt Leak:
  ✗ /path/to/post/index.md:42 — 매칭: "## 서론"

◇ Unresolved Markers:
  ✓ 모든 마커 정상 해소됨 (0건)

◇ CTA Leak:
  ✓ CTA 블록 없음 (0건)

◆ featureimage URL:
  ✓ 모든 이미지 R2 URL 정상

◇ Images Exist:
  ✓ 3/3 이미지 R2 존재 확인 완료

◇ Hugo Build:
  ✓ rotcha: 빌드 성공 (0 warnings)
  ✓ informationhot: 빌드 성공 (0 warnings)
  ✓ techpawz: 빌드 성공 (0 warnings)

══ Result: 1 FAIL (prompt leak) ══
```
또는
```
══ Result: ALL PASS — 0 issues across 6 checks ══
```

**--fix 모드** (선택):
- 프롬프트 릭 발견 시: 해당 라인 제거 (Phase 9 `_strip_prompt_leak()` 동일 로직)
- 미해소 마커 발견 시: 해당 마커 제거 (Phase 9 cleanup regex 동일 로직)
- CTA 블록 발견 시: Phase 9 `_sanitize_markdown_body()` 호출

**비고:**
- Hugo 빌드 검사는 무거우므로 `--quick` 플래그 시 skip
- R2 존재 확인은 네트워크 I/O가 있으므로 timeout 5s 적용
- 기존 체인(Phase 5 이전)은 검사 대상에서 제외 (--all 시에만 검사)

---

## Wave 4: E2E 통합 검증 (manual execution)

### Task 10-6: 3사이트 Hugo 빌드 + CF Pages 배포 + audit 통과

**절차:**

1. **audit 전수검사** (기존 체인)
   ```
   python -m audit.audit_chain --chain-id 26  # 체인 26 (rotcha)
   python -m audit.audit_chain --chain-id 27  # 체인 27 (informationhot)
   python -m audit.audit_chain --chain-id 28  # 체인 28 (techpawz)
   python -m audit.audit_chain --chain-id 29  # 체인 29 (테스트 체인)
   ```

2. **Hugo 빌드** (3개 사이트)
   ```bash
   cd /Users/twinssn/Projects/rotcha-blog && hugo --gc --minify
   cd /Users/twinssn/Projects/informationhot-hugo && hugo --gc --minify
   cd /Users/twinssn/Projects/techpawz-hugo && hugo --gc --minify
   ```

3. **CF Pages 배포** (3개 사이트, hugh79757 프로필)
   ```bash
   # 각 사이트 배포 전 env unset
   unset CLOUDFLARE_API_TOKEN CLOUDFLARE_ACCOUNT_ID CF_DNS_TOKEN CLOUDFLARE_WORKERS_AI_API_TOKEN R2_ENDPOINT
   
   cd /Users/twinssn/Projects/rotcha-blog && wrangler --profile hugh79757 pages deploy ./public --project-name rotcha-blog
   cd /Users/twinssn/Projects/informationhot-hugo && wrangler --profile hugh79757 pages deploy ./public --project-name informationhot-hugo
   cd /Users/twinssn/Projects/techpawz-hugo && wrangler --profile hugh79757 pages deploy ./public --project-name techpawz-hugo
   ```

4. **HTTP 200 확인**
   - 각 사이트 pages.dev URL 접속 → HTTP 200
   - CSS 렌더링 정상 (브라우저 콘솔 SRI/CORS 에러 0)
   - 이미지 로딩 정상 (R2 URL 200)

5. **신규 체인 E2E** (회귀 테스트)
   ```
   python chain_publisher.py --seed "회귀테스트" --draft --image --publish
   python -m audit.audit_chain --chain-id <new>  # 0건 통과
   ```

**성공 기준:** audit 6개 검사 모두 PASS, 3개 사이트 배포 성공, HTTP 200, CSS/이미지 정상 렌더링

---

## Verification Criteria

| # | Criterion | Check Method | Wave |
|---|-----------|-------------|------|
| V1 | R2 업로드 성공 | 신규 체인 생성 후 R2에 `images/techpawz/2026072*` 파일 존재 확인 | W1 |
| V2 | get_r2_client() credentials 정상 | `get_r2_client()` 호출 시 유효한 S3 client 반환 | W1 |
| V3 | informationhot CSS/SRI 정상 | Hugo 빌드 0 warning, pages.dev CSS 렌더링 OK | W2 |
| V4 | techpawz CSS/SRI 정상 | Hugo 빌드 0 warning, pages.dev CSS 렌더링 OK | W2 |
| V5 | audit 체계 가동 | `python -m audit.audit_chain --chain-id 29` 실행 가능 | W3 |
| V6 | audit 프롬프트 릭 0건 | 기존 체인 audit 시 프롬프트 릭 0건 | W3 |
| V7 | audit 미해소 마커 0건 | 기존 체인 audit 시 미해소 마커 0건 | W3 |
| V8 | audit CTA 블록 0건 | 기존 체인 audit 시 CTA 블록 0건 | W3 |
| V9 | 3개 사이트 배포 성공 | `wrangler pages deploy` 3/3 성공 | W4 |
| V10 | 신규 체인 E2E 회귀 없음 | 신규 체인 생성 + audit ALL PASS | W4 |

---

## File Summary

| File | Action | Task |
|------|--------|------|
| `mde2/app/services/r2_uploader.py` | READ + MODIFY | 10-1 |
| `chain_publisher_core.py` | READ + MODIFY | 10-2 |
| `informationhot-hugo/layouts/partials/head.html` | MODIFY | 10-3 |
| `informationhot-hugo/layouts/partials/header/fixed-fill-blur.html` | MODIFY | 10-3 |
| `techpawz-hugo/layouts/partials/head.html` | MODIFY | 10-4 |
| `techpawz-hugo/layouts/partials/header/fixed-fill-blur.html` | MODIFY | 10-4 |
| NEW: `audit/audit_chain.py` | CREATE | 10-5 |
| (manual) Hugo 빌드 + 배포 | EXECUTE | 10-6 |

**Total:** 7 files, 6 tasks, 4 waves.
