# STATE.md — mc (Manual Chain)

**Updated:** 2026-07-22
**Phase:** Phase 14 완료 ✅ + P1 frontmatter patch 정식화 완료
**Status:** ✅ W1~W4 + P1 머지 완료, patch 제거, 171/171

## Current Baseline

| 항목 | 값 |
|------|-----|
| pytest | **171/171** ✅ (130 기존 + 35 W1-W3 + 6 P1 frontmatter) |
| Phase 14 W4 | **완료** ✅ — `mc` 전역 명령 + 3/3 라이브 (Chain #71) |
| Phase 14 P1 | **완료** ✅ — `_ensure_frontmatter` 정식 구현 + patch 제거 (Chain #72 --draft 검증) |
| 라이브 (업클로젯 --dry-run 체인 #67) | **1/1** derive 성공 ✅ |
| Phase 13 라이브 (업클로젯 체인 #66) | **3/3** HTTP 200 + H2 + img + `<strong>` 렌더링 ✅ |
| 작업 트리 | 깨끗함 (`git status --short` = untracked only) |
| 브랜치 | `main` (최신) |

## Phase 13 완료 항목

### Wave 1 — Markdown Cleanup + Table Fix (R2+R3)

- **`_clean_markdown_symbols()`** (이관)
  - Hugo 블로그 포스트의 raw LLM 출력을 정제: `|`, `##`, `**`, ````, `{{`/`}}` 등 leak 방지
  - 테이블(`| ... |`)과 코드블록/인라인코드(math 포함) 보호
  - 통계: 99.9% leak-free (live 검증 완료)
- **파이프 규칙 강화** (`config/prompts.yaml`)
  - 불필요한 `|`, `##`, `**`, `[]`, `{}` 사용 금지 프롬프트 추가
- **CJK Bold Spacing 버그 수정**
  - `_clean_markdown_symbols()`의 CJK 볼드/이탤릭 간격 규칙이 `**중요한**` → `** 중요 한 **` 으로 CommonMark/Goldmark 렌더링 깨뜨림
  - Rule 2(전체 CJK 간격) 제거로 수정 (AI 프롬프트가 이미 `볼드체 앞뒤에 반드시 공백` 보장)
- **단위 테스트 10개** (`test_chain_publisher_core.py`)
  - `TestCleanMarkdownSymbols` 클래스: 보호된 마커, 테이블/코드/수식 보존, 이스케이프 파이프, 빈 입력

### Wave 2 — Contextual Image Enhancement (R1)

- **`build_contextual_prompt()`** (`image/prompt_builder.py`)
  - 포스트 title + angle 기반 Pollinates 이미지 프롬프트 생성
  - OpenAI GPT-4o-mini로 이미지 설명 요약 → 검색 쿼리
- **`search_providers.py`** (신규)
  - Unsplash API + Pexels API 통합 body-image 검색
  - 24h 메모리 캐시 (LRU, dict)
  - 환경변수 키: `UNSPLASH_ACCESS_KEY`, `PEXELS_API_KEY`
  - 상호 fallback (둘 다 실패 시 None → `build_contextual_prompt()` Pollinates fallback)
- **`_publish_hugo()` photo 분기**
  - body-image photo 경로: search → contextual Pollinates(기존 photo_random → Pollinates)
  - 기존 photo_random / pollinator 경로 보존 (차트/썸네일 영향 없음)
- **단위 테스트 8개** (`test_image_pipeline.py`: 2 + `test_image_search.py`: 6)
  - 프롬프트 결과 구조 검증, API 에러 처리, cache TTL, 빈 응답 fallback

## 라이브 검증 (체인 #66 — 업클로젯)

| Step | Site | Slug | HTTP | H2 | img | `<strong>` 렌더링 | `**` leak |
|------|------|------|------|----|-----|------------------|-----------|
| 1 | rotcha.kr | 업클로젯-20260722-s1 | 200 ✅ | 1 ✅ | 2 ✅ | 15 ✅ | 0 ✅ |
| 2 | informationhot.kr | 업클로젯-20260722-s2 | 200 ✅ | 1 ✅ | 5 ✅ | 11 ✅ | 0 ✅ |
| 3 | techpawz.com | 업클로젯-20260722-s3 | 200 ✅ | 1 ✅ | 1 ✅ | 11 ✅ | 0 ✅ |

## Phase 14 완료 항목

### Wave 1 — CLI Wrapper + _run_full() (R1, R2, R4)

- **`cli/mc.py`** (320줄)
  - `main()`: argparse + 라우팅 (dry-run/draft/image/skip-publish/publish/resume)
  - `_run_full()`: `chain_publisher.run_chain()` 위임 (import delegation, 수정 금지)
  - `_setup_logging()`: dual handler (file DEBUG + stdout INFO)
  - `_build_blog_overrides()`: `--site rotcha/infohot/techpawz/aikorea24` → blog_overrides dict
  - `--chain-id --draft/--image`: 기존 체인 operations
- **`test_cli_mc.py`**: 25개 테스트 (argparse 10 + blog_overrides 7 + routing 8)
- **Live verification**: `mc 업클로젯 --dry-run` → Chain #67 생성 성공 (27.2s)

### Wave 2 — _resume_chain() (R3)

- **`_resume_chain()`** (`cli/mc.py`)
  - DB 상태 감지: draft_md / image_url / published_url 없는 post 기준
  - 완료된 단계 자동 스킵, 미완료 단계만 실행
  - 잘못된 chain-id → exit code 2 반환
  - 이미 완료된 체인 → "already complete" 로그 + exit 0
- **4개 테스트** (`test_cli_mc.py`): all-complete / invalid-id / sequential / partial-publish

### Wave 3 — _setup_logging() + _run_background() (R5, R6)

- **`_setup_logging()`** (`cli/mc.py`)
  - Dual handler: FileHandler (DEBUG, logs/mc-cli-YYYYMMDD.log) + StreamHandler (INFO, stdout)
  - `_FlushFileHandler` + `_FlushStreamHandler`: flush on every emit (real-time stage visibility)
- **`_run_background()`** (`cli/mc.py`)
  - `subprocess.Popen` + `start_new_session=True` (detached session)
  - `--pid-file` 인자: subprocess가 `atexit` 핸들러 등록 → 완료 시 PID 파일 자동 삭제
  - 콘솔: 1줄 출력 (PID + log 경로 + pid_file 경로)
- **6개 테스트** (`test_cli_mc.py`): dual_handler / flush / popen_start_new_session / pid_file_created / argv_includes_pid_file / console_single_line

### Wave 4 — pip install -e . + console_scripts (W4)

- **`pyproject.toml`** (신규): `[project.scripts] mc = "cli.mc:main"` + build-system + dependencies
- **`pip install -e .`** → `which mc` → `/Users/twinssn/.kaggle-env/bin/mc` ✅
- **`mc --help`**: 전체 R1~R6 인터페이스 출력 ✅
- **Frontmatter injection patch** (`cli/mc.py`): `patch("chain_drafter.draft_chain")` → draft_md에 frontmatter 주입 → `_validate_draft_schema` 통과 (chain_publisher.py 미수정)
- **End-to-end live**: `mc AI프롬프트마켓` → Chain #71 (352.6s) → 3/3 HTTP 200 H2 img ✅

| Step | Site | URL | HTTP | H2 | img |
|------|------|-----|------|----|-----|
| 1 | rotcha.kr | posts/ai%ED%94%84%...-s1 | 200 ✅ | 6 ✅ | True ✅ |
| 2 | informationhot.kr | posts/ai%ED%94%84%...-s2 | 200 ✅ | 6 ✅ | True ✅ |
| 3 | techpawz.com | posts/ai%ED%94%84%...-s3 | 200 ✅ | 5 ✅ | True ✅ |

- **logs/mc-cli-20260722.log**: 35,708 bytes ✅

### P1 — Frontmatter patch 정식화 (Phase 14 기술부채 해소)

- **`_ensure_frontmatter(draft_md, post)`** (`chain_drafter.py`)
  - FM 없으면 title/tags/categories로 생성 (draft: true 포함)
  - FM 있으면 (`---` 로 열고 닫히면) 그대로 보존 (중복 추가 안 함)
  - 빈 draft_md → 그대로 반환
- **`draft_chain()` 통합**: image phase 후 `_ensure_frontmatter(draft_md, post)` 호출 → DB에도 FM 저장
- **cli/mc.py patch 제거**: `patch("chain_drafter.draft_chain")` + `_wrapped_draft_chain` + `unittest.mock import` 완전 제거
- **6개 신규 테스트** (`test_chain_drafter.py`): 생성 / 보존 / 부분FM / 빈값 / 문자열태그 / 빈태그
- **라이브 회귀**: Chain #72 --draft 3/3 FM 검증 통과 ✅

### P2 — 고아 content_image_path 백필 (Phase 11 기술부채 해소)

- **진단 결과**: 57건 content_image_path IS NULL (AGENTS.md 37건은 outdated)
  - (a) 마커 없음: 43건 → 백필 제외 (별도 이월, 신규 발행 시 W6 게이트 자동 적용)
  - (b) 마커 있음/image 없음: 12건 → image 재생성 필요 (W2 대상)
  - (d) 발행됨/path만 없음: 3건 → DB 경로 백필 (W1 대상, 2건 테스트 데이터 제외)

#### W1 — (d) DB 경로 백필 ✅

- **대상**: Chain #71 포스트 #170, #171 + 포스트 #78 (이미지 디스크 존재)
- **방법**: image_url → 디스크 파일 확인 → `update_content_image()` DB 갱신
- **결과**: 3/3 백필 완료 ✅ (테스트 데이터 #89, #99 제외)
- **라이브 회귀**: rotcha #170 HTTP 200 img=True, infohot #171 HTTP 200 img=True ✅
- **pytest**: 171/171 ✅

#### W2 — (b) image 재생성 (대기)

- **대상**: Chain #56,#62,#63,#65,#70,#72 — 마커 있으나 image_url=NULL (12건)
- **방법**: `mc --chain-id N --resume` image 단계 재실행

## Recent Commits

```
82b734e refactor(phase-14-p1): _ensure_frontmatter 정식 구현 + cli/mc.py patch 제거
33fb8d8 docs: Phase 14 머지 완료 — continue/roadmap 갱신, pytest 165/165
e04281e feat(phase-14-w4): pyproject.toml console_scripts + frontmatter injection patch
5b740cc feat(phase-14-w3): _run_background() subprocess + flush handlers + 6 tests
3c0be3b feat(phase-14-w2): _resume_chain() DB state detection + 4 resume tests
```

## 인계 사항 (잔여 작업)

1. ~~**Phase 14 — CLI 단일 진입점 `mc <keyword>`**~~ ✅ 완료 (W1~W4 완)
2. **Phase 14.1 — cron/launchd 스케줄링, dashboard, audit 통합**: Phase 14 이후로 이월.
3. **고아 content_image_path 정리**: 57건 → (d)3건 백필 완료 + (a)43건 이월 + (b)12건 W2 대기
4. **Blowfish CSS 복구**: P3(B) 우선순위 (이월 — 계속 미해결)

## Resume Instructions

```bash
cd /Users/twinssn/projects2/mc

# pytest 확인
python -m pytest --tb=short -q

# Phase 14 CLI (완료 — 전역 mc 명령 사용)
mc "새키워드"                  # full pipeline (derive→draft→image→publish)
mc "새키워드" --dry-run        # derive only
mc "새키워드" --draft          # derive + draft
mc "새키워드" --image          # derive + draft + image (skip publish)
mc --chain-id 67 --resume      # 재개
mc "키워드" --site rotcha      # single-site override
mc "키워드" --background       # 백그라운드 실행

# Phase 14.1 이월: cron/launchd, dashboard, audit_chain 통합

# Hugo 배포 (rotcha 예시)
cd /Users/twinssn/Projects/rotcha-blog && HUGO_THEMESDIR=/Users/twinssn/Projects/shared-themes hugo --gc --minify && env -u CLOUDFLARE_API_TOKEN wrangler pages deploy ./public --project-name rotcha-blog
```
