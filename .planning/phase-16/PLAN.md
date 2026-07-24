# PLAN.md — Phase 16: 실전 검증 파이프라인

**Phase:** 16  
**Owner:** 신입 에이전트  
**Mode:** wave-based execution  
**Status:** ○ Planned

**테스트 키워드:** 하이바이풀빌라  
**예상 분류:** travel → lateral  
**Pass 조건:** 9개 검증 항목(슬롯/역할/MD문법/프롬프트릭/썸네일/R2/카드/외부링크/글품질) 전수 통과 + 대표님 실발행 승인

---

## Wave-0 — 사전 준비

**의미:** 로컬 환경 및 DB 상태를 확인하고, dry-run을 위한 기반을 점검한다.

- [ ] pytest 231/231 통과 확인
- [ ] Hugo 빌드 3사이트(rotcha / issue.techpawz / techpawz) 정상 확인
- [ ] DB 체인 현황 스냅샷 (총 체인 수, 최근 체인)
- [ ] `mc --help` 정상 동작 확인
- [ ] config/prompts.yaml draft_system / draft_user 최신 버전 캡처

**Pass 조건:** pytest 231/231 + Hugo 빌드 3/3 + mc 명령 정상

---

## Wave-1 — dry-run 실행 및 초안 품질 검증 (STEP-1)

**사전 조건:** Wave-0 완료  
**의미:** 키워드 "하이바이풀빌라"로 dry-run을 실행하고, 생성된 초안의 품질을 6개 항목으로 검증한다.

### 실행

```bash
mc "하이바이풀빌라" --dry-run 2>&1 | tee /tmp/dryrun_haibai.log
```

### 체크리스트

- [ ] **3개 슬롯 배정 확인**
  - Step 1: rotcha
  - Step 2: issue.techpawz
  - Step 3: techpawz
- [ ] **각 블로그 역할 분담 확인**
  - rotcha: 기초/위치/기본정보 중심인지
  - issue.techpawz: 실전/이용후기/심화정보 중심인지
  - techpawz: 예약방법/가격비교/딥다이브 중심인지
- [ ] **내용 겹침 여부**
  - 3개 글 간 중복 섹션이 없는지 (체인 방향 depth/lateral 적합도 함께 확인)
- [ ] **MD 문법 삽입 검증**
  - ```json 펜스 미닫힘 여부
  - frontmatter 누락 여부 (--- 시작/종료)
  - H2/H3 구조 깨짐 여부
  - 파이프(|)가 표 밖에 노출되지 않았는지
- [ ] **프롬프트 릭 여부**
  - draft_system 내용이 본문에 노출되지 않았는지
  - "절대 금지", "Role (역할)", "Chain Context" 등 키워드 노출 확인
- [ ] **분류 방향 적합도**
  - "하이바이풀빌라"가 travel/lateral로 분류되는지
  - 각도(angle)가 블로그 역할에 맞는지

**Pass 조건:** 체크리스트 6개 항목 전부 ✅ → Wave-2 진행  
**실패 시:** 문제 항목 기록 → PLAN.md에 수정 사항 반영 후 재시도

---

## Wave-2 — 이미지/썸네일 생성 검증 (STEP-2)

**사전 조건:** Wave-1 완료  
**의미:** dry-run 이후 이미지 생성 단계를 검증한다.

### 실행

```bash
# 생성된 이미지 경로 확인
ls -lt image/output/ 2>/dev/null | head -10
# R2 업로드 상태 확인
# 최근 체인의 이미지 경로 확인
```

### 체크리스트

- [ ] **썸네일 생성 정상**
  - 3개 블로그 각각 썸네일 생성 여부 (rotcha / issue.techpawz / techpawz)
  - 썸네일 포맷 (webp/png) 확인
- [ ] **R2 업로드 성공**
  - `upload_all_images()` 정상 완료 확인
  - R2 prefix가 site별 올바른지 (images/rotcha, images/issue-techpawz, images/techpawz)
- [ ] **업로드된 이미지 URL 실제 접근**
  - `curl -I https://img.techpawz.com/...` 200 확인
  - `curl -I https://img.rotcha.kr/...` 200 확인
- [ ] **이미지 사이즈/포맷 적합**
  - 1024x1024 (1:1) 확인
  - webp 포맷 확인
- [ ] **43건 고아 이미지 현황**
  - W6 게이트 정상 동작 중인지 (신규 발행에서 content_image_path 체크)
  - DB 조회: `content_image_path` 누락 포스트 수

**실패 시:** 문제 항목 기록 → 해당 이미지/업로드 모듈 수정 후 Wave-2 재시도  
**Pass 조건:** 체크리스트 5개 항목 전부 ✅ → Wave-3 진행

---

## Wave-3 — 카드 삽입 검증 (STEP-3)

**사전 조건:** Wave-2 완료  
**의미:** 체인 3단계 간 카드 연결이 올바른지 검증한다.

### 체크리스트

- [ ] **카드 위치 적절성**
  - rotcha 글 → issue.techpawz 글로 연결되는 카드
  - issue.techpawz 글 → techpawz 글로 연결되는 카드
  - 각 카드가 적절한 위치(H2 섹션 사이/본문 마지막)에 삽입되는지
- [ ] **카드 링크 URL 형식**
  - rotcha 글 카드 URL: `https://issue.techpawz.com/...`
  - issue.techpawz 글 카드 URL: `https://techpawz.com/...`
  - URL이 실제 유효한지 (curl 200)
