# State: mc (Manual Chain)

**Last updated:** 2026-08-18 (Phase 45 완료: cross_blog_checker 모듈)

## Project Reference

See: .planning/PROJECT.md

**Core value:** One random keyword → 3 interconnected blog posts on 3 different domains, each going deeper than the last, with images and cross-links — fully automated.
**Current focus:** **M2 — 정보가 3-블로그 체인 복제** (Phase 37 착수 대기). 기존 기능(Phase 1~36)은 유지, 신규 독립 레포 셋업.

## Phase Status

| Phase | Status | Progress |
|-------|--------|----------|
| 1 — Foundation & Config | ✅ Complete | config, DB, paths |
| 2 — AI Content Generation | ✅ Complete | drafter, image pipeline |
| 3 — Image, Publishing & CLI | ✅ Complete | Pollinations, publisher, card injector |
| 4 — Loop Chain Direction | ✅ Deprecated | Phase 6이 대체 |
| 5 — mde2 Architecture Rewrite | ✅ Complete | R2-first, Wrangler deploy |
| 6 — Loop Funnel | ✅ Complete | Hub + dual-CTA spokes |
| 7 — Search-Augmented Drafting | ✅ Complete | Naver API context |
| 8 — Chart Generation | ✅ Complete | pillow_chart.py + GPT recognition |
| 9 — Publish Quality Fix | ✅ Complete | 프롬프트 릭·이미지·썸네일 |
| 10 — Phase 9 Aftermath | ✅ Complete | 회귀 방지 + CSS/SRI |
| 11 — HTML 릭 + 광고 겹침 | ✅ Complete | 10 tasks, 5 waves |
| 12 — mc R2 업로더 분리 | ✅ Complete | R2 독립 모듈 |
| 13 — 콘텐츠 고도화 | ✅ Complete | markdown cleanup + contextual image |
| **14 — CLI `mc <keyword>`** | **✅ Complete** | **W1~W4 + P1 frontmatter + P2 backfill + R2 published_md + techpawz bucket** |
| **15 — informationhot → issue.techpawz 슬롯 교체** | **✅ Complete** | **Wave 0~4: config/code/prompts 교체 + pub ID 통일 + 검증** |
| **17 — CTA 시나리오 설계** | **✅ Complete** | **CTA-SCENARIO.md 작성, 대표님 검토 대기** |
| **20 — 검색 상시화 + GROUNDING 확장** | **✅ Complete** | **--search global default + STOCK & AUTOMOTIVE GROUNDING block** |
| **24 — YAML Frontmatter Structural Fix** | **✅ Complete** | **FM 분리: AI는 body만 생성, FM은 코드 조립. _ensure_frontmatter 91→23라인 단순화, _build_frontmatter/_extract_description 신규, _extract_body_from_raw FM 제거, 378 tests ✅** |
| **26 — 코드베이스 리팩토링** | **✅ Complete** | **W2: LinkFinder/CardGenerator/HtmlRenderer 신설 + CardInjector 퍼사드 위임(출력 바이트 동일성 유지), W3: BaseImageProvider/CacheManager 신설, W4: 이미지 제공자 적응 + JSON-Schema 검증 + MarkdownProcessor + 최종 검증. 754 tests ✅** |
| **27 — 카테고리별 Draft 품질 검증** | **✅ Complete** | **12 derive + 36 draft, H2 36/36, 릭 36/36, 글자수 이슈 문서화** |
| **28 — product 카테고리 추가** | **✅ Complete** | **product keyword category + lateral prompt + 315 tests** |
| **29 — 블로그 형식/외형 검증** | **✅ Complete** | **audit_format.py 10 checks + 39 tests + baseline 8/10** |
| **30 — audit_format.py gap closure** | **✅ Complete** | **3 new functions + 13 checks + 47 tests** |
| **Quick 20260801 — 표 렌더링 깨짐 수정** | **✅ Complete** | **3개 사이트 표 9건 수정 + markdown_processor.fix_tables 신설 + prompts.yaml 3줄 구조 지시. 762 tests ✅. .planning/quick/20260801-broken-table-render/SUMMARY.md** |
| **31 — 공공기관 라벨 제거 (공식 링크 동적 판정)** | **✅ Complete** | **_score_official()에서 AUTHORITY_GOVERNMENT 분기 + "공공기관" 하드코딩 제거. find_external_links() 2-pass→1-pass 단순화. 모든 도메인 동일 신호(키워드-도메인 일치, 제목 "공식", 순위)로 판정. 763 tests ✅** |
| **43 — 사전 리서치 (pre_researcher)** | **✅ Complete** | **quality/pre_researcher.py: Factsheet/Fact 데이터클래스 + NaverSearchClient 재사용 리서치 + graceful degradation + 프롬프트 주입. 16 신규 테스트. 966 tests ✅** |
| **44 — 사실성 검증 (factuality_checker)** | **✅ Complete** | **quality/factuality_checker.py: extract_claims(숫자/리뷰/통계 패턴) + check_forbidden + validate_factuality(점수 0.7 임계값). 21 신규 테스트. 1003 tests ✅** |
| **45 — 크로스 블로그 중복 검증** | **✅ Complete** | **quality/cross_blog_checker.py: 3-gram Jaccard 유사도 + 역할 필수 요소 검증. 16 신규 테스트. 1000 tests ✅** |
| **32 — 연도 오류 방지 시스템** | **✅ Complete** | **year_guard.py 유틸리티 + 3겹 방어 (입력단/생성단/출력단). 패턴 3종 + 사실날짜 보호. 22 단위 + 6 통합 = 28건 신규. 792 tests ✅** |
| **33 — JSON 메타데이터 잔류 근본 수정** | **✅ Complete (2026-08-02 승인)** | **parse_ai_output() 중괄호 깊이 카운팅 파싱 분리 + _extract_clean_body 블록 단위 2차 방어 + 배포 검증 실패 상세 로깅. 커밋 59ed4dd. 851 tests ✅** |
| **34 — AI 사고과정/프롬프트 릭 3겹 방어** | **✅ Complete (2026-08-02 승인)** | **C: raw_output 보존(DB+파일) + A: 프롬프트 메타대화 금지 + temperature 0.7 + B: 문단단위 leak_defense. 커밋 78a5e79. 851 tests ✅** |
| **35 — 실발행 재검증 + use_context 실측 + 카테고리 + 중간 CTA** | **🔄 In Progress** | **P0: #378/#405 실발행 재검증, P1: use_context 실측·카테고리, P2: 중간 CTA + 통합 테스트. 4 Waves. 시작 2026-08-02** |
| **M2 — 정보가 3-블로그 체인 복제** | **📋 등록됨 (Phase 37-40)** | **조사 완료(읽기 전용): DB/shared/R2 분리 지점 + 정보가 인프라 실측 + chain_config 교체 범위 확정. 대표 결정: shared=vendoring, 카드=체인만 파랑. Phase 37 착수 대기** |

