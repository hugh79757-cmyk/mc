# STATE.md — mc (Manual Chain)

**Updated:** 2026-07-22
**Phase:** Phase 14 W1 완료 — CLI 단일 진입점 `mc <keyword>` (W2 구현 진행 중)
**Status:** 🚧 W1 머지 완료, W2 착수

## Current Baseline

| 항목 | 값 |
|------|-----|
| pytest | **155/155** ✅ (130 기존 + 25 W1 신규) |
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

### Wave 2 — _resume_chain() 구현 중 (R3)

- `cli/mc.py`에 `_resume_chain()` stub 존재 → NotImplementedError
- 목표: 실패 체인 재개 (draft→image→publish 상태 감지)

## Recent Commits

```
eb1b24a feat(phase-14-w1): cli/mc.py argparse + _run_full() 파이프라인 래퍼 + 25개 테스트
9e6c3e9 plan(phase-14): CLI 단일 진입점 mc <keyword> — 기획 완료 (CONTEXT.md + PLAN.md)
0b0a3a9 feat(phase-13): 콘텐츠 고도화 — markdown cleanup + contextual image + 130/130
72fb5ec plan(phase-13): 4건 수정 — GFM 표 확인, API cache/fallback, Wave 순서 전환
```

## 인계 사항 (잔여 작업)

1. **Phase 14 — CLI 단일 진입점 `mc <keyword>`**: PLAN.md만 존재, 구현 필요. (기획 완료)
2. **Phase 14.1 — cron/launchd 스케줄링, dashboard, audit 통합**: Phase 14 이후로 이월.
3. **고아 content_image_path 정리**: 37건 NULL content_image_path (이월 — 계속 미해결)
4. **Blowfish CSS 복구**: P3(B) 우선순위 (이월 — 계속 미해결)

## Resume Instructions

```bash
cd /Users/twinssn/projects2/mc

# pytest 확인
python -m pytest --tb=short -q

# Phase 14 CLI (새로운 방식 — W1 완료)
python cli/mc.py "새키워드"           # full pipeline
python cli/mc.py "새키워드" --dry-run  # derive only
python cli/mc.py "새키워드" --draft    # derive + draft
python cli/mc.py "새키워드" --image    # derive + draft + image (skip publish)
python cli/mc.py --chain-id 67 --resume  # 재개
python cli/mc.py "키워드" --site rotcha  # single-site override

# Phase 14 W2 구현 중: resume (cli/mc.py _resume_chain)
# Phase 14 W3: logging + background
# Phase 14 W4: pip install -e . + which mc

# Hugo 배포 (rotcha 예시)
cd /Users/twinssn/Projects/rotcha-blog && HUGO_THEMESDIR=/Users/twinssn/Projects/shared-themes hugo --gc --minify && env -u CLOUDFLARE_API_TOKEN wrangler pages deploy ./public --project-name rotcha-blog
```