- [ ] **마지막 techpawz 글 외부 카드**
  - `find_external_links()`로 하이바이풀빌라 예약페이지 URL 추출
  - 하이바이풀빌라 공식 홈페이지 URL 추출
  - Naver API fallback 동작 확인 (`_naver_fallback`)
  - 추출된 URL이 실제 유효한지 curl 확인
- [ ] **카드 HTML/MD 렌더링 깨짐**
  - 카드 HTML이 Hugo 빌드에서 깨지지 않는지
  - 인용 부호, 태그 닫힘 정상 확인

**실패 시:** 문제 항목 기록 → 카드 주입 로직 수정 후 Wave-3 재시도  
**Pass 조건:** 체크리스트 4개 항목 전부 ✅ → Wave-4 진행

---

## Wave-4 — 글쓰기 프롬프트 품질 검증 (STEP-4)

**사전 조건:** Wave-3 완료  
**의미:** prompts.yaml의 draft 프롬프트가 블로그 역할과 내용 겹침 방지에 적합한지 평가한다.

### 평가 기준

- [ ] **블로그별 역할 프롬프트 반영**
  - rotcha: 기초 개념, 위치, 기본정보 추출 지시
  - issue.techpawz: 실전 이용후기, 심화정보 추출 지시
  - techpawz: 예약방법, 가격비교, 딥다이브 추출 지시
- [ ] **숙소/장소 키워드 대응**
  - "하이바이풀빌라" 같은 장소 키워드에 위치/기본정보/예약정보 추출 지시가 프롬프트에 있는지
- [ ] **내용 겹침 방지 지시 구체성**
  - 각 단계별 "이전 포스트에서 다룬 기본 개념을 반복하지 말 것" 지시
  - 역할 분담이 구체적인 키워드 레벨로 명시되었는지
- [ ] **외부 링크 카드 지시**
  - 마지막 블로그(techpawz)에만 외부 링크 카드 삽입 지시
  - 이전 단계에는 내부 체인 카드만 삽입
- [ ] **금지 표현/ANTI-HALLUCINATION**
  - ABSOLUTE BAN 리스트가 최신인지
  - ANTI-HALLUCINATION 규칙이 충분히 구체적인지

**실패 시:** 문제 항목 기록 → prompts.yaml 수정 후 Wave-4 재시도  
**Pass 조건:** 체크리스트 5개 항목 전부 ✅ → Wave-5 진행

---

## Wave-5 — 종합 판단 및 실발행 승인 요청 (STEP-5)

**사전 조건:** Wave-1~4 완료  
**의미:** 위 4개 Wave 결과를 종합하여 실발행 가능 여부를 판단한다.

### 종합 보고서

| 항목 | 상태 | 문제 내용 | 수정 필요 여부 |
|------|------|-----------|---------------|
| 슬롯 배정 | ✅/❌ | | |
| 역할 분담 | ✅/❌ | | |
| MD 문법 | ✅/❌ | | |
| 프롬프트 릭 | ✅/❌ | | |
| 썸네일 생성 | ✅/❌ | | |
| R2 업로드 | ✅/❌ | | |
| 카드 삽입 | ✅/❌ | | |
| 외부 링크 | ✅/❌ | | |
| 글 품질 | ✅/❌ | | |

### 판단 규칙

- **수정 필요 항목 = 0개** → 실발행 승인 요청 (대표님)
- **수정 필요 항목 ≥ 1개** → 수정 완료 후 Wave-1~4 재검증, 재검증 완료 후 승인 요청

### 실행 (조건부)

```bash
# 실발행 (승인 후)
mc "하이바이풀빌라" 2>&1 | tee /tmp/publish_haibai.log

# Hugo 빌드 + 배포
cd /Users/twinssn/Projects/rotcha-blog && hugo --gc --minify
env -u CLOUDFLARE_API_TOKEN -u CLOUDFLARE_ACCOUNT_ID -u CF_DNS_TOKEN -u CLOUDFLARE_WORKERS_AI_API_TOKEN -u R2_ENDPOINT \
  wrangler pages deploy ./public --project-name rotcha-blog

cd /Users/twinssn/Projects/issue-techpawz-hugo && hugo --gc --minify
env -u CLOUDFLARE_API_TOKEN -u CLOUDFLARE_ACCOUNT_ID -u CF_DNS_TOKEN -u CLOUDFLARE_WORKERS_AI_API_TOKEN -u R2_ENDPOINT \
  wrangler pages deploy ./public --project-name issue-techpawz-hugo

cd /Users/twinssn/Projects/techpawz-hugo && hugo --gc --minify
env -u CLOUDFLARE_API_TOKEN -u CLOUDFLARE_ACCOUNT_ID -u CF_DNS_TOKEN -u CLOUDFLARE_WORKERS_AI_API_TOKEN -u R2_ENDPOINT \
  wrangler pages deploy ./public --project-name techpawz-hugo
```

**Pass 조건:** 종합 보고서 수정 필요 항목 0개 + 대표님 승인

---

## Definition of Done

- [ ] 모든 Wave Pass 조건 충족
- [ ] STEP-1~4 체크리스트 전수 ✅
- [ ] 종합 보고서 작성 완료
- [ ] 대표님 실발행 승인 완료
- [ ] 실발행 완료
- [ ] Hugo 빌드 + 배포 완료
- [ ] `PLAN.md` 각 항목 체크 표시 완료
- [ ] STATE.md 갱신

## Repository

- **Working dir:** `/Users/twinssn/projects2/mc`
- **Phase dir:** `.planning/phase-16`
- **Branch:** `feat/replace-informationhot-to-issue-techpawz` (또는 실발행 후 main)
