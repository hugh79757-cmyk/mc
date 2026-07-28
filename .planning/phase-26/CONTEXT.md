# CONTEXT.md — Phase 26: 코드베이스 리팩터링

**Phase:** 26  
**Created:** 2026-07-27  
**Mode:** development  

## Objective

MC 코드베이스의 중복을 제거하고 복잡도를 낮추며, 기사 형식 품질과 유지보수성을 향상시키는 점진적인 리팩터링을 수행한다. 기존 기능은 완전히 보존하면서 코드 구조를 모듈화하고, 테스트 커버리지를 높이며, 향후 기능 확산을 용이하게 만든다.

## Background

현재 코드베이스는 다음과 같은 문제가 있다:
- 중복된 프론트매터 처리 함수(`_ensure_frontmatter`, `_ensure_frontmatter_closer`)
- 과도하게 복잡한 카드 주입 로직(`chain_card_injector.py` 695줄)
- 산재된 상수 및 하드코딩된 리스트
- 설정 파일의 중복 및 검증 부재
These issues increase maintenance overhead and risk of regressions.

## Dependencies

- phase-22

## Current State Summary

The codebase currently has duplicated frontmatter handling, complex card injection logic, scattered constants, and unvalidated configuration files.

## Scope

This phase targets three areas:
1. Foundation – common utilities (frontmatter, URL, constants) extraction and consolidation
2. Component Simplification – refactor card injection system into role-based classes and template-based HTML generation
3. Advanced Optimizations – improve pipeline architecture and introduce configuration validation mechanisms

Implementation will be done in a non-destructive, additive manner, preserving existing functionality and ensuring all existing tests (251) pass.
