# Phase 26: 코드베이스 리팩토링 — Research

**Researched:** 2026-07-27  
**Domain:** MC codebase refactoring  
**Confidence:** HIGH  

## Summary

Phase 26 focuses on refactoring the MC codebase to eliminate duplication, reduce complexity, and improve article format quality and maintainability while preserving existing functionality. The phase is structured into three waves: Foundation, Component Simplification, and Advanced Optimizations.

## Background

The current codebase suffers from:
- Duplicate frontmatter handling functions (`_ensure_frontmatter`, `_ensure_frontmatter_closer`)
- Overly complex card injection logic (`chain_card_injector.py` at 695 lines)
- Scattered constants and hardcoded lists
- Duplicated configuration without validation

These issues increase maintenance overhead and regression risk.

## Scope

This phase targets three areas:

1. **Foundation** – Extract common utilities for frontmatter, URL handling, and constants into dedicated modules.
2. **Component Simplification** – Refactor the card injector into separate classes (`LinkFinder`, `CardGenerator`, `HtmlRenderer`) with a facade retaining the original interface.
3. **Advanced Optimizations** – Introduce a common image provider base class, centralized cache manager, JSON-Schema configuration validation, and refactor the markdown processing pipeline.

## Details

### Foundation
- Create `frontmatter_utils.py` with a unified `ensure_frontmatter(text, meta)` function.
- Replace all calls to `_ensure_frontmatter` and `_ensure_frontmatter_closer` in `chain_drafter.py` and `chain_publisher_core.py`.
- Create `url_utils.py` for domain extraction, normalization, and tracking parameter stripping.
- Replace ad-hoc URL logic in `chain_card_injector.py` and elsewhere with these utilities.
- Create `constants.py` to centralize `AUTHORITY_DOMAINS`, `SKIP_DOMAINS`, regex patterns, and other hardcoded values.
- Update imports across the codebase.

### Component Simplification (Card Injector)
- Design and implement `LinkFinder` class (exposes `find_links(text) -> list[dict]`).
- Implement `CardGenerator` (input: link dict, context: post meta → card spec).
- Implement `HtmlRenderer` (template strings for next/internal/official cards).
- Refactor `chain_card_injector.inject_*` to use these three components.
- Maintain a backward-compatible wrapper with a deprecation notice for existing callers.
- Add unit tests for each new class (target ≥90% coverage).
- Run integration tests with sample chains to verify card output remains identical.

### Advanced Optimizations
- Extract image provider base class in `image/base_provider.py` (fetch, validate interfaces).
- Move caching logic to `image/cache_manager.py` (LRU, TTL, shared dict).
- Refactor `search_providers.py` and `prompt_builder.py` to use the base class and cache.
- Define JSON-Schema in `config/schema.yaml` for `prompts.yaml` and `keyword_mapping.yaml`.
- Add validation hook at config load time (fail fast on malformed YAML).
- Refactor `chain_publisher_core.py`:
  - Create `MarkdownProcessor` class handling leak protection, symbol cleaning, table protection.
  - Separate frontmatter handling (delegate to `frontmatter_utils.ensure_frontmatter`).
  - Keep `_publish_hugo` focused on Hugo-specific frontmatter and image handling.
- Update `leak_defense.py` to import centralized constants if needed.
- Run full test suite and spot-check generated articles for visual fidelity.

## Dependencies

- **Upstream:** Phase 22 (quality gates), Phase 23 (auto-rewrite loop) – none directly block this phase.
- **Downstream:** Phase 27 and beyond will benefit from the cleaner codebase and improved testability.

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Import-time side effects in `chain_publisher_core` breaking import-only reuse | Low | High | Guard top-level code with `if __name__ == "__main__":` or move into functions. |
| Card injection behavior changes due to refactor | Medium | Medium | Property-based testing: generate random HTML inputs, compare pre/post output via snapshots. |
| Config schema too strict, rejecting valid YAML | Low | Medium | Start with permissive schema, add constraints iteratively; validate against all existing configs. |
| Performance regression from added indirection | Low | Low | Benchmark key paths (link finding, card generation) before/after; target ≤5% variance. |
| Missing edge-case in URL utility causing broken links | Low | High | Comprehensive unit tests for URL normalization (tracking params, fragments, scheme). |

## References

- Existing code: `chain_drafter.py`, `chain_card_injector.py`, `chain_publisher_core.py`, `image/` directory, `config/prompts.yaml`
- Refactoring patterns: "Extract Class", "Replace Conditional with Polymorphism", "Introduce Parameter Object", "Facade"
- GSD workflow: `gsd-plan-phase`, `gsd-plan-checker`

## Next Steps

1. Ensure the directory `.planning/phase-26` exists (already done).
2. This `RESEARCH.md` file is now complete.
3. Run `/gsd-plan-phase 26` to generate a draft `PLAN.md` (if needed) or proceed with execution.
4. Execute the plan via `/gsd-execute-phase --phase 26`.
5. Verify with `/gsd-plan-checker --phase 26`.
6. Upon successful verification, mark the phase as complete and proceed to the next phase.