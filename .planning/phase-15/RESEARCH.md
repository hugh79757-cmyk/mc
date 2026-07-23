# RESEARCH.md — Phase 15

**Researcher:** BYD (project context synthesis)  
**Date:** 2026-07-23  
**Phase:** 15 — replace `informationhot` with `issue.techpawz`  

## Executive Summary

The requested change is a full blog-slot migration, not a simple rename. It touches site structure, config, prompts, publisher code, AdSense IDs, and potentially live published content. Current known blockers/research items are captured in Wave-0 items; the rest are execution assumptions pending Wave-1 confirmation.

## Current Architecture Snapshot

- Three Hugo sites: rotcha, informationhot-hugo, techpawz-hugo
- Chain publishing routes posts by blog slot definitions in `config/chain_config.yaml`
- Card injection references site slots and base URLs
- AdSense partials are embedded in site layouts/partials; rotcha and techpawz appear to share one publisher family, informationhot another

## Risks / Questions Requiring Answers

1. Does `/Users/twinssn/Projects/issue.techpawz-hugo` already exist?
2. Should `issue.techpawz-hugo` reuse the existing techpawz R2 bucket or get its own?
3. Should `issue.techpawz-hugo` be a new Cloudflare Pages project, or a route/path rewrite on an existing project?
4. What is the exact target AdSense publisher ID for techpawz-family sites after unification?
5. Do we migrate existing `informationhot` published URLs, or treat this as a fresh slot?

## Suggested Execution Order

- Capture current state before edits (Wave-0)
- Build/verify destination site (Wave-1)
- Swap code/config references on a feature branch (Wave-2)
- Audit and align AdSense IDs (Wave-3)
- Verify pytest + Hugo builds + dry-run slot routing; commit (Wave-4)

## Notes

- Do not deploy until Phase 15 verification passes.
- If `issue.techpawz-hugo` is not a clone of `techpawz-hugo`, clone minimum viable config first.
