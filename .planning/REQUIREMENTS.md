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

## M3 Quality Gate Requirements

- QG-01: 각 블로그(rotcha/issue.techpawz/techpawz)별 산출물 계약이 YAML로 정의되어야 한다
- QG-02: contract_loader가 YAML을 로드하고 필수 필드 누락 시 GateResult.FAIL을 반환해야 한다
- QG-03: 제목의 핵심 약속 토픽이 본문 H2/H3 섹션에 구체적 정보와 함께 존재해야 한다
- QG-04: derive→draft 사이에 웹 리서치가 실행되어 factsheet.json이 생성되어야 한다 ✅ Phase 43-01
- QG-05: 본문의 수치·통계·후기 문장에 [출처: ...] 태그가 필수이며, 없으면 발행 차단 ✅ Phase 43-01 (inject_factsheet_to_prompt 구현, Phase 44에서 필터 게이트 구현)
- QG-06: 금지 표현("최저가", "100%", "검증된") 포함 시 발행 차단
- QG-07: 동일 chain 3편 간 문장 유사도 30% 이하
- QG-08: 블로그별 역할 필수 섹션 존재 (rotcha=가이드코스, issue=비교표, techpawz=체크리스트)
- QG-09: Hugo 빌드 HTML에서 title 태그와 본문 H1 중복 없음, CTA 2회 이상 반복 없음 ✅ Phase 46-01
- QG-10: 가중합 스코어(계약 40% + 사실성 25% + 역할 20% + 시각 15%) 자동 산출
- QG-11: 7.0 미만 재생성, 7.0~8.9 수동 검토 플래그, 9.0+ 자동 승인

## Traceability

**Total:** 42 requirements (23 v1 + 11 v2/v3 + 8 Phase 14) — 41 validated, 1 deprecated, 0 unmapped
**M2:** 13 requirements (CLONE 5 + INFRA 4 + CFG 5 + VERIFY 3) — 0 mapped yet, 0 unmapped ✓
**M3:** 11 requirements (QG-01~QG-11) — 3 validated (QG-04, QG-05, QG-09), 0 unmapped ✓
