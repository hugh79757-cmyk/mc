# Phase 29 — VERIFICATION.md

## Plan: 29-01 (format verification baseline)

### Verification Run: 2026-07-28

**Command:** `python audit/audit_format.py --dry-run --all` and `python audit/audit_format.py --all`

### Results Summary

| Check                    | Result | Details                                              |
| ------------------------ | ------ | ---------------------------------------------------- |
| 카드 주입 수             | ✅ 0건 | All posts within card count limits                   |
| 카드 위치                | ✅ 0건 | Cards placed correctly (mid after 2nd H2, bottom after last H2) |
| 크로스링크 URL           | ✅ 0건 | D0→issue.techpawz, D1→techpawz URLs correct         |
| H2 구조                  | ❌ 1건 | #488 step1 "Test Title" — H2 개수 불일치 (test post, expected) |
| 프론트매터 완성도        | ❌ 1건 | #488 step1 "Test Title" — 프론트매터 없음 (test post, expected) |
| Hugo HTML 렌더링         | ✅ 0건 | No raw markdown or CTA leaks in rendered HTML        |
| DB 일관성                | ✅ 0건 | All published posts consistent                       |
| 카드 타입                | ✅ 0건 | Correct card types per depth                         |
| 외부링크 패턴            | ✅ 0건 | External link cards match expected patterns          |
| chain-card shortcode     | ✅ 0건 | Shortcodes have required attributes                  |

**Total:** 8/10 checks pass, 2 failures (both from test post #488 — not production data)

### Unit Tests

```
39 passed in 0.09s
```

Tests cover: frontmatter parsing (7), card count (4), card placement (3), H2 extraction (3), cross-link URL (4), frontmatter completeness (6), card type (3), DB consistency (3), H2 structure (3), keyword template extraction (3).

### Notes

- The 2 failures originate from post #488 which appears to be a test/placeholder entry in the DB with no frontmatter and no H2 sections. This is expected and not a production issue.
- Hugo HTML rendering checks confirmed no raw markdown or injected CTA blocks in any rendered pages.
- The audit tool correctly identifies format issues that `audit_chain.py` does not cover.
