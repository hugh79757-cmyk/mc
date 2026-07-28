---
phase: 28
plan: 01
subsystem: config
tags: [keyword-classification, product-category, lateral-chain]
dependency_graph:
  requires: []
  provides: [product-category-classification, product-lateral-prompt]
  affects: [mc_paths, chain_deriver, chain_drafter]
tech_stack:
  added: []
  patterns: [config-driven-category, priority-based-classification]
key_files:
  created: []
  modified:
    - config/prompts.yaml
    - config/chain_config.yaml
    - conftest.py
    - test_chain_deriver.py
decisions:
  - "D-28-01: Category name 'product' over 'electronics' — broader scope, covers future non-electronics products"
  - "D-28-02: priority=50 — between golf_course(10) and default(100) to avoid conflicts"
  - "D-28-03: Removed 삼성전자/LG전자 from product patterns to prevent customer_service conflict"
metrics:
  duration: ~5min
  completed: "2026-07-28T03:40:00Z"
  tasks_completed: 2
  files_modified: 4
---

# Phase 28 Plan 01: Product Category Addition Summary

Added `product` (전자기기/상품) keyword category to mc chain system so keywords like "갤럭시 폴드8 울트라 자급제" are classified as `product` instead of `etc`, using lateral chain direction with product-specific prompts and step sections.

## Verification Results

- [✅] classify_keyword("갤럭시 폴드8 울트라 자급제") == "product". 근거: pytest test_product_brand_keywords PASS, inline assertion PASS
- [✅] classify_keyword("아이폰 16 프로 가격") == "product". 근거: pytest test_product_brand_keywords PASS, inline assertion PASS
- [✅] classify_keyword("에어팟 프로 3세대") == "product". 근거: pytest test_product_brand_keywords PASS, inline assertion PASS
- [✅] resolve_chain_type("갤럭시 폴드8 울트라 자급제") == "lateral". 근거: pytest test_product_lateral_direction PASS, inline assertion PASS
- [✅] classify_keyword("맥북 프로 M4") == "product". 근거: pytest test_product_brand_keywords PASS, inline assertion PASS
- [✅] classify_keyword("PS5 가격") == "product". 근거: pytest test_product_category_keywords PASS, inline assertion PASS
- [✅] classify_keyword("닌텐도 스위치2") == "product". 근거: pytest test_product_category_keywords PASS, inline assertion PASS
- [✅] Regression: stock/golf_course/travel/medicine/gov_finance unchanged. 근거: pytest TestNewCategoryClassification PASS, inline assertions PASS
- [✅] Full pytest suite: 315 passed in 5.12s. 근거: pytest -v output

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed 삼성전자/LG전자 from product patterns**
- **Found during:** Task 2 verification (full pytest suite)
- **Issue:** Product pattern `(삼성전자|LG전자)` matched "삼성전자서비스 고객센터" before customer_service patterns, causing customer_service → product misclassification
- **Fix:** Removed `(삼성전자|LG전자)` from product patterns in prompts.yaml. These are company names, not product names. Brand-specific patterns (갤럭시, 아이폰, etc.) already cover product searches.
- **Files modified:** config/prompts.yaml
- **Commit:** 65fbd88

**2. [Rule 1 - Bug] Updated 3 pre-existing tests for expected behavior change**
- **Found during:** Task 2 verification
- **Issue:** `test_shopping_keyword_returns_etc`, `test_etc_maps_to_depth`, and `test_lateral_category_uses_correct_angle[아이폰 17-etc]` expected "etc" for iPhone keywords, but product category now correctly classifies them
- **Fix:** Updated test assertions and parametrize to reflect new expected behavior
- **Files modified:** test_chain_deriver.py
- **Commit:** 65fbd88

## Threat Flags

None — all patterns use simple alternation (no ReDoS risk), prompt follows existing template structure.

## Known Stubs

None — all config blocks fully populated with patterns, step sections, CTA phrases, and char counts.

## Residual Risks

- None identified. All 315 tests pass, all 11 inline assertions pass.

## Self-Check: PASSED

- Commits verified: 33accb9 (feat), 65fbd88 (test) — both in git log
- SUMMARY.md exists at .planning/phases/28-product/28-01-SUMMARY.md
- Files modified: config/prompts.yaml, config/chain_config.yaml, conftest.py, test_chain_deriver.py
