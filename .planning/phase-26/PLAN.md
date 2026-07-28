---
phase: 26
plan: 01
type: executable
wave: 1-3
depends_on: [phase-22]
files_modified:
  - chain_drafter.py
  - chain_card_injector.py
  - chain_publisher_core.py
  - image/__init__.py
  - image/search_providers.py
  - image/prompt_builder.py
  - config/prompts.yaml
  - leak_defense.py
files_created:
  - frontmatter_utils.py
  - url_utils.py
  - constants.py
  - link_finder.py
  - card_generator.py
  - html_renderer.py
  - image/base_provider.py
  - image/cache_manager.py
  - config/schema.yaml
autonomous: false
requirements:
  - R-REF-01
  - R-REF-02
  - R-REF-03
  - R-REF-04
  - R-REF-05
---

# PLAN.md — Phase 26: 코드베이스 리팩토링

**Phase:** 26  
**Owner:** 리팩토링 담당 에이전트  
**Mode:** development  
**Status:** 🔲 Planning  

## Objective

MC 코드베이스의 중복을 제거하고 복잡도를 낮추며, 기사 형식 품질과 유지보수성을 향상시키는 점진적인 리팩터링을 수행한다. 기존 기능은 완전히 보존하면서 코드 구조를 모듈화하고, 테스트 커버리지를 높이며, 향후 기능 확장을 용이하게 만든다.

## Background

현재 코드베이스는 다음과 같은 문제가 있다:
- 중복된 프론트매터 처리 함수(`_ensure_frontmatter`, `_ensure_frontmatter_closer`)
- 과도하게 복잡한 카드 주입 로직(`chain_card_injector.py` 695줄)
- 산재된 상수 및 하드코딩된 리스트
- 설정 파일의 중복 및 검증 부재
These issues increase maintenance overhead and risk of regressions.

## Scope

이 단계에서는 다음 영역을 대상으로 리팩터링을 수행한다:
1. **Foundation** – 공통 유틸리티(프론트매터, URL, 상수) 추출 및 통합
2. **Component Simplification** – 카드 주입 시스템을 역할별 클래스로 분리 및 템플릿 기반 HTML 생성
3. **Advanced Optimizations** – 파이프라인 아키텍처 개선 및 구성 검증 메커니즘 도입

구현은 기존 기능을 변경하지 않는 비파괴적 방식으로 진행하며, 모든 기존 테스트(251개)가 통과해야 함.

## Design

### 1. Foundation
- `frontmatter_utils.py`: `ensure_frontmatter(text, meta)` 단일 함수 제공
- `url_utils.py`: URL 파싱, 도메인 추출, 정규화 함수 모음
- `constants.py`: `AUTHORITY_DOMAINS`, `SKIP_DOMAINS`, regex 패턴 등 중앙집중

### 2. Component Simplification (Card Injector)
- `LinkFinder`: URL 발견, 순위 매기기, 필터링 전담
- `CardGenerator`: 링크 데이터를 카드 사양(유형, 텍스트, 플래그)으로 변환
- `HtmlRenderer`: 사양을 HTML 쇼트코드로 변환 (템플릿 문자열 사용)
- 기존 `chain_card_injector.py`는 위 클래스들을 조합하는 얇은 facade로 유지

### 3. Advanced Optimizations
- `image/base_provider.py`: 이미지 공급자 공통 인터페이스
- `image/cache_manager.py`: LRU 캐시 중앙화 (TTL, 공유)
- `config/schema.yaml`: JSON-Schema 기반 YAML 검증 (프롬프트, 키워드 매핑 등)
- `chain_publisher_core.py`: 마크다운 처리 파이프라인을 별도 클래스로 분리, frontmatter 처리 명확히 분리

## Deliverables

| Item | Description |
|------|-------------|
| **New utility modules** | `frontmatter_utils.py`, `url_utils.py`, `constants.py` |
| **Card injector refactor** | `link_finder.py`, `card_generator.py`, `html_renderer.py`, refactored `chain_card_injector.py` |
| **Image provider refactor** | `image/base_provider.py`, `image/cache_manager.py` |
| **Configuration schema** | `config/schema.yaml` + 검증 로직 |
| **Updated core modules** | `chain_drafter.py`, `chain_publisher_core.py` (util 사용) |
| **Documentation** | 개요 및 마이그레이션 가이드 (README 스닛) |
| **Test coverage** | 신규/수정 로직에 대한 단위 테스트 추가 (기존 테스트 unaffected) |

## Work Plan (Wave‑Based)

