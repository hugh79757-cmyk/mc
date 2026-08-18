# Requirements: mc (Manual Chain)

**Defined:** 2026-07-18
**Last updated:** 2026-08-18 — M3 (9점 품질 파이프라인) 요구사항 등록
**Core Value:** One random keyword → 3 interconnected blog posts on 3 different domains, each going deeper than the last, with images and cross-links — fully automated.

## v1 Requirements

| Requirement | Phase | Status |
|-------------|-------|--------|
| SCF-01: .gitignore | Phase 1 | ✅ Validated |
| SCF-02: requirements.txt | Phase 1 | ✅ Validated |
| SCF-03: .env.example | Phase 1 | ✅ Validated |
| CFG-01: chain_config.yaml | Phase 1 | ✅ Validated |
| CFG-02: prompts.yaml | Phase 1 | ✅ Validated |
| DB-01: chain_db.py | Phase 1 | ✅ Validated |
| DERV-01: chain_deriver 3 topics | Phase 2 | ✅ Validated |
| DERV-02: keyword routing | Phase 2 | ✅ Validated |
| DERV-03: structured JSON | Phase 2 | ✅ Validated |
| DRAFT-01: Hugo MD generation | Phase 2 | ✅ Validated |
| DRAFT-02: chain context injection | Phase 2 | ✅ Validated |
| DRAFT-03: Hugo frontmatter rules | Phase 2 | ✅ Validated |
| IMG-01: Pollinations Flux | Phase 3 | ✅ Validated |
| IMG-02: thumbnail 1200×630 | Phase 3 | ✅ Validated |
| IMG-03: GPT image prompts | Phase 3 | ✅ Validated |
| IMG-04: image_injector | Phase 3 | ✅ Validated (Phase 7: featureimage) |
| IMG-05: static/images/ | Phase 3 | 🔴 Deprecated → IMG-v2-01 (R2) |
| PUB-01: Hugo draft MD | Phase 3 | ✅ Validated |
| PUB-02: reverse publish order | Phase 3 | ✅ Validated |
| CARD-01: bridge cards | Phase 3 | ✅ Validated (Phase 6: DualCTA) |
| CLI-01: chain_publisher.py CLI | Phase 3 | ✅ Validated |
| CLI-02: operator checkpoints | Phase 3 | ✅ Validated |
| CLI-03: progress/error handling | Phase 3 | ✅ Validated |

## v2/v3 Additions (Phase 5-8)

| Requirement | Phase | Status |
|-------------|-------|--------|
| IMG-v2-01 (R2 upload) | Phase 5 | ✅ Validated |
| IMG-v2-02 (WebP) | Phase 5 | ○ Pending (low priority) |
| PUB-v2-01 (mde2 rewrite) | Phase 5 | ✅ Validated |
| LOOP-01 (Hub + spoke) | Phase 6 | ✅ Validated |
| LOOP-02 (DualCTA) | Phase 6 | ✅ Validated |
| SEARCH-01 (Naver API) | Phase 7 | ✅ Validated |
| IMG-v3-01 (Unsplash/Pexels) | Phase 7 | ✅ Validated |
| IMG-v3-02 (Content image pipeline) | Phase 7 | ✅ Validated |
| CHART-01 (GPT chart recognition) | Phase 8 | ✅ Validated |
| CHART-02 (Pillow chart rendering) | Phase 8 | ✅ Validated |
| CHART-03 (Korean font support) | Phase 8 | ✅ Validated |

## Phase 14 Additions

| Requirement | Phase | Status |
|-------------|-------|--------|
| CLI-v2-01: `mc <keyword>` single entry point | Phase 14 | ✅ Validated |
| CLI-v2-02: `--resume` interrupted chain | Phase 14 | ✅ Validated |
| CLI-v2-03: `--background` detached process | Phase 14 | ✅ Validated |
| CLI-v2-04: `pip install -e .` global `mc` command | Phase 14 | ✅ Validated |
| CLI-v2-05: `_ensure_frontmatter()` FM preservation | Phase 14 P1 | ✅ Validated |
| IMG-v4-01: published_md for card injection R2 preservation | Phase 14 R2 | ✅ Validated |
| IMG-v4-02: techpawz R2 bucket branching (techpawz-images) | Phase 14 R2 | ✅ Validated |
| IMG-v4-03: content_image_path backfill (15/15) | Phase 14 P2 | ✅ Validated |

## Coverage

