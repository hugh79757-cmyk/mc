# CONTEXT.md — Phase 15

**Phase:** 15  
**Created:** 2026-07-23  
**Milestone:** Site transition  
**Mode:** research-first → planning  

## Objective

Replace the `informationhot` blog slot with `issue.techpawz` across the chain system. This is not a config-only change; it couples blog replacement, AdSense account unification, and chain logic updates.

## Scope

- Blog slot swap: `informationhot` → `issue.techpawz`
- Hugo site: `issue.techpawz-hugo` preparation or creation
- AdSense Publisher ID verification/unification
- Code references cleanup in chain/config/prompts/DB
- Final build + dry-run verification

## Constraints

- Do not modify unrelated generation logic.
- Preserve existing test count: maintain current pytest suite pass rate.
- Do not deploy to Cloudflare Pages until explicit post-commit approval.

## Inputs

- ROADMAP.md current milestone/phase registry
- STATE.md current baseline
- `.continue-here.md` handoff notes
- Phase 14 completed work registry

## Next Steps

- Wave-0: Capture current state snapshot
- Wave-1: Prepare/Create `issue.techpawz-hugo`
- Wave-2: Replace chain code references
- Wave-3: Unify AdSense Publisher ID
- Wave-4: Final verification and commit
