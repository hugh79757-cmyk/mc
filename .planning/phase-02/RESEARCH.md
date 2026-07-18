# Phase 2 Research — AI Content Generation

**Generated:** 2026-07-18
**Source:** User's manual diagnosis of current vs desired writing prompt

---

## Diagnosis Summary

### Current `config/prompts.yaml` draft section — gaps identified

| 항목 | 현재 prompts.yaml | 사용자 글쓰기 프롬프트 |
|------|------------------|----------------------|
| Frontmatter 형식 규칙 | ❌ 없음 | ✅ 상세 (title/tags/categories 한 줄 배열 등) |
| Hugo 빌드 오류 방지 규칙 | ❌ 없음 | ✅ 상세 (tags 하이픈 리스트 금지 등) |
| SEO 키워드 배치 우선순위 | ❌ 없음 | ✅ title 앞 30자, description 앞 80자 등 |
| 표(markdown table) 사용 | ❌ 없음 | ✅ 적극 사용 지시 |
| 이모티콘 금지 | ❌ 없음 | ✅ 명시 금지 |
| 볼드체 앞뒤 공백 규칙 | ❌ 없음 | ✅ 명시 |
| 인용 태그 금지 | ❌ 없음 | ✅ [citation:N] 절대 금지 |
| Output Checklist | ❌ 없음 | ✅ 20개 항목 |
| 결론 소제목 형식 | ❌ 없음 | ✅ "마무리 - XXX" 형식 지정 |
| 분량 | 1500-2000자 | ✅ (동일하게 유지 가능) |
| 체인 컨텍스트 주입 | ✅ 있음 | ❌ 없음 (mc 전용 추가 필요) |
| 이전 포스트 링크 형식 | ✅ 있음 | ❌ 없음 |
| 이미지 주석 | ✅ `<!-- image: xxx -->` | ❌ 없음 |
| 태그/카테고리 추천 | ✅ 있음 | frontmatter 규칙으로 대체 가능 |

### Conclusion
Current draft prompts need full replacement. Use the user's writing prompt as base, merge mc-specific elements (chain context, prev/next post links, image placeholders).

---

## Proposed Changes

### File 1: `config/prompts.yaml` — draft section replacement
- Keep `derive_system` / `derive_user` unchanged
- Replace `draft_system` / `draft_user` with user's writing prompt + mc chain context injection

### File 2: `chain_drafter.py` — NEW
- Extract `draft_post()` and `_build_chain_context()` from `chain_publisher.py`
- Use new `draft_system` / `draft_user` from prompts.yaml
- Save drafts to `output/drafts/{chain_id}/`
- Include operator review checkpoint

### File 3: `image/` package — 3 NEW files
- `image/__init__.py` — package marker
- `image/pollinations_client.py` — Pollinations Flux client (extracted from inline)
- `image/prompt_builder.py` — Korean → English image prompt via GPT
- `image/injector.py` — image URL injection into frontmatter + body

### File 4: `chain_publisher.py` — modify
- Remove inline `draft_post()`, `_build_chain_context()`, `generate_image()`
- Import from `chain_drafter` and `image.*`
- Add `--draft` CLI flag

---

## 5. Dependencies Verified

| Library | Status |
|---------|--------|
| `requests` | ✅ in requirements.txt |
| `python-slugify` | ✅ in requirements.txt |
| `pyyaml` | ✅ in requirements.txt |
| `openai` | ✅ in requirements.txt (via 5000 venv) |
| 5000 `.venv` Python | ✅ at `/Users/twinssn/Projects/5000/.venv/bin/python` |

## 6. Pollinations.ai API

- URL: `https://image.pollinations.ai/prompt/{encoded_prompt}.jpg?width={w}&height={h}&model=flux&nologo=true`
- Rate limit: ~1 req/15s (anonymous)
- Returns: Image binary (Content-Type: image/...)
- No API key required for Flux

## 7. Funnel Analysis — 방향별 체인 비교

### 핵심 통찰: 키워드 성격에 따라 체인 방향이 달라져야 함

츄니토리(여성 쇼핑몰) 사례 분석 결과:

| 기준 | Depth (깊이) | Swallow (역방향) | Lateral (횡방향) |
|------|-------------|-----------------|-----------------|
| 독자 연속성 | 중간 | **높음** | 낮음 |
| 수익화 강도 | 중간 | **높음** | 중간 |
| 주제 비약 위험 | 낮음 | **낮음** | 높음 |
| 검색 수요 | 낮음 | **높음** | 낮음 |

### 키워드 → 방향 매핑 규칙

| 키워드 성격 | 체인 방향 | Step 흐름 |
|------------|----------|----------|
| 쇼핑/소비/브랜드 | Swallow | 소비 → 절약/관리 → 금융/투자 |
| IT/기술/프로그래밍 | Depth | 기초 → 응용 → 심화/전문 |
| 여행/지역/맛집 | Lateral | 장소/정보 → 비교/비용 → 비즈니스/재테크 |
| 이슈/시사/트렌드 | Depth | 사건/개요 → 분석 → 전망 |
| 일반 (fallback) | Depth | 기본 정보 → 확장 → 심화 |

### 수익화 방향 (방향별)

- **Depth**: Step 3에서 전문가 컨설팅/강의/프리미엄 콘텐츠
- **Swallow**: Step 3에서 금융 상품/카드/적금 추천 (제휴 수익)
- **Lateral**: Step 3에서 마케팅 도구/B2B 서비스 광고

### 구현 영향

1. `chain_deriver.py`: `_classify_keyword()` 함수 추가 → 분류 결과에 따라 derive prompt 선택
2. `config/prompts.yaml`: derive_user를 direction별 3종으로 확장
3. `config/chain_config.yaml`: chain_type 필드 + direction_role 정의
4. `chain_db.py`: chain_type 컬럼 추가

---

## 8. Risk Items

1. **chain_db.py schema upgrade**: Must add `draft_md TEXT` and `slug TEXT` columns — existing test data may need migration
2. **mc_paths.py constants**: Must add `PROMPTS_PATH`, `CHAIN_CONFIG_PATH`, `MC_DB_PATH`, `DRAFTS_DIR` before chain_drafter.py can reference them
3. **chain_deriver.py post schema**: Currently stores `depth`, `title`, `target_keyword`, `key_points`, `image_prompt`, `image_keyword` — but user's new prompt references `domain`, `angle`, `step`, `depth_role`, `category_guess`. Must enrich derive output or map from existing fields.
4. **Python runtime**: Must use 5000's `.venv/bin/python` for `shared.ai_writer` imports
5. **Subagent reliability**: gsd-phase-researcher hung at 23min — need ~5min health check polling for background agents