## Current Metrics

- **pytest:** 1000/1000 ✅ (Phase 45: cross_blog_checker 16건 추가. 기존 8건 실패 무관)
- **카테고리:** 11종 (travel/real_estate/automotive/stock/customer_service/gov_finance/shopping_brand/golf_course/medicine/product/etc)
- **라이브:** 3/3 R2 200 ✅ (rotcha/infohot/techpawz)
- **`mc` 전역 명령:** ✅ `/Users/twinssn/.kaggle-env/bin/mc`
- **파서 안정성:** BOM/제로폭/코드펜스/텍스트 전후 대응 + 테스트 12건

## M2 (정보가 복제) 실측 요약

- **CF Pages 프로젝트 3개 존재 + 커스텀 도메인 바인딩 + HTTPS 3/3 200** ✅
  - informationhot-hugo → informationhot.kr (`Information HOT`)
  - kuta-hugo → kuta.informationhot.kr (`KUTALOG`)
  - 5-informationhot → 5.informationhot.kr (`TEAM65`)
- **AdSense**: 3사이트 모두 ca-pub-6677996696534146 (정보가 계열) 일치 ✅
- **미비 (셋업 필요)**: shortcode 3종 전부 부재 / 5.informationhot-hugo baseURL `example.org` 플레이스홀더 / ads.txt(kuta·5) 부재 / R2 매핑 키(informationhot·5) 부재
- **필수 분리 지점**: chain_config.yaml `db_path`(5000 공유) / mc_paths.py PATH_5000 / r2_uploader HUGO_R2_DOMAINS / git origin / `.env` 재생성

## Active Context

- GitHub repo: https://github.com/hugh79757-cmyk/mc
- Local path: /Users/twinssn/projects2/mc
- Runtime: opencode
- 5000 path: /Users/twinssn/Projects/5000
- Hugo paths: /Users/twinssn/Projects/{rotcha-blog, issue-techpawz-hugo, techpawz-hugo}
- **M2 대상 Hugo paths: /Users/twinssn/Projects/{informationhot-hugo, kuta-hugo, 5.informationhot-hugo}**
- Chain DB: /Users/twinssn/Projects/5000/data/mc_chains.db (M2에서 복제 레포 DB로 분리 예정)
- Shared themes: /Users/twinssn/Projects/shared-themes
- Branch: `feat/keyword-category-template`

## Next Action

1. **M2 Phase 37 착수** — 복제 레포 생성 + 필수 분리 (DB/.env/shared vendoring/R2 매핑) — `/gsd:plan-phase 37`
2. **운영 계속** — 카테고리 11종 체계 가동 중. 새 키워드 → `mc "키워드"` 실행
3. **Post #488 정리** — 테스트/플레이스홀더 포스트 삭제 시 10/10 checks 통과
4. **(P2) classify_priority 수정** — real_estate priority를 90으로 낮춰 도시명+부동산 키워드 정확 분류
5. **(P2) _parse_derivation 강화** — ``json\n[...]`` 패턴 지원 추가
6. **(P3) char_count config 조정** — step1: 2500~3500, step2/3: 2500~3500으로 범위 상향
7. **(P3) depth 방향 프롬프트 확인** — stock/real_estate의 lateral 프롬프트 사용이 의도된 것인지 확인
8. **(a) 40건 고아 이미지** — 재발행 전까지 이미지 없음
9. **Automotive 검색 개선** — search_retriever에 automotive-specific search template 필요
10. **(P3) pyproject include 정리** — 신규 루트 모듈(frontmatter_utils/url_utils/constants/link_finder/card_generator/html_renderer/markdown_processor)이 packages include 목록에 없음 (01-01~03-05 SUMMARY Residual Risk 동일 지적)

