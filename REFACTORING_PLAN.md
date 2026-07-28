# MC (Manual Chain) Codebase Refactoring Plan

## Executive Summary

This refactoring plan addresses the core issues identified in the MC codebase:
1. Redundancy and code duplication
2. Overly complex functionality (especially card injection)
3. Article format quality concerns
4. Maintenance challenges due to tightly coupled components

The plan focuses on incremental, non-breaking changes that preserve existing functionality while improving code quality, maintainability, and performance.

## Key Issues Identified

### 1. Redundancy and Duplication
- Multiple frontmatter handling functions (`_ensure_frontmatter`, `_ensure_frontmatter_closer`)
- Similar HTML generation patterns across card types
- Duplicate leak detection logic migrating to centralized `leak_defense.py`

### 2. Complexity Hotspots
- `chain_card_injector.py` (695 lines) - overly complex card generation and injection logic
- `chain_drafter.py` - complex prompt handling and text processing
- `prompts.yaml` - excessively large configuration file with hardcoded templates

### 3. Article Format Quality
- Generally good protection against code leakage via `leak_defense.py`
- Some concerns with aggressive markdown processing in `_clean_markdown_symbols`
- Image handling appears robust with proper marker protection

### 4. Card Link Generation Complexity
- Over-engineered domain authority classification
- Complex HTML generation with inline styles
- Tight coupling between link discovery and card generation

## Refactoring Recommendations

### Phase 1: Foundation Improvements (Low Risk, High Impact)

#### 1.1 Consolidate Frontmatter Handling
**Files**: `chain_drafter.py`, `chain_publisher_core.py`
**Action**: 
- Create a single `frontmatter_utils.py` module with standardized functions
- Replace `_ensure_frontmatter` and `_ensure_frontmatter_closer` with unified interface
- Maintain backward compatibility during transition

#### 1.2 Extract URL Utilities
**Files**: `chain_card_injector.py` (and potentially others)
**Action**:
- Move URL parsing, domain extraction, and link normalization to `url_utils.py`
- Simplify `_classify_authority` function by delegating to utility functions

#### 1.3 Centralize Constants
**Files**: Multiple files with hardcoded lists
**Action**:
- Move domain lists (AUTHORITY_*, SKIP_*) to `constants.py`
- Move regex patterns to appropriate utility modules
- Reduce magic strings scattered throughout codebase

### Phase 2: Component Simplification (Medium Risk, High Impact)

#### 2.1 Simplify Card Injection System
**Files**: `chain_card_injector.py` (primary target)
**Goals**:
- Reduce from 695 lines to <300 lines
- Separate concerns: link discovery vs card generation vs HTML generation
- Replace complex HTML generation with template-based approach
- Simplify domain authority classification

**Specific Changes**:
- Split `CardInjector` into:
  - `LinkFinder`: Responsible only for finding and ranking links
  - `CardGenerator`: Responsible only for creating card data structures
  - `HtmlRenderer`: Responsible only for converting cards to HTML
- Create base card templates to eliminate duplication
- Move complex domain logic to separate classifier module

#### 2.2 Streamline Prompt and Template System
**Files**: `config/prompts.yaml`, `chain_drafter.py`
**Goals**:
- Reduce `prompts.yaml` size by 50%+ through template inheritance
- Implement dynamic template generation instead of exhaustive enumeration
- Create template helper functions for common patterns

### Phase 3: Advanced Optimizations (Higher Risk, Transformative Impact)

#### 3.1 Pipeline Architecture Improvements
**Files**: Main orchestration files (`chain_publisher.py`, phase-specific files)
**Goals**:
- Decouple stages further to enable better testing and replacement
- Introduce clear interfaces between components
- Add pipeline metrics and monitoring capabilities

#### 3.2 Configuration Refactoring
**Files**: All YAML configuration files
**Goals**:
- Implement configuration validation
- Create schema definitions for all config files
- Add support for environment-specific overrides
- Implement hot-reload capability for development

## Detailed File-by-File Recommendations

### chain_drafter.py
**Current Issues**: 
- Complex prompt handling logic
- Multiple frontmatter-related functions
- Aggressive text processing that may remove valid content

**Recommendations**:
1. Extract frontmatter handling to shared utility
2. Simplify prompt template selection logic
3. Review `_count_visible_chars` and `_validate_draft_schema` for over-aggressive filtering
4. Consider extracting image/chart metadata handling to separate class

### chain_card_injector.py (Primary Target)
**Current Issues**:
- 695 lines of complex, intertwined logic
- HTML generation embedded with business logic
- Complex domain classification with hardcoded lists
- Tight coupling between link discovery and card generation

