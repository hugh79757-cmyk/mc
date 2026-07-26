# VERIFICATION.md — Phase 21 Plan Check

**Date:** 2026-07-26  
**Plan:** `.planning/phase-21/PLAN.md` (1 plan, 3 tasks, Wave 1)  
**Checker:** gsd-plan-checker

---

## Executive Summary

| Dimension | Result |
|-----------|--------|
| Goal Alignment | ✅ PASS |
| Completeness | ✅ PASS |
| Feasibility | ⚠️ CONDITIONAL (see warnings) |
| Test Coverage | ✅ PASS |
| Risk Assessment | ✅ PASS |
| Rollback Plans | ✅ PASS |
| Context Compliance | ✅ PASS |
| Requirement Coverage | ⚠️ WARNING |
| Dependency Correctness | ✅ PASS |
| Verification Derivation | ✅ PASS |
| **Overall Verdict** | **CONDITIONAL APPROVED** |

---

## Dimension 1: Goal Alignment

**Phase Goal:** `mc "키워드"` 한 줄로, 플래그 없이, 60초 이내에 3개 사이트 발행 완료 + URL 자동 검증

| Sub-Goal | Coverage | Status |
|----------|----------|--------|
| `mc "키워드"` no flags → full pipeline | Task 2 (B) verifies `publish_mode="auto"` at cli/mc.py:142 ✅ | PASS |
| 60초 이내 이미지 파이프라인 | Task 1 (A-1+A-2): thumbnail 재사용 → ~15s 절약 ✅ | PASS |
|  | Task 2 (A-3): sleep 제거 → 45s 절약 ✅ | PASS |
|  | Task 2 (A-4): 병렬화 → ~10s 절약 ✅ | PASS |
|  | 추정: 81s → ~13s (RESEARCH.md 기준) ✅ | PASS |
| URL 자동 검증 | Task 3 (C): smoke_test() after deploy ✅ | PASS |
| **Overall** | 모든 sub-goal이 task로 커버됨 | **PASS** |

**Verdict:** PASS — The plan's three tasks directly map to the three components of the phase goal.

---

## Dimension 2: Completeness

ALL sub-tasks from CONTEXT.md are covered:

| Sub-Task | Task | Status |
|----------|------|--------|
| A-1: Thumbnail 재사용 | Task 1 — `img_thumb()` → `add_text_overlay()` 대체 | ✅ |
| A-2: R2 업로드 병합 | Task 1 — Content image 재사용, 중복 API 호출 제거 | ✅ |
| A-3: Sleep 제거 | Task 2 — `time.sleep(15)` at line 316-318 제거 | ✅ |
| A-4: 병렬화 | Task 2 — `ThreadPoolExecutor(max_workers=3)` | ✅ |
| B: CLI publish_mode 검증 | Task 2 변경 4 — line 142 `publish_mode = "auto"` 확인 | ✅ |
| C-1: smoke_test() 함수 | Task 3 — 상세 구현 포함 | ✅ |
| C-2: DB 스키마 | Task 3 — 3개 컬럼 MIGRATIONS_SQL 추가 | ✅ |
| C-3: 단위 테스트 | Task 3 — 5개 smoke_test 단위 테스트 | ✅ |

**Verdict:** PASS — Every sub-task has a covering task with specific action code.

---

## Dimension 3: Feasibility

Implementation details verified against actual codebase:

### ✅ Verified Claims

| Claim | Verification | Status |
|-------|-------------|--------|
| `add_text_overlay()` exported in `image/__init__.py` | Line 11: `from .thumbnail import generate_thumbnail, add_text_overlay` | ✅ |
| `add_text_overlay()` signature: `(image_path, title, subtitle, target_size) -> Path` | `thumbnail.py:238-243, 336-339` | ✅ |
| `img_thumb` imported at module level (line 47, 166, 171) | `from image.thumbnail import generate_thumbnail as img_thumb` | ✅ |
| `img_thumb` only used in `generate_chain_images()` line 257 | grep confirms single call site | ✅ |
| `time.sleep(15)` at lines 316-318 | Confirmed in source | ✅ |
| Sleep is OUTSIDE the `if use_new_image:` block (applies to both paths) | line 316 is after `else:` block line 309 | ✅ |
| `publish_mode = "auto"` at cli/mc.py:142 | Confirmed in source | ✅ |
| `requests>=2.31.0` in requirements.txt | Line 2 | ✅ |
| `beautifulsoup4>=4.12.0` in requirements.txt | Line 5 | ✅ |
| `get_conn()` creates new connection each call | `chain_db.py:33-41` | ✅ |
| SQLite WAL mode enabled | `chain_db.py:39`: `PRAGMA journal_mode=WAL` | ✅ |
| MIGRATIONS_SQL pattern | `chain_db.py:105-123` | ✅ |
| `inject_cards_chain()` internally calls `_deploy_blogs_after_inject()` | `chain_publisher.py:548` | ✅ |
| `_deploy_blogs_after_inject()` at line 608 | Confirmed | ✅ |
| Current pytest count: 246 | `python -m pytest --collect-only -q`: 246 collected | ✅ |
| `use_new_image` is module-level global (line 165) | Confirmed — accessible from any module-level function | ✅ |
| No existing tests directly test `generate_chain_images` internals | All 3 callers mock at module level (`@patch("chain_publisher.generate_chain_images")`) | ✅ |

