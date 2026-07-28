---
phase: 30-audit-gap-closure
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - audit/audit_format.py
  - test_audit_format.py
autonomous: true
requirements:
  - GAP-01
  - GAP-02
  - GAP-03
gap_closure: true
---

<objective>
Add 3 missing verification functions to `audit/audit_format.py` to close the gaps identified in Phase 29's self-audit. The existing 10 functions remain unchanged (additive only). After this phase, `audit/audit_format.py` covers all 10 checks promised in the original Phase 29 plan.
</objective>

<execution_context>
@/Users/twinssn/.config/opencode/get-shit-done/workflows/execute-plan.md
@/Users/twinssn/.config/opencode/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phase-30/CONTEXT.md
@.planning/phase-29/VERIFICATION.md
@.planning/phase-29/PLAN.md

<interfaces>
<!-- Existing functions in audit/audit_format.py that must NOT be changed -->

```python
# Existing 10 check functions ( signatures preserved ):
check_card_count(body, depth, label) -> list
check_card_placement(body, depth, label) -> list
check_cross_link_url(body, depth, label) -> list
check_h2_structure(body, category, step, label) -> list
check_frontmatter(body, label) -> list
check_hugo_html_rendering(slug, site_name, label) -> list  # only checks raw markdown
check_db_consistency(posts, label_prefix) -> list
check_card_type(body, depth, label) -> list
check_external_link_pattern(body, depth, label) -> list
check_chain_card_shortcode(body, depth, label) -> list

# Existing scan functions:
scan_chain_format(chain_id, dry_run) -> dict
scan_all_format(dry_run) -> dict
```

From audit_chain.py (reference for Hugo build pattern):
```python
def check_hugo_build(skip: bool = False) -> list:
    hugo_bin = shutil.which("hugo") or "/opt/homebrew/bin/hugo"
    for name, site in HUGO_SITES.items():
        build = subprocess.run(
            [hugo_bin, "--gc", "--minify"],
            cwd=str(site["path"]),
            capture_output=True, text=True, timeout=120,
        )
        # returncode != 0 → fail, warnings → warn
```

HUGO_SITES already defined in audit_format.py:
```python
HUGO_SITES = {
    "rotcha": {"path": Path("/Users/twinssn/Projects/rotcha-blog"), "output_prefix": "posts/"},
    "issue.techpawz": {"path": Path("/Users/twinssn/Projects/issue-techpawz-hugo"), "output_prefix": ""},
    "techpawz": {"path": Path("/Users/twinssn/Projects/techpawz-hugo"), "output_prefix": ""},
}
```

Hugo build requires: `HUGO_THEMESDIR=/Users/twinssn/Projects/shared-themes`

chain_posts DB columns used:
- published_url, status, hugo_file_path, card_injected, card_injected_at, slug, depth, step, title, category_guess
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add 3 missing check functions to audit/audit_format.py</name>
  <files>audit/audit_format.py</files>
  <action>
Add 3 new functions to `audit/audit_format.py`. Do NOT modify any existing functions. Additive only.

**Function 1: `check_hugo_build(site_name=None, skip=False)`**

Run Hugo build on specified site(s) and check for errors. Pattern from `audit_chain.py` `check_hugo_build()`.

```python
def check_hugo_build(site_name: str = None, skip: bool = False) -> list:
    """Hugo 빌드 검증 — 에러/경고 출력. site_name=None이면 전체 사이트."""
    findings = []
    if skip:
        return findings

    hugo_bin = shutil.which("hugo") or "/opt/homebrew/bin/hugo"
    if not Path(hugo_bin).exists():
        return [{"check": "hugo_build", "detail": f"hugo 실행 파일 없음: {hugo_bin}"}]

    env = os.environ.copy()
    env["HUGO_THEMESDIR"] = "/Users/twinssn/Projects/shared-themes"

    sites = {site_name: HUGO_SITES[site_name]} if site_name else HUGO_SITES
    for name, site in sites.items():
        try:
            build = subprocess.run(
                [hugo_bin, "--gc", "--minify"],
                cwd=str(site["path"]),
                capture_output=True, text=True, timeout=120, env=env,
            )
            if build.returncode != 0:
                errors = [l for l in build.stderr.splitlines() if "ERROR" in l][:5]
                findings.append({
                    "check": "hugo_build",
                    "detail": f"{name}: 빌드 실패 (exit {build.returncode})",
                    "errors": errors or [build.stderr[:200]],
                })
            else:
                warnings = [l.strip() for l in build.stderr.splitlines()
                           if "WARN" in l][:3]
                if warnings:
                    findings.append({
                        "check": "hugo_build",
                        "detail": f"{name}: 빌드 성공, 경고 {len(warnings)}건",
                        "warnings": warnings,
                    })
        except subprocess.TimeoutExpired:
            findings.append({
                "check": "hugo_build",
                "detail": f"{name}: 빌드 타임아웃 (120초)",
            })
    return findings
```