- v1 requirements: 23 total, 22 validated, 1 deprecated (IMG-05 → R2)
- v2/v3 additions: 11 mapped to Phase 5-8
- Phase 14 additions: 8 mapped
- Unmapped: 0 ✓

---

## Out of Scope

| Feature | Reason |
|---------|--------|
| Non-Hugo platforms | All 3 blogs are Hugo; v1 is Hugo-only |
| Text gen via Pollinations | Pollen credits required; OpenAI handles drafting |
| Multi-account Pollinations | Single anonymous tier sufficient for blog scale |
| Image alt-text generation | Static alt text sufficient for v1 |
| Social media auto-posting | Out of scope for core chain pipeline |

---

## M2 — 정보가 3-블로그 체인 복제 (Phase 37-40)

**등록:** 2026-08-02 — mc 복제 방식 타당성 조사 결과 반영.
**종료 상태:** 복제 레포 + 필수 분리 + 정보가 3사이트 셋업 + chain_config 교체 + dry-run 검증. 실발행은 별도 승인.

### 복제/분리 (Phase 37)

| Requirement | Phase | Status |
|-------------|-------|--------|
| CLONE-01: 복제 레포 git 생성 + 기존 mc origin과 원격 분리 | 37 | ○ Pending |
| CLONE-02: 복제 레포 `.env` 재생성 (R2/KREA 키, git 미추적) | 37 | ○ Pending |
| CLONE-03: DB 분리 — chain_config `db_path`를 복제 레포 내 경로로 교체 (5000 공유 해제) | 37 | ○ Pending |
| CLONE-04: shared vendoring — ai_writer.py + env_loader.py + models.yaml 복사, mc_paths.py PATH_5000 제거 | 37 | ○ Pending |
| CLONE-05: R2 매핑 키 추가 — informationhot / 5.informationhot (kuta는 기존 존재) | 37 | ○ Pending |