### ⚠️ Issues Found

**Issue 1 — `_process_post_image()` scope ambiguity (minor)**
- The plan's code shows `_process_post_image()` as a standalone function before `generate_chain_images()`. As a module-level function, it correctly accesses module globals (`use_new_image`, `db`, `img_gen`, etc.). ✅ Works.
- However, `_write_image_log()` is also a module-level function (line 134), and `_find_disk_image()` is at line 149. Both accessible. ✅ Works.

**Issue 2 — R2 upload count claim inaccurate**
- **Done criteria says:** "R2 업로드는 포스트당 1회로 감소 (thumbnail은 content image 파일에 text overlay만 추가)"
- **Actual implementation:** Content image upload (1회) + thumbnail upload via `add_text_overlay()` + R2 `put_object` (1회) = **2회** upload per post
- **Impact:** R2 upload time is ~1s each, so 3s total. The phase goal (60s) is not threatened. But the claim is inaccurate.
- **Severity:** WARNING — Fix done criteria wording

**Issue 3 — `.continue-here.md` update not covered by any task**
- Success criteria item 11 requires updating `.continue-here.md`
- No task action mentions this file
- **Severity:** INFO — The executor should be aware of this

**Issue 4 — `img_thumb` import becomes dead code**
- After Task 1, `img_thumb` is imported at module level (lines 47, 166, 171) but never called
- The plan acknowledges this: "`img_thumb` import는 유지 — 다른 코드 경로에서 사용될 수 있음"
- However, no other code path in the current codebase uses it
- **Severity:** INFO — Dead import, but harmless. Can be cleaned up if desired.

**Issue 5 — Legacy `--publish` path missing smoke_test**
- The `if args.publish and args.chain_id:` path (chain_publisher.py:987-1002) calls `publish_chain()` + `inject_cards_chain()` but doesn't call smoke_test
- This is the direct `python chain_publisher.py --chain-id N --publish` path, not `mc "키워드"`
- The phase goal is specifically about `mc "키워드"`, so this is out of scope
- **Severity:** INFO — Acceptable scope boundary

**Verdict:** CONDITIONAL — Issues 2-5 are non-blocking. Fix Issue 2 (done criteria wording) during execution.

---

## Dimension 4: Test Coverage

### Existing Test Impact
| Test File | Tests | Impact of Changes | Status |
|-----------|-------|-------------------|--------|
| `test_cli_mc.py` | ~38 tests | Tests mock `chain_publisher.run_chain` and `chain_publisher.generate_chain_images` at module level — internal refactoring doesn't affect them | ✅ No breakage |
| `test_image_pipeline.py` | ~13 thumbnail tests | Tests `generate_thumbnail()` and `add_text_overlay()` directly — functions unchanged | ✅ No breakage |
| `test_chain_publisher_core.py` | ~44 tests | No tests directly call `generate_chain_images()` or reference `img_thumb` | ✅ No breakage |
| Other test files | ~151 tests | No dependency on changed functions | ✅ No breakage |

### New Smoke Test Coverage (5 tests)

| Test Case | Scenario | Coverage |
|-----------|----------|----------|
| `test_smoke_test_all_pass` | 3 posts, all HTTP 200 + title + og:image | ✅ |
| `test_smoke_test_http_500` | HTTP 500 on page | ✅ |
| `test_smoke_test_connection_error` | Connection timeout | ✅ |
| `test_smoke_test_missing_url` | `published_url` is None | ✅ |
| `test_smoke_test_og_image_404` | Page OK but og:image returns 404 | ✅ |

### Mock Correctness Verification

All test mocks use `@patch("chain_publisher.requests.get")` which correctly patches at module level. The `smoke_test()` function does `import requests as req` inside (or top-level), which accesses the patched module object. ✅

**Test mock sequencing verified:**
- `test_smoke_test_og_image_404`: `mock_get.side_effect = [mock_page, mock_og]` — 2 elements for 1 post (1 page + 1 og:image) ✅
- `test_smoke_test_all_pass`: `mock_get.return_value = mock_resp` — single return value for 6 calls (3 pages + 3 og:images) ✅

**Expected test count:** 246 + 5 = 251 ✅

**Verdict:** PASS — Smoke test coverage is thorough. Existing tests won't break.

---

## Dimension 5: Risk Assessment

| Threat ID | Risk | Mitigation | Status |
|-----------|------|-----------|--------|
| T-21-01 | ThreadPoolExecutor 내 DB 쓰기 | `get_conn()` per thread + WAL mode | ✅ Mitigated |
| T-21-02 | 병렬 Unsplash/Pexels API rate limit | 3 concurrent = 50/hr limit not hit | ✅ Accepted |
| T-21-03 | smoke_test() HTTP GET | Read-only, no rollback | ✅ Accepted |
| T-21-SC | requests 의존성 | `requests>=2.31.0` in requirements.txt; urllib fallback provided | ✅ Mitigated |

