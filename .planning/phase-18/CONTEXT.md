# CONTEXT.md — mc (Manual Chain) Phase 18: Codebase Refactoring

## Phase Overview
This phase focuses on refactoring the MC codebase to address technical debt, reduce redundancy, and improve maintainability while preserving all existing functionality.

## Key Objectives
1. Eliminate code duplication across modules
2. Simplify complex components (particularly card injection system)
3. Improve separation of concerns
4. Enhance maintainability without changing external behavior
5. Establish better foundations for future development

## Scope
- Frontmatter handling consolidation
- URL/utility extraction and centralization  
- Card injection system refactoring
- Prompt/template system optimization
- Configuration management improvements
- All changes must be backward compatible

## Success Criteria
- All existing tests pass (251/251)
- No functional changes in output or behavior
- Measurable reduction in code duplication
- Improved modularity and separation of concerns
- Documentation of new architecture patterns

## Constraints
- Must maintain full backward compatibility
- No changes to public APIs or CLI interface
- All existing functionality must be preserved
- Performance should not degrade
- Security properties must remain unchanged