### Wave 1 – Foundation (Low Risk, High Impact)
- [ ] Create `frontmatter_utils.py` with unified `ensure_frontmatter`
- [ ] Replace all calls to `_ensure_frontmatter` / `_ensure_frontmatter_closer` in `chain_drafter.py`, `chain_publisher_core.py`
- [ ] Create `url_utils.py` (parse domain, normalize, strip tracking params)
- [ ] Replace ad‑hoc URL logic in `chain_card_injector.py` and elsewhere with utilities
- [ ] Create `constants.py` and move `AUTHORITY_*`, `SKIP_*`, regex patterns
- [ ] Update imports across codebase
- [ ] Run full test suite to ensure no regression (target 251/251 pass)

### Wave 2 – Component Simplification (Medium Risk)
- [ ] Design and implement `LinkFinder` class (expose `find_links(text)` → list of dict)
- [ ] Implement `CardGenerator` (input: link dict, context: post meta) → card spec
- [ ] Implement `HtmlRenderer` (template strings for next/internal/official cards)
- [ ] Refactor `chain_card_injector.inject_*` to use the three components
- [ ] Keep backward‑compatible wrapper for existing callers (deprecation notice)
- [ ] Add unit tests for each new class (≥90% coverage)
- [ ] Run integration test with sample chains to verify card output identical

### Wave 3 – Advanced Optimizations (Higher Risk, Transformative)
- [ ] Extract image provider base class in `image/base_provider.py` (fetch, validate)
- [ ] Move caching logic to `image/cache_manager.py` (LRU, TTL, shared dict)
- [ ] Refactor `search_providers.py` and `prompt_builder.py` to use base + cache
- [ ] Define JSON‑Schema in `config/schema.yaml` for `prompts.yaml`, `keyword_mapping.yaml`
- [ ] Add validation hook at config load time (fail fast on malformed YAML)
- [ ] Refactor `chain_publisher_core.py`:
    * Create `MarkdownProcessor` class handling leak protection, symbol cleaning, table protection
    * Separate frontmatter handling (call `frontmatter_utils.ensure_frontmatter`)
    * Keep `_publish_hugo` focused on Hugo‑specific frontmatter/image handling
- [ ] Update `leak_defense.py` if needed to import centralized constants
- [ ] Run full test suite + spot‑check generated articles for visual fidelity

## Definition of Done (DoD)

- [ ] All new/updated modules have unit tests; overall test coverage ≥90% for touched files
- [ ] Existing test suite passes completely: `python -m pytest -q` → 251/251
- [ ] No functional regression: side‑by‑side comparison of article output (HTML) before/after refactor for a sample set of seeds shows identical content (ignoring whitespace)
- [ ] Public APIs of existing modules unchanged (backward‑compatible)
- [ ] New utility modules are import‑safe and have no side‑effects at import time
- [ ] Configuration schema validates all existing YAML files without error
- [ ] Documentation updated (inline docstrings + short migration guide)
- [ ] No introduction of new lint‑flake8 / mypy errors; existing violations unchanged

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Import‑time side effects in `chain_publisher_core` breaking import‑only reuse | Low | High | Verify all top‑level code is guarded behind `if __name__ == "__main__":` or moved into functions |
| Card injection behavior changes due to refactor | Medium | Medium | Property‑based testing: generate random HTML inputs, compare pre/post output via snapshot |
| Config schema too strict rejecting valid YAML | Low | Medium | Start with permissive schema, add constraints iteratively; validate against all existing configs |
| Performance regression from added indirection | Low | Low | Benchmark key paths (link finding, card generation) before/after; aim for ≤5% variance |
| Missing edge‑case in URL utility causing broken links | Low | High | Write comprehensive unit tests for URL normalization (tracking params, fragments, scheme) |

## References

- Existing code: `chain_drafter.py`, `chain_card_injector.py`, `chain_publisher_core.py`, `image/` directory, `config/prompts.yaml`
- Refactoring patterns: “Extract Class”, “Replace Conditional with Polymorphism”, “Introduce Parameter Object”, “Facade”
- GSD workflow: `gsd-plan-phase`, `gsd-plan-checker`

## Next Steps

1. Create the directory `.planning/phase-26` (already done).
2. Fill this `PLAN.md` (current file).
3. Run `/gsd-plan-phase 26` to kick off the planning researcher (if needed).
4. Execute the plan via `/gsd-execute-phase --phase 26`.
5. Verify with `/gsd-plan-checker --phase 26`.
6. Upon successful verification, mark phase as complete and proceed to next phase.

