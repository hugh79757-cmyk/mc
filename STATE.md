# STATE.md — mc (Manual Chain)

**Updated:** 2026-07-22
**Phase:** Phase 13 — 콘텐츠 고도화 (Wave 1 + Wave 2)
**Status:** ✅ 머지 완료

## Current Baseline

| 항목 | 값 |
|------|-----|
| pytest | **130/130** ✅ (112 기존 + 18 신규) |
| 라이브 (업클로젯 체인 #66) | **3/3** HTTP 200 + H2 + img + `<strong>` 렌더링 ✅ |
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

## Recent Commits

```
0b0a3a9 feat(phase-13): 콘텐츠 고도화 — markdown cleanup + contextual image + 130/130
72fb5ec plan(phase-13): 4건 수정 — GFM 표 확인, API cache/fallback, Wave 순서 전환, 120/120 목표
8374edc plan(phase-13): 콘텐츠 고도화 — image relevance + markdown cleanup + table fix
bfa8606 docs: W6 완료 STATE.md/ROADMAP.md/.continue-here.md 갱신
5b7267a fix(11-w6): chart fallback image_keyword auto-fill + prompt leak regex fix
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

# 체인 발행 (예시)
python chain_publisher.py --seed "새키워드"
python chain_publisher.py --chain-id <id> --draft
python chain_publisher.py --chain-id <id> --image
python chain_publisher.py --chain-id <id> --publish

# Next: Phase 14 CLI 구현
ls .planning/phase-14/PLAN.md

# 라이브 검증
curl -s -o /dev/null -w "%{http_code}" https://rotcha.kr/posts/<slug>/
curl -s -o /dev/null -w "%{http_code}" https://informationhot.kr/posts/<slug>/
curl -s -o /dev/null -w "%{http_code}" https://techpawz.com/<slug>/
```
