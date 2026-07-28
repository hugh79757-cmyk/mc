---
phase: 29-format-verification
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - audit/audit_format.py
  - test_audit_format.py
autonomous: true
requirements:
  - CARD-01
  - CARD-02
  - CARD-03
  - CARD-04
  - CARD-05
  - PUB-01
  - CFG-01
  - DB-01

must_haves:
  truths:
    - "Published posts have featureimage set to a valid R2 URL in frontmatter"
    - "Each post has at most 2 cards (mid + bottom), correctly placed relative to H2 sections"
    - "Depth 0/1 card URLs point to the correct next-blog domain (rotcha→issue.techpawz, issue.techpawz→techpawz)"
    - "H2 titles in published posts match stepSections templates from prompts.yaml for the post's category"
    - "Hugo build completes without errors for all 3 sites"
    - "DB card_injected flag matches actual card presence in index.md"
  artifacts:
    - path: "audit/audit_format.py"
      provides: "10-format verification checks across 3 Hugo sites"
      min_lines: 300
      exports: ["check_thumbnail", "check_card_count", "check_card_placement", "check_cross_links", "check_h2_structure", "check_frontmatter", "check_hugo_build", "check_html_render", "check_live_access", "check_db_consistency"]
    - path: "test_audit_format.py"
      provides: "Unit tests for verification functions"
      min_lines: 100
  key_links:
    - from: "audit/audit_format.py"
      to: "chain_db.py"
      via: "get_conn() for chain_posts queries"
      pattern: "chain_posts.*published_url.*card_injected"
    - from: "audit/audit_format.py"
      to: "config/prompts.yaml"
      via: "yaml.safe_load() for stepSections"
      pattern: "step[123]_sections"
    - from: "audit/audit_format.py"
      to: "config/chain_config.yaml"
      via: "yaml.safe_load() for site paths and permalink patterns"
      pattern: "site_path|permalink_pattern"
---

<objective>
Create `audit/audit_format.py` — an automated verification script that checks the format/visual structure of published blog posts across 3 Hugo sites (rotcha.kr → issue.techpawz.com → techpawz.com).

Purpose: Complement the existing `audit/audit_chain.py` (which checks prompt leaks, whitelist, featureimage URL) with format-specific checks that `_verify_before_deploy()` does not cover: card injection count/placement, cross-link URL correctness, H2 structure matching stepSections, frontmatter completeness, Hugo HTML rendering, and DB consistency.

Output: `audit/audit_format.py` (verification script), `test_audit_format.py` (unit tests), baseline verification report from running against all published chains.
</objective>

<execution_context>
@/Users/twinssn/.config/opencode/get-shit-done/workflows/execute-plan.md
@/Users/twinssn/.config/opencode/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phase-29/CONTEXT.md
@.planning/phase-29/29-RESEARCH.md

<interfaces>
<!-- Key types and contracts the executor needs. Extracted from codebase. -->

From chain_db.py:
```python
def get_conn() -> sqlite3.Connection:
    """Return a new SQLite connection (row_factory = sqlite3.Row)."""

# chain_posts table columns used by audit:
# id, chain_id, depth, step, title, slug, category_guess,
# hugo_file_path, published_url, card_injected, card_injected_at,
# published_md, draft_md, status
```

From audit/audit_chain.py (style reference):
```python
DB_CANDIDATES = [
    PROJECT_ROOT / "data" / "mc_chains.db",
    Path("/Users/twinssn/Projects/5000/data/mc_chains.db"),
    Path.home() / "Projects" / "5000" / "data" / "mc_chains.db",
]
DB_PATH = next((p for p in DB_CANDIDATES if p.exists()), DB_CANDIDATES[0])

HUGO_SITES = {
    "rotcha": {"path": Path("/Users/twinssn/Projects/rotcha-blog"), "project": "rotcha-blog"},
    "issue.techpawz": {"path": Path("/Users/twinssn/Projects/issue-techpawz-hugo"), "project": "issue-techpawz-hugo"},
    "techpawz": {"path": Path("/Users/twinssn/Projects/techpawz-hugo"), "project": "techpawz-hugo"},
}

def _split_frontmatter(text: str) -> tuple:
    """(frontmatter, body) 분리. frontmatter가 없으면 ('', text)"""
```

From config/chain_config.yaml (site mapping):
```python
# chain_blogs maps depth → site key:
#   0 → rotcha, 1 → issue.techpawz, 2 → techpawz
# permalink patterns:
#   rotcha: /posts/:slug/
#   issue.techpawz: /:slug/
#   techpawz: /:slug/
# site_path for each:
#   rotcha: /Users/twinssn/Projects/rotcha-blog
#   issue.techpawz: /Users/twinssn/Projects/issue-techpawz-hugo
#   techpawz: /Users/twinssn/Projects/techpawz-hugo
```