Key details:
- `import os` at top of file (if not already present)
- Uses `HUGO_THEMESDIR` env var for theme resolution
- Returns findings with check="hugo_build" for consistent output format
- `site_name` parameter allows checking a single site or all 3
- `skip` parameter aligns with `--dry-run` behavior

**Function 2: `check_html_render(slug, site_name, label)`**

Verify og:image meta tag and card shortcode rendering in Hugo HTML output.

```python
def check_html_render(slug: str, site_name: str, label: str = "") -> list:
    """Hugo 출력 HTML에서 og:image + 카드 렌더링 검증"""
    findings = []
    site = HUGO_SITES.get(site_name)
    if not site:
        return findings

    output_prefix = site["output_prefix"]
    html_path = site["path"] / "public" / output_prefix / slug / "index.html"

    if not html_path.exists():
        findings.append({
            "post": label, "check": "html_render",
            "detail": f"HTML 파일 없음: {html_path}",
        })
        return findings

    try:
        html = html_path.read_text(encoding="utf-8")
    except Exception as e:
        findings.append({
            "post": label, "check": "html_render",
            "detail": f"HTML 읽기 실패: {e}",
        })
        return findings

    # 1. og:image 메타 태그 존재 여부
    if 'property="og:image"' not in html and 'name="og:image"' not in html:
        findings.append({
            "post": label, "check": "html_render",
            "detail": "og:image 메타 태그 없음",
        })

    # 2. 카드 shortcode가 HTML로 렌더링되었는지 확인
    # chain-card shortcode는 <div class="chain-card"> 또는 유사 HTML로 렌더링됨
    # 원시 shortcode {{< 가 HTML에 잔존하면 실패
    if "{{<" in html and "chain-card" in html:
        findings.append({
            "post": label, "check": "html_render",
            "detail": "chain-card shortcode가 HTML에 원시 상태로 잔존",
        })

    return findings
```