**Recommendations**:
1. **Extract LinkFinder class**:
   - Handle only URL discovery, ranking, and filtering
   - Move domain authority classification to separate module
   - Return structured data (URL, title, type, confidence)

2. **Extract CardGenerator class**:
   - Convert link data to card specifications
   - Handle card type determination (next vs external vs official)
   - Generate platform-agnostic card data

3. **Extract HtmlRenderer class**:
   - Convert card specifications to target format (HTML shortcodes)
   - Use template strings instead of string concatenation
   - Centralize CSS/styles in external files or constants

4. **Simplify public interface**:
   - Reduce number of parameters to injection methods
   - Create configuration objects for common parameter groups

### chain_publisher_core.py
**Current Issues**:
- Complex markdown processing pipeline
- Mixed concerns in `_publish_hugo` method
- Some duplicated frontmatter handling

**Recommendations**:
1. Extract markdown processing pipeline to separate class
2. Clearly separate frontmatter handling from body processing
3. Consider extracting image handling to dedicated service
4. Review `_clean_markdown_symbols` for potential over-processing

### image/ directory
**Current Issues**:
- Multiple provider implementations with similar interfaces
- Cache management scattered across files

**Recommendations**:
1. Create common base class for image providers
2. Extract cache management to separate module
3. Standardize error handling and retry logic

### config/ directory
**Current Issues**:
- Large, complex YAML files with duplication
- No schema validation
- Hardcoded values that should be configurable

**Recommendations**:
1. Implement JSON schema validation for all YAML configs
2. Break `prompts.yaml` into smaller, composable templates
3. Create base templates with override mechanism
4. Move constants to dedicated constants module

## Risk Assessment and Mitigation

### High Risk Changes
- **Card injector refactoring**: High complexity, tight coupling to publishing flow
  - *Mitigation*: Implement behind feature flag, maintain backward compatibility layer
  - *Testing*: Comprehensive unit tests + integration tests with real chains

### Medium Risk Changes
- **Frontmatter consolidation**: Widely used across multiple modules
  - *Mitigation*: Create adapter layer, update all callers incrementally
  - *Testing*: Property-based testing for round-trip compatibility

### Low Risk Changes
- **Utility extraction**: Isolated functions with clear interfaces
  - *Mitigation*: Standard extract/refactor approach with unit tests
  - *Testing*: Existing unit tests should pass with minimal modification

## Implementation Roadmap

### Sprint 1: Foundation (2 weeks)
- [ ] Create utility modules (frontmatter, URL, constants)
- [ ] Update all files to use new utilities (backend compatibility layer)
- [ ] Add comprehensive unit tests for new utilities
- [ ] Verify no functional changes through regression testing

### Sprint 2: Card System Refactor (3 weeks)
- [ ] Implement LinkFinder, CardGenerator, HtmlRenderer classes
- [ ] Create template system for HTML generation
- [ ] Migrate chain_card_injector.py to use new architecture
- [ ] Maintain backward compatibility wrapper
- [ ] Performance benchmarking

### Sprint 3: Prompt and Config Optimization (2 weeks)
- [ ] Analyze and refactor prompts.yaml for template reuse
- [ ] Implement configuration validation
- [ ] Update prompt generation logic in chain_drafter.py
- [ ] A/B test output quality

### Sprint 4: Quality Assurance and Performance (1 week)
- [ ] Load testing with realistic workloads
- [ ] Security review of changes
- [ ] Documentation updates
- [ ] Final regression testing suite

## Success Metrics

### Code Quality
- Reduce overall lines of code by 20-30%
- Increase test coverage to >90% for modified modules
- Reduce cyclomatic complexity of complex functions by 40%

### Performance
- Maintain or improve end-to-end pipeline performance
- Reduce memory footprint through better object reuse
- Faster startup time through lazy initialization where appropriate

### Maintainability
- Clear separation of concerns
- Reduced coupling between modules
- Improved onboarding documentation
- Consistent coding standards across codebase

### Functional Equivalence
- Zero regression in output quality
- Identical article generation results (given same seed)
- Preserved card injection behavior and positioning
- Maintained image handling and R2 upload fidelity

## Conclusion

This refactoring plan transforms the MC codebase from a monolithic, tightly-coupled system into a modular, maintainable architecture while preserving all existing functionality. By addressing the root causes of complexity and duplication, we create a foundation for faster feature development, easier bug fixing, and improved system reliability.

The incremental approach minimizes risk while delivering continuous value, allowing the team to validate improvements at each step before proceeding to more ambitious changes with more complex refactorings.