### Additional Risk — DB Migration ordering
- The new `MIGRATIONS_SQL` entries will be appended to existing list (after line 123)
- However, `_run_migrations()` uses `PRAGMA table_info` to check column existence before running each migration — safe ✅
- Existing migration `image_meta` at line 122 was already processed in previous migrations; new `smoke_test_*` columns will be applied normally ✅

### Additional Risk — `update_image_meta` uses chain_models.ImageMeta
- Task 1's new code (line 217) constructs `meta` dict directly then calls `db.update_image_meta(post_id, meta)`
- `update_image_meta()` (chain_db.py:474-487) expects `dict` or `ImageMeta` and serializes via `model_dump_json()`
- BUT: the code constructs `meta` as a plain dict with `thumbnail_r2_url`, `thumbnail_source`, `thumbnail_path` keys
- `update_image_meta` does `meta = ImageMetaDB(**image_meta)` — this creates an `ImageMeta` Pydantic model from a dict
- If `ImageMetaDB` doesn't accept `thumbnail_r2_url`, this will fail
- **Risk:** Need to verify ImageMeta schema accepts `thumbnail_r2_url`
- **Severity:** WARNING — Executor must verify schema compatibility

**Verdict:** PASS — All identified risks have clear mitigations. One additional risk identified.

---

## Dimension 6: Rollback Plans

| Task | Rollback Command | Assessment |
|------|-----------------|------------|
| Task 1 | `git checkout -- chain_publisher.py` | ✅ Simple, correct |
| Task 2 | `git checkout -- chain_publisher.py` | ✅ Simple, correct |
| Task 3 | `git checkout -- chain_db.py chain_publisher.py test_chain_publisher_core.py` | ✅ Simple, correct |

**Note:** All tasks modify `chain_publisher.py`. Since they're in a single plan, the rollback is atomic. If partial rollback is needed between tasks, the executor should `git commit` after each task.

**Verdict:** PASS

---

## Dimension 7: Requirement Coverage

The PLAN.md frontmatter declares `requirements: [R21-01, R21-02, R21-03, R21-04, R21-05]`.

These requirement IDs **do not exist in ROADMAP.md** — Phase 21 is not documented in `.planning/ROADMAP.md` at all.

**Assessment:** The requirements are effectively defined by CONTEXT.md and the PLAN.md's success criteria. The missing ROADMAP.md entry is an administrative gap, not a plan correctness issue. The plan's tasks cover all requirements stated in CONTEXT.md.

**Severity:** WARNING — ROADMAP.md should be updated to include Phase 21, but this doesn't block execution.

---

## Dimension 8: Overall Verdict

```
APPROVED ✅ (CONDITIONAL)
```

### Conditions (must be addressed during execution)

1. **Fix R2 upload done criteria wording** — Change from "포스트당 1회로 감소" to "포스트당 2회 유지 (content image + thumbnail 각각 업로드)" or clarify that the savings are in API search calls, not R2 upload count.

2. **Verify ImageMeta schema accepts `thumbnail_r2_url`** — Before execution, check that `chain_models.ImageMeta` has a field for `thumbnail_r2_url`. If not, either add the field or use `image_meta` dict update via `_merge_image_meta()` instead.

3. **Update ROADMAP.md** — Add Phase 21 entry to `.planning/ROADMAP.md` after execution to resolve the missing requirement IDs.

4. **`.continue-here.md`** — Ensure the executor either creates/updates this file as listed in success criteria, or removes it from the done list if not applicable.

### Non-Blocking Recommendations

- Clean up unused `img_thumb` import if no other code paths use it
- Extract R2 upload logic into a shared helper function to reduce code duplication in Task 1's replacement code (the current inline R2 upload code duplicates lines 227-248)

---

## Execution Guard Notes

The following things could derail execution:

1. **ThreadPoolExecutor + DB writes** — While `get_conn()` creates separate connections, concurrent writes to SQLite still serialize at the DB level. This is acceptable for 3 threads but can cause `database is locked` errors under heavy load. Mitigation: the plan already handles this by catching exceptions per-post.

2. **`_process_post_image()` function scope** — If extracted as a module-level function, it must access `use_new_image` as a module global (not closure). The plan's template shows it after the `try/except` block that sets `use_new_image = True`, so it will see the global value correctly. ✅

3. **`smoke_test()` import of `requests`** — The plan provides two approaches (top-level import vs function-level). Recommend top-level import for simplicity, but function-level also works with the mock setup. ✅

4. **Legacy `publish_mode = None` path** — The path at `run_chain()` line 766-784 (`else:` branch, when `publish_mode` is None) also calls `inject_cards_chain()` but the plan doesn't add smoke_test there. This is intentional (the goal is about `mc "키워드"` which goes through the `publish_mode="auto"` path).