From config/prompts.yaml (stepSections):
```python
# Each category has step1_sections, step2_sections, step3_sections
# Each section list contains H2 title templates like:
#   '## {keyword} — 위치와 기본 정보'
# medicine: 3 sections per step (not 4)
# All others: 4 sections per step
# Categories: travel, real_estate, automotive, stock, customer_service,
#             gov_finance, shopping_brand, golf_course, medicine, product, etc
```

Card injection patterns (from chain_card_injector.py D9 gate):
```python
# Shortcode cards (Depth 0/1):
#   {{< chain-card ... >}}
#   {{< chain-official-card ... >}}
# External link cards (Depth 2):
#   <div style="..."> with "관련 공식 사이트" or "바로가기 →"
#   <div style="..."> with "더 많은 정보"
```

Blog cross-link structure:
```python
# Depth 0 (rotcha) → card links to issue.techpawz.com
# Depth 1 (issue.techpawz) → card links to techpawz.com
# Depth 2 (techpawz) → external link card (no next blog)
# chain_blog_mapping default:
#   depth: [rotcha, issue.techpawz, techpawz]
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create audit/audit_format.py — main verification script</name>
  <files>audit/audit_format.py</files>
  <action>
Create `audit/audit_format.py` that implements 10 verification checks for published blog posts. Follow the exact style of `audit/audit_chain.py` (same DB path resolution, HUGO_SITES dict, argparse CLI, print_results format with ✓/✗).

**Script structure:**

```python
"""
audit/audit_format.py — 블로그 형식/외형 검증 (Phase 29)

10개 검증 항목을 자동화하여 발행된 블로그 포스트의 구조적/시각적 완결성을 확인한다.

검증 항목:
1. 썸네일(featureimage) — frontmatter에 R2 URL 존재
2. 카드 삽입 수 — 포스트당 최대 2개
3. 카드 배치 — mid=2nd H2 직후, bottom=마지막 H2 이후
4. 블로그 간 연결 — Depth 0→1→2 카드 URL 정확성
5. H2 구조 — stepSections 템플릿과 일치
6. frontmatter 완결성 — draft, slug, date, featureimage, images
7. Hugo 빌드 — 에러 없이 빌드 성공
8. HTML 렌더링 — og:image, 카드 HTML 렌더링
9. 라이브 접근 — HTTP 200 확인
10. DB 일관성 — card_injected 플래그 vs 실제 카드 존재

사용법:
  python audit/audit_format.py --dry-run                    # Hugo 빌드/라이브 스킵
  python audit/audit_format.py --site rotcha                # 특정 사이트만
  python audit/audit_format.py --chain-id 29               # 특정 체인만
  python audit/audit_format.py --all                        # 전체 검증
"""
```

**Check functions to implement:**

1. `check_thumbnail(fm_text, label)` — Parse frontmatter, verify `featureimage` field exists and starts with `http` (valid R2 URL). Return list of issues.

2. `check_card_count(body, label)` — Count card patterns in body: `{{< chain-card` shortcode + `<div style="...">` with "관련 공식 사이트" or "바로가기 →" or "더 많은 정보". Return issue if count > 2.

3. `check_card_placement(body, label)` — Extract H2 positions (`^## ` at char offset), count cards. If H2 >= 3: verify mid card is between h2_positions[1] and h2_positions[2]. Verify bottom card is after last H2 section. Return issues.

4. `check_cross_links(body, depth, label)` — For depth 0: card URLs must contain "issue.techpawz.com". For depth 1: card URLs must contain "techpawz.com". For depth 2: verify external link card exists (not chain-card shortcode). Return issues.

5. `check_h2_structure(body, category, step, label)` — Load prompts.yaml, get `step{step}_sections` for the category. Extract H2 titles from body with regex `^##\s+(.+)$`. Compare count matches (allow +/-1 for AI deviation). Return issues if mismatch > 1.

6. `check_frontmatter(fm_text, label)` — Verify all required fields present: `draft`, `slug`, `date`, `featureimage`, `images`. Parse YAML with `yaml.safe_load()`. Return issues for missing fields.

7. `check_hugo_build(site_name, site_path, skip=False)` — Run `hugo --gc --minify` with HUGO_THEMESDIR=/Users/twinssn/Projects/shared-themes, check exit code. Return issues.

8. `check_html_render(site_path, slug, label)` — After Hugo build, check `public/posts/{slug}/index.html` (rotcha) or `public/{slug}/index.html` (others) for `og:image` meta tag and card HTML rendering. Return issues.

9. `check_live_access(published_url, label)` — `curl -I {published_url}`, verify HTTP 200. Return issues.

10. `check_db_consistency(card_injected_flag, body, label)` — If card_injected=1, verify body contains card patterns. If card_injected=0, verify body does NOT contain card patterns. Return issues.

**Main flow:**

```python
def scan_posts(chain_id=None, site_filter=None, dry_run=False):
    # 1. Query DB for published posts (published_url IS NOT NULL)
    # 2. Read index.md from hugo_file_path
    # 3. Split frontmatter + body
    # 4. Get category from DB (category_guess)
    # 5. Get step from DB
    # 6. Run all 10 checks per post
    # 7. Hugo build + HTML render + live access (unless dry_run)
    # 8. Return aggregated results
```

**CLI arguments:**
- `--chain-id N`: Filter to specific chain
- `--site {rotcha|issue-techpawz|techpawz|all}`: Filter to site (default: all)
- `--dry-run`: Skip Hugo build, HTML render, and live access checks
- `--all`: All published chains (default if no chain-id)

**Output format** (follow audit_chain.py pattern):
```
=========================================================
  audit_format.py — Blog Format Verification
  (2026-07-28 14:30)
=========================================================

  Chain #29 — "키워드"

  ✓ Thumbnail (featureimage): PASS
  ✓ Card count (max 2): PASS
  ✗ Card placement: FAIL — mid card not between 2nd and 3rd H2
  ✓ Cross-links: PASS
  ...

  ═══════════════════════════════
   ✅ ALL PASS — 10/10 checks
  ═══════════════════════════════
```

**Critical implementation details from research:**

- DB path: use same `DB_CANDIDATES` pattern as `audit_chain.py`
- Hugo theme dir: `HUGO_THEMESDIR=/Users/twinssn/Projects/shared-themes`
- Card patterns: `{{< chain-card` (shortcode) AND `<div style="...">` with "관련 공식 사이트" or "바로가기 →" (external HTML)
- H2 count: medicine has 3 per step, all others have 4. Both trigger mid card (>=3)
- Hugo output paths differ: rotcha uses `/posts/:slug/`, others use `/:slug/`
- Frontmatter fields: draft, slug, date, featureimage, images, description
- `yaml` module is available (used in test_w3_cards_image.py)
- Add `sys.path.insert(0, str(PROJECT_ROOT))` for mc module imports (same pattern as audit_chain.py)
- For H2 structure check, extract category keyword from the H2 template by removing `{keyword}` placeholder and `##` prefix, then compare semantic structure (not exact text match since AI varies titles)
  </action>
  <verify>
    <automated>python -c "import audit.audit_format; print('import ok')" && python audit/audit_format.py --help</automated>
  </verify>
  <done>audit/audit_format.py exists, imports cleanly, --help displays 10 check descriptions, all 10 check functions are defined with correct signatures</done>
</task>

<task type="auto">
  <name>Task 2: Create test_audit_format.py — unit tests for verification functions</name>
  <files>test_audit_format.py</files>
  <action>
Create `test_audit_format.py` with unit tests for the core verification functions. Follow the style of `test_w3_cards_image.py` (class-based, pytest, direct function testing).

**Test classes and methods:**

```python
class TestFrontmatterParsing:
    """frontmatter 파싱 + 필수 필드 검증 테스트."""

    def test_split_frontmatter_with_valid_fm(self):
        """--- 로 감싸진 frontmatter 분리 확인."""

    def test_split_frontmatter_without_fm(self):
        """frontmatter 없을 때 전체를 body로 반환."""

    def test_check_frontmatter_all_fields_present(self):
        """draft, slug, date, featureimage, images 모두 있으면 통과."""

    def test_check_frontmatter_missing_featureimage(self):
        """featureimage 없으면 이슈 반환."""

    def test_check_frontmatter_missing_draft(self):
        """draft 없으면 이슈 반환."""

class TestCardCount:
    """카드 수 검증 테스트."""

    def test_count_zero_cards(self):
        """카드 없으면 0 반환."""

    def test_count_one_shortcode_card(self):
        """chain-card shortcode 1개."""

    def test_count_two_cards_mid_and_bottom(self):
        """chain-card shortcode 2개 (mid + bottom)."""

    def test_count_over_two_cards_fails(self):
        """카드 3개 이상이면 이슈 반환."""

    def test_count_external_link_card(self):
        """외부 링크 카드 (Depth 2 HTML) 카운트."""

class TestCardPlacement:
    """카드 배치 위치 검증 테스트."""

    def test_mid_card_between_2nd_and_3rd_h2(self):
        """mid 카드가 2번째 H2와 3번째 H2 사이에 위치."""

    def test_bottom_card_after_last_h2(self):
        """bottom 카드가 마지막 H2 이후에 위치."""

    def test_h2_less_than_3_no_mid_card(self):
        """H2 < 3이면 mid 카드 없음."""

class TestH2Extraction:
    """H2 제목 추출 테스트."""

    def test_extract_h2_from_body(self):
        """본문에서 ## 로 시작하는 H2 제목 추출."""

    def test_h2_count_matches_step_sections(self):
        """H2 수가 stepSections 템플릿 수와 일치."""

class TestCrossLinkValidation:
    """블로그 간 연결 URL 검증 테스트."""

    def test_depth0_links_to_issue_techpawz(self):
        """Depth 0 카드가 issue.techpawz.com을 가리킴."""

    def test_depth1_links_to_techpawz(self):
        """Depth 1 카드가 techpawz.com을 가리킴."""

    def test_depth2_has_external_card(self):
        """Depth 2는 외부 링크 카드 (chain-card 없음)."""
```

**Key test patterns:**
- Use `_split_frontmatter()` from `audit/audit_chain.py` or reimplement in `audit_format.py`
- Test card count with realistic markdown snippets including `{{< chain-card >}}` shortcodes
- Test placement with markdown that has `## H1\n...\n## H2\n...\n## H3\n...` structure
- Test cross-link with markdown containing `href="https://issue.techpawz.com/..."` or `href="https://techpawz.com/..."`
- Each test should be self-contained (no DB or file I/O)
  </action>
  <verify>
    <automated>python -m pytest test_audit_format.py -v 2>&1 | tail -30</automated>
  </verify>
  <done>All tests in test_audit_format.py pass (pytest exit 0), covering frontmatter parsing, card count, card placement, H2 extraction, and cross-link validation</done>
</task>

<task type="auto">
  <name>Task 3: Run full verification on existing published chains — baseline report</name>
  <files>.planning/phase-29/VERIFICATION.md</files>
  <action>
Run the complete verification against all existing published chains to establish a baseline.

**Steps:**
1. Run `python audit/audit_format.py --dry-run` (skips Hugo build + live access for speed)
2. Capture the full output
3. Run `python audit/audit_format.py --all` (full verification including Hugo build) — this may take a few minutes for Hugo builds
4. Create `.planning/phase-29/VERIFICATION.md` with:
   - Full script output from both runs
   - Summary of pass/fail counts per check type
   - List of any failures with specific post IDs and descriptions
   - Recommendations for follow-up fixes (if any failures found)

**VERIFICATION.md format:**
```markdown
# VERIFICATION.md — Phase 29: 블로그 형식/외형 검증

**Date:** 2026-07-28
**Script:** audit/audit_format.py

## Dry-Run Results (--dry-run)
[full output]

## Full Results (--all)
[full output]

## Summary
| Check | Pass | Fail | Notes |
|-------|------|------|-------|
| Thumbnail | X | Y | ... |
| ... | ... | ... | ... |

## Failures
[details of each failure]

## Recommendations
[follow-up actions needed]
```
  </action>
  <verify>
    <automated>test -f .planning/phase-29/VERIFICATION.md && echo "exists" || echo "missing"</automated>
  </verify>
  <done>VERIFICATION.md exists with dry-run + full results, summary table, and failure details</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| DB → Script | Script reads chain_posts table; no writes (read-only verification) |
| Filesystem → Script | Script reads index.md files; no writes to Hugo content |
| Network → Script | curl -I for live access check (HTTP HEAD only, read-only) |
| Hugo build → Script | Script runs `hugo --gc --minify` locally; output goes to public/ (read-only for verification) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-29-01 | Tampering | audit_format.py | accept | Read-only script, no production code modified |
| T-29-02 | Info Disclosure | DB queries | accept | Script runs locally, no external data transmission |
| T-29-03 | Elevation | Hugo build | accept | Local build only, no deploy; --dry-run flag available |
| T-29-SC | Tampering | Package installs | mitigate | No external packages installed; Python stdlib + yaml only |
</threat_model>

<verification>
- `python audit/audit_format.py --help` shows usage with all flags
- `python -m pytest test_audit_format.py -v` passes all tests
- `python audit/audit_format.py --dry-run` runs without errors against published chains
- `python audit/audit_format.py --all` completes Hugo builds and reports results
</verification>

<success_criteria>
- audit/audit_format.py implements all 10 verification checks
- test_audit_format.py has 15+ passing unit tests
- --dry-run flag works (skips Hugo build + live checks)
- --site and --chain-id filters work correctly
- Exit code 0 when all checks pass, exit code 1 when any fail
- VERIFICATION.md contains baseline results from existing published chains
</success_criteria>

<output>
Create `.planning/phases/29-format-verification/29-01-SUMMARY.md` when done
</output>
