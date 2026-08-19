---
date: 2026-08-18
type: fix
status: resolved
---

# 5 Category Draft Prompts + Fuzzy Section Matching + DB Standardization

## What
- Added `draft_system_{category}` and `draft_user_{category}` for 5 new categories: product, customer_service, gov_finance, shopping_brand, golf_course
- Updated customer_service prompt with step-specific mandatory items (step1=contact+hours, step2=procedure, step3=FAQ)
- Added fuzzy H2 heading matching to `quality/contract_loader.py` for contract validation
- Updated `quality/cross_blog_checker.py` to use fuzzy matching
- Standardized 9 non-standard `category_guess` values in `data/mc_chains.db`

## Why
- 9-category system was partially implemented (4 READY + 5 new) — E2E testing showed prompt routing and content generation working correctly
- customer_service Step1 had 0/4 mandatory items because MANDATORY section was flat list with no step-specific instruction
- Contract validation required exact H2 heading matches, causing false failures when AI slightly paraphrased section names
- DB had non-standard category_guess values from older LLM free-classification (e.g., "패션/아웃도어 상품" instead of "shopping_brand")

## Files changed
- `config/prompts.yaml` — 5 new system+user prompt pairs, customer_service step-specific mandatory
- `chain_drafter.py` — prompt routing for new categories (already existed, verified)
- `quality/contract_loader.py` — `match_section()` with exact/contains/fuzzy matching, `_fuzzy_tokens()` for Korean particle stripping
- `quality/cross_blog_checker.py` — use `match_section()` for role element checks

## How
1. Added prompts following existing pattern (ABSOLUTE BAN, category-specific mandatory, ANTI-HALLUCINATION, sentence completion, length/tone/format rules)
2. customer_service MANDATORY section split: common items (contact+hours) for all steps, step-specific items (procedure for step2, FAQ for step3)
3. `match_section()` implements 4-tier matching: exact → contains → normalized contains → keyword overlap (Jaccard ≥ 0.5)
4. DB UPDATE with 3 SQL statements mapping non-standard → standard categories

## Verification
- pytest 124 passed (regression)
- E2E: "다이슨 에어랩" (product), "국민연금 수령나이" (gov_finance), "SK텔레콤 고객센터" (customer_service), "안나앤플러스" (shopping_brand), "포천힐스CC" (golf_course) — all 5 categories routed correctly, schema validated
- customer_service Step1 re-test after fix: 전화번호(114, 1599-0011) + 운영시간(평일 09:00~18:00, 24시간) confirmed
- E2E publish chain #24 (포천힐스CC): 3/3 posts published, thumbnail R2 upload, CTA injection, Hugo build, smoke test all passed
- DB: 0 non-standard category_guess values remaining
