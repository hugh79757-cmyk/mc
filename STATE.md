# STATE.md — mc (Manual Chain)

**Updated:** 2026-07-22
**Phase:** Phase 14 완료 ✅ — CLI 단일 진입점 `mc <keyword>` 전 Waves 완료
**Status:** ✅ W1~W4 머지 완료, Phase 14 전체 완료

## Current Baseline

| 항목 | 값 |
|------|-----|
| pytest | **165/165** ✅ (130 기존 + 35 W1-W3 테스트) |
| Phase 14 W4 | **완료** ✅ — `mc` 전역 명령 + 3/3 라이브 (Chain #71) |
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

## Recent Commits

```
e04281e feat(phase-14-w4): pyproject.toml console_scripts + frontmatter injection patch
5b740cc feat(phase-14-w3): _run_background() subprocess + flush handlers + 6 tests
c340271 docs(state): Phase 14 W2 완료 — pytest 159/159, _resume_chain 가동
3c0be3b feat(phase-14-w2): _resume_chain() DB state detection + 4 resume tests
eb1b24a feat(phase-14-w1): cli/mc.py argparse + _run_full() 파이프라인 래퍼 + 25개 테스트
```

## 인계 사항 (잔여 작업)

1. ~~**Phase 14 — CLI 단일 진입점 `mc <keyword>`**~~ ✅ 완료 (W1~W4 완)
2. **Phase 14.1 — cron/launchd 스케줄링, dashboard, audit 통합**: Phase 14 이후로 이월.
3. **고아 content_image_path 정리**: 37건 NULL content_image_path (이월 — 계속 미해결)
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