### 정보가 3사이트 인프라 (Phase 38)

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-01: 정보가 3사이트에 shortcode 3종 (chain-card / chain-official-card / dual-cta) 파랑(#2563eb) 신규 생성 | 38 | ○ Pending |
| INFRA-02: 5.informationhot-hugo baseURL 플레이스홀더(example.org) → 5.informationhot.kr 수정 | 38 | ○ Pending |
| INFRA-03: kuta / 5 사이트 static/ads.txt 추가 | 38 | ○ Pending |
| INFRA-04: CF Pages 프로젝트 3개 매핑 확인 (informationhot-hugo / kuta-hugo / 5-informationhot) | 38 | ○ Pending |

### chain_config 교체 (Phase 39)

| Requirement | Phase | Status |
|-------------|-------|--------|
| CFG-M2-01: sites에 정보가 3개 Hugo 사이트 정의 (hugo_root/cf_pages_project/permalink/content_dir/card_cta) | 39 | ○ Pending |
| CFG-M2-02: chain_blogs → {0: informationhot, 1: kuta, 2: 5_informationhot} | 39 | ○ Pending |
| CFG-M2-03: chain_blog_mapping.default depth/swallow/lateral 리스트 교체 | 39 | ○ Pending |
| CFG-M2-04: 기존 사이트 정의(rotcha/issue.techpawz/techpawz/2_techpawz/65_informationhot) 처리 결정 및 반영 | 39 | ○ Pending |
| CFG-M2-05: 카드 색상 파랑 적용 검증 (shortcode) | 39 | ○ Pending |

### 검증 (Phase 40)

| Requirement | Phase | Status |
|-------------|-------|--------|
| VERIFY-M2-01: e2e dry-run 3종 통과 (derive/draft/publish dry-run) | 40 | ○ Pending |
| VERIFY-M2-02: pytest green 유지 (기존 851건 + 신규) | 40 | ○ Pending |
| VERIFY-M2-03: DoD 체크리스트 — 실발행은 별도 승인 게이트로 이월 | 40 | ○ Pending |

## M2 Out of Scope

| Feature | Reason |
|---------|--------|
| 정보가 3사이트 실발행 | 검증 통과 후 대표 승인 게이트 (다음 마일스톤) |
| 5000 레포와의 발행 충돌 정합 | 5000이 정보가 사이트 관리 중 — 통합은 별도 논의 (미확정 이월) |
| external 카드 파랑 전면 통일 | html_renderer.py 수정 필요 — 체인 카드만 파랑 확정 |
| 정보가 사이트 기존 콘텐츠 slug 정합 | 536/2036/34건 기존 글 — 충돌 정책 미확정 이월 |

---

## M3 — 9점 품질 달성을 위한 파이프라인 개선 (Phase 41-47)

**등록:** 2026-08-18 — 최근 발행 블로그 품질 점수 5.8~7.2점. Phase 0~6 설계 기반.
**선행 조건:** M2(Phase 37-40) 완료.
**종료 상태:** 모든 Phase 41-47 완료 + pytest green + 최소 1개 키워드로 e2e 품질 점수 9.0+ 달성.

### Phase 0: 산출물 계약서 정의 (Phase 41)

| Requirement | Phase | Status |
|-------------|-------|--------|
| QC-CONTRACT-01: contracts/ 디렉토리 생성 + per-blog YAML 계약서 (rotcha/issue.techpawz/techpawz) | 41 | ○ Pending |
| QC-CONTRACT-02: YAML에 필수 섹션·금지 섹션·제목 패턴·출처 규칙 정의 | 41 | ○ Pending |
| QC-CONTRACT-03: contract_loader.py — YAML 로드 + 스키마 검증 | 41 | ○ Pending |
| QC-CONTRACT-04: quality_gate.py — 계약 기반 검증 엔진 (publish 전 계약 충족 여부 판정) | 41 | ○ Pending |
| QC-CONTRACT-05: pytest — 계약 로드·검증 테스트 | 41 | ○ Pending |

### Phase 1: 제목-본문 계약 검증 (Phase 42)

| Requirement | Phase | Status |
|-------------|-------|--------|
| QC-TITLE-01: title_body_checker.py — 제목에서 핵심 약속 토픽 추출 ("양귀비 개화시기 및 산책코스" → ["양귀비 개화시기", "산책코스"]) | 42 | ○ Pending |
| QC-TITLE-02: 본문 H2/H3 헤딩 + 섹션 본문 파싱 | 42 | ○ Pending |
| QC-TITLE-03: 각 약속 토픽이 본문 섹션에 실질적으로 다뤄졌는지 확인 (단순 키워드 매칭이 아닌 구체적 정보 포함 여부) | 42 | ○ Pending |
| QC-TITLE-04: 미충족 약속 1개 이상 시 발행 차단 + 누락 약속 리포트 | 42 | ○ Pending |
| QC-TITLE-05: quality_gate.py에 제목 검증 게이트 통합 | 42 | ○ Pending |
| QC-TITLE-06: pytest — 제목-본문 검증 테스트 (10건) | 42 | ○ Pending |

### Phase 2: 사실성 필터 — 근거 없는 수치/후기 차단 (Phase 43)

| Requirement | Phase | Status |
|-------------|-------|--------|
| QC-FACT-01: 프롬프트에 출처 태그 규칙 하드코딩 ("[출처: URL 또는 기관명, 조회일]" 태그 없이 수치 금지) | 43 | ○ Pending |
| QC-FACT-02: factuality_checker.py — 생성된 MD에서 숫자 패턴(퍼센트, 만족도, "N명", 가격 등) 추출 | 43 | ○ Pending |
| QC-FACT-03: 추출된 수치 문장에 [출처:] 태그 존재 여부 검사 | 43 | ○ Pending |
| QC-FACT-04: 태그 없는 수치 문장 발견 시 발행 차단 + 해당 문장 목록 리포트 | 43 | ○ Pending |
| QC-FACT-05: 기존 `_strip_prompt_leak()` 패턴과 통합 | 43 | ○ Pending |
| QC-FACT-06: quality_gate.py에 사실성 검증 게이트 통합 | 43 | ○ Pending |
| QC-FACT-07: pytest — 사실성 필터 테스트 | 43 | ○ Pending |

### Phase 3: 블로그 간 중복 제거 및 역할 강제 (Phase 44)

| Requirement | Phase | Status |
|-------------|-------|--------|
| QC-XBLOG-01: cross_blog_checker.py — 3개 글 본문을 문장 단위로 분리 | 44 | ○ Pending |
| QC-XBLOG-02: n-gram 또는 SequenceMatcher로 문장 유사도 검사 (30% 이상 겹치면 차단) | 44 | ○ Pending |
| QC-XBLOG-03: 역할별 필수 요소 검사 — rotcha(코스/일정), issue(비교 대상 2개+), techpawz(액션 아이템) | 44 | ○ Pending |
| QC-XBLOG-04: 독자 질문 차별화 검사 — 세 글의 핵심 질문이 서로 다른지 확인 | 44 | ○ Pending |
| QC-XBLOG-05: quality_gate.py에 중복 검증 게이트 통합 | 44 | ○ Pending |
| QC-XBLOG-06: pytest — 블로그 간 중복 해소 테스트 | 44 | ○ Pending |

### Phase 4: HTML 렌더링 중복 검사 (Phase 45)

| Requirement | Phase | Status |
|-------------|-------|--------|
| QC-HTML-01: html_render_checker.py — Hugo 빌드 후 HTML 파싱 | 45 | ○ Pending |
| QC-HTML-02: `<title>` 태그와 본문 첫 `<h1>`/`<h2>` 동일 문자열 경고 | 45 | ○ Pending |
| QC-HTML-03: CTA 패턴 2회 이상 중복 시 차단 | 45 | ○ Pending |
| QC-HTML-04: 같은 텍스트 블록 반복 검사 | 45 | ○ Pending |
| QC-HTML-05: 기존 audit_format.py 검증 항목과 통합 | 45 | ○ Pending |
| QC-HTML-06: quality_gate.py에 렌더링 검증 게이트 통합 | 45 | ○ Pending |
| QC-HTML-07: pytest — HTML 렌더링 중복 테스트 | 45 | ○ Pending |

### Phase 5: 리서치 보강 — 생성 전 팩트 수집 (Phase 46)

| Requirement | Phase | Status |
|-------------|-------|--------|
| QC-RESEARCH-01: pre_publish_researcher.py — 키워드 → 웹 검색 → 구조화된 팩트시트 생성 | 46 | ○ Pending |
| QC-RESEARCH-02: 공식 사이트, 지자체 관광 페이지, 네이버 지도/카카오맵 정보 수집 | 46 | ○ Pending |
| QC-RESEARCH-03: 주소, 운영시간, 요금, 코스, 교통편, 주변 시설 등을 구조화 | 46 | ○ Pending |
| QC-RESEARCH-04: 팩트시트 → drafting 프롬프트에 주입 | 46 | ○ Pending |
| QC-RESEARCH-05: derive 후, draft 전 리서치 실행 | 46 | ○ Pending |
| QC-RESEARCH-06: search_retriever.py 재사용 (기존 Naver API 인프라) | 46 | ○ Pending |
| QC-RESEARCH-07: pytest — 리서치 단계 테스트 | 46 | ○ Pending |

### Phase 6: 썸네일 검증 및 종합 스코어링 (Phase 47)

| Requirement | Phase | Status |
|-------------|-------|--------|
| QC-THUMB-01: thumbnail_checker.py — 썸네일 파일명/alt 텍스트가 키워드 포함 여부 | 47 | ○ Pending |
| QC-THUMB-02: 이미지 존재 확인 (빌드 후 404 검사) | 47 | ○ Pending |
| QC-SCORE-01: quality_scorer.py — 가중합 점수 산출 (계약40% + 사실성25% + 역할20% + 시각15%) | 47 | ○ Pending |
| QC-SCORE-02: 7.0미만 = 재생성, 9.0+ = 자동 승인 기준 | 47 | ○ Pending |
| QC-SCORE-03: 감점 사유 상세 리포트 (대시보드 + 수동 판단용) | 47 | ○ Pending |
| QC-SCORE-04: 기존 image 파이프라인과 통합 | 47 | ○ Pending |
| QC-SCORE-05: quality_gate.py에 스코어링 게이트 통합 | 47 | ○ Pending |
| QC-SCORE-06: pytest + e2e 검증 — 최소 1개 키워드로 9점 달성 확인 | 47 | ○ Pending |

## M3 Out of Scope

| Feature | Reason |
|---------|--------|
| 웹 검색 기반 자동 출처 교차 검증 | Phase 2-B에서 "출처 태그 유무"만 검사, 자동 교차 검증은 향후 확장 |
| LLM 기반 의미적 문장 유사도 | Phase 3에서 n-gram/SequenceMatcher로 충분, LLM 유사도는 비용 대비 효과 낮음 |
| 실시간 가격/예약 정보 수집 | 동적 데이터는 리서치 스텝에서 공식 사이트 링크로 안내 |

---

## Traceability

**Total:** 42 requirements (23 v1 + 11 v2/v3 + 8 Phase 14) — 41 validated, 1 deprecated, 0 unmapped
**M2:** 13 requirements (CLONE 5 + INFRA 4 + CFG 5 + VERIFY 3) — 0 mapped yet, 0 unmapped ✓
**M3:** 40 requirements (CONTRACT 5 + TITLE 6 + FACT 7 + XBLOG 6 + HTML 7 + RESEARCH 7 + THUMB/SCORE 7) — 0 validated, 0 unmapped ✓