Key details:
- Checks og:image meta tag presence in rendered HTML
- Detects un-rendered shortcode patterns ({{< chain-card)
- Complements existing `check_hugo_html_rendering` which only checks raw markdown

**Function 3: `check_live_access(published_url, label)`**

HTTP HEAD request to verify live site returns 200.

```python
def check_live_access(published_url: str, label: str = "") -> list:
    """라이브 사이트 HTTP 200 확인"""
    import urllib.request
    import urllib.error

    findings = []
    if not published_url:
        return findings

    try:
        req = urllib.request.Request(published_url, method="HEAD")
        resp = urllib.request.urlopen(req, timeout=10)
        if resp.status != 200:
            findings.append({
                "post": label, "check": "live_access",
                "detail": f"HTTP {resp.status} — 예상: 200",
            })
    except urllib.error.HTTPError as e:
        findings.append({
            "post": label, "check": "live_access",
            "detail": f"HTTP 에러 {e.code}: {e.reason}",
        })
    except Exception as e:
        findings.append({
            "post": label, "check": "live_access",
            "detail": f"접근 실패: {str(e)[:80]}",
        })
    return findings
```

Key details:
- Uses `urllib.request` (stdlib, no new dependencies)
- HTTP HEAD only (read-only, no side effects)
- 10 second timeout
- Returns empty list on HTTP 200 (pass), findings on failure

**Integration into scan functions:**

Update `scan_chain_format()` to call the 3 new functions:

```python
# In scan_chain_format(), add after existing checks:
if not dry_run:
    results["hugo_build"].extend(check_hugo_build(skip=dry_run))
    results["html_render"].extend(check_hugo_html_rendering(slug, site_name, label))  # existing
    results["html_render"].extend(check_html_render(slug, site_name, label))  # new
    results["live_access"].extend(check_live_access(p.get("published_url"), label))

# In _CHECK_LABELS dict, add:
"hugo_build": "Hugo 빌드",
"html_render": "HTML 렌더링",
"live_access": "라이브 접근",
```

**Important: `import os` must be added at top if not already present.**

  </action>
  <verify>
    <automated>python -c "from audit.audit_format import check_hugo_build, check_html_render, check_live_access; print('3 new functions importable')"</automated>
  </verify>
  <done>All 3 new functions exist in audit/audit_format.py, importable without error, integrated into scan_chain_format()</done>
</task>

<task type="auto">
  <name>Task 2: Add unit tests for 3 new functions</name>
  <files>test_audit_format.py</files>
  <action>
Add test classes for the 3 new functions to `test_audit_format.py`. Follow existing style (class-based, pytest, self-contained).

**Test classes to add:**

```python
class TestHugoBuild:
    """check_hugo_build 단위테스트."""

    def test_skip_returns_empty(self):
        """skip=True이면 빈 리스트 반환."""
        from audit.audit_format import check_hugo_build
        assert check_hugo_build(skip=True) == []

    def test_nonexistent_site(self):
        """존재하지 않는 사이트명 → 빈 리스트 (사이트 not in HUGO_SITES)."""
        from audit.audit_format import check_hugo_build
        # Should not crash, may return findings or empty
        result = check_hugo_build(site_name="nonexistent", skip=False)
        assert isinstance(result, list)


class TestHtmlRender:
    """check_html_render 단위테스트."""

    def test_missing_html_file(self):
        """HTML 파일 없으면 findings 반환."""
        from audit.audit_format import check_html_render
        findings = check_html_render("nonexistent-slug-xyz", "rotcha", "test")
        assert len(findings) >= 1
        assert "HTML 파일 없음" in findings[0]["detail"]

    def test_unknown_site(self):
        """존재하지 않는 사이트 → 빈 리스트."""
        from audit.audit_format import check_html_render
        assert check_html_render("slug", "nonexistent", "test") == []


class TestLiveAccess:
    """check_live_access 단위테스트."""

    def test_empty_url(self):
        """빈 URL → 빈 리스트."""
        from audit.audit_format import check_live_access
        assert check_live_access("", "test") == []

    def test_none_url(self):
        """None URL → 빈 리스트."""
        from audit.audit_format import check_live_access
        assert check_live_access(None, "test") == []
```

Key patterns:
- Each test is self-contained (no DB, no network, no file I/O)
- Tests verify function signatures and edge cases, not actual Hugo builds or network calls
- Follow existing class naming: `TestHugoBuild`, `TestHtmlRender`, `TestLiveAccess`

  </action>
  <verify>
    <automated>python -m pytest test_audit_format.py -v 2>&1 | tail -20</automated>
  </verify>
  <done>All existing 39 tests still pass + new tests added (target: 45+ total)</done>
</task>

<task type="auto">
  <name>Task 3: Update _CHECK_LABELS and scan functions, verify CLI</name>
  <files>audit/audit_format.py</files>
  <action>
Ensure the integration is complete:

1. `_CHECK_LABELS` dict includes all 13 checks (10 existing + 3 new):
   - hugo_build, html_render, live_access added

2. `scan_chain_format()` calls the 3 new functions:
   - `check_hugo_build()` called once per chain (not per post)
   - `check_html_render()` called per post when not dry_run
   - `check_live_access()` called per post when not dry_run

3. `print_results()` handles the new check types in its output loop

4. CLI `--dry-run` flag skips hugo_build, html_render, and live_access

5. Run `python audit/audit_format.py --help` to verify CLI still works

6. Run `python audit/audit_format.py --dry-run --chain-id <lowest_chain_with_posts>` to verify no crashes

  </action>
  <verify>
    <automated>python audit/audit_format.py --help 2>&1 | head -5 && python -c "from audit.audit_format import _CHECK_LABELS; print(f'{len(_CHECK_LABELS)} checks:', list(_CHECK_LABELS.keys()))"</automated>
  </verify>
  <done>CLI works, _CHECK_LABELS has 13 entries, scan functions call new checks</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Hugo build → Script | Script runs `hugo --gc --minify` locally; output to public/ (read-only verification) |
| Network → Script | urllib HEAD request for live access (read-only, 10s timeout) |
| Filesystem → Script | Reads Hugo output HTML; no writes |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-30-01 | Elevation | Hugo build | accept | Local build only, no deploy; HUGO_THEMESDIR set |
| T-30-02 | Info Disclosure | Network HEAD | accept | HTTP HEAD only, no data sent, 10s timeout |
| T-30-03 | DoS | Hugo build timeout | mitigate | 120s timeout per site |
</threat_model>

<verification>
- `python -c "from audit.audit_format import check_hugo_build, check_html_render, check_live_access"` → import ok
- `python -m pytest test_audit_format.py -v` → all tests pass (39 existing + new)
- `python audit/audit_format.py --help` → shows all flags
- `python audit/audit_format.py --dry-run --all` → runs without crashes
- `_CHECK_LABELS` has 13 entries
</verification>

<success_criteria>
- check_hugo_build() implemented and integrated
- check_html_render() implemented and integrated (og:image + card rendering)
- check_live_access() implemented and integrated
- All 39 existing tests still pass
- New tests added (target: 45+ total)
- --dry-run skips all 3 new checks
- CLI --help shows updated description
</success_criteria>

<output>
Create `.planning/phases/30-audit-gap-closure/30-01-SUMMARY.md` when done
</output>
