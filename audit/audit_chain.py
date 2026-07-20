"""
audit/audit_chain.py — 체인 발행 품질 감사 (Phase 10)

프롬프트 릭, 미해소 마커, CTA 블록, 이미지 URL, R2 존재 여부, Hugo 빌드를
전수검사하여 회귀를 조기에 탐지한다.

사용법:
  python -m audit.audit_chain --chain-id 29     # 특정 체인 audit
  python -m audit.audit_chain --all               # 모든 체인 전수검사
  python -m audit.audit_chain --chain-id 29 --fix # 발견된 문제 자동 수정
  python -m audit.audit_chain --chain-id 29 --quick  # Hugo 빌드 스킵
"""

import argparse
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
from datetime import datetime

# ── 경로 ──
PROJECT_ROOT = Path(__file__).resolve().parent.parent

DB_CANDIDATES = [
    PROJECT_ROOT / "data" / "mc_chains.db",
    Path("/Users/twinssn/Projects/5000/data/mc_chains.db"),
    Path.home() / "Projects" / "5000" / "data" / "mc_chains.db",
]
DB_PATH = next((p for p in DB_CANDIDATES if p.exists()), DB_CANDIDATES[0])

HUGO_SITES = {
    "rotcha": {
        "path": Path("/Users/twinssn/Projects/rotcha-blog"),
        "project": "rotcha-blog",
    },
    "informationhot": {
        "path": Path("/Users/twinssn/Projects/informationhot-hugo"),
        "project": "informationhot-hugo",
    },
    "techpawz": {
        "path": Path("/Users/twinssn/Projects/techpawz-hugo"),
        "project": "techpawz-hugo",
    },
}


# ── 프롬프트 릭 패턴 ─────────────────────────────────────────────

_PROMPT_SECTION_RE = re.compile(
    r"^(?:"
    r"#\s*Role\s*\(역할\)|"
    r"#\s*SEO\s*기본\s*원칙|"
    r"#\s*Frontmatter\s*Rules|"
    r"##\s*title\s*규칙|"
    r"##\s*description\s*규칙|"
    r"##\s*tags\s*규칙|"
    r"##\s*categories\s*규칙|"
    r"#\s*Content\s*Structure|"
    r"#\s*Formatting\s*Rules|"
    r"##\s*절대\s*금지|"
    r"##\s*링크|"
    r"#\s*H2\s*제목\s*SEO\s*규칙|"
    r"#\s*Tone\s*&\s*Manner|"
    r"#\s*Output\s*Checklist|"
    r"#\s*Chain\s*Context|"
    r"#\s*이미지\s*플레이스홀더|"
    r"#\s*이미지\s*유형\s*판단|"
    r"image_type\s*결정\s*기준|"
    r"다음은\s*요청하신|"
    r"아래는\s*.*블로그\s*포스트|"
    r"이전\s*포스트\s*\(|"
    r"다음\s*포스트\s*\("
    r")"
)

_UNRESOLVED_MARKER_RE = re.compile(
    r"<!--\s*(?:thumbnail|image)\s*:\s*.*?-->|"
    r"<!--\s*todo:\s*(?:image|chart)\s*-->|"
    r"<!--todo:(?:image|chart)-->"
)

_CTA_RE = re.compile(r"더\s*(?:깊이\s*)?알아보기")
_CTA_HTML_RE = re.compile(r'<div[^>]*class="[^"]*cta[^"]*"[^>]*>')


# ── 1. 프롬프트 릭 검사 ──────────────────────────────────────────

def check_prompt_leak(body: str, label: str = "") -> list:
    """본문(body)에서 프롬프트 섹션 헤더가 노출되었는지 검사"""
    findings = []
    for i, line in enumerate(body.splitlines(), start=1):
        stripped = line.strip()
        if stripped and _PROMPT_SECTION_RE.match(stripped):
            findings.append({
                "post": label,
                "line": i,
                "match": stripped[:80],
            })
    return findings


# ── 2. 미해소 마커 검사 ──────────────────────────────────────────

def check_unresolved_markers(body: str, label: str = "") -> list:
    """본문에 미해소 마커가 남아있는지 검사"""
    findings = []
    for i, line in enumerate(body.splitlines(), start=1):
        for m in _UNRESOLVED_MARKER_RE.finditer(line):
            findings.append({
                "post": label,
                "line": i,
                "match": m.group()[:60],
            })
    return findings


# ── 3. CTA 인라인 블록 검사 ──────────────────────────────────────

def check_cta_leak(body: str, label: str = "") -> list:
    """본문에 AI가 직접 생성한 CTA 블록이 있는지 검사"""
    findings = []
    for i, line in enumerate(body.splitlines(), start=1):
        if _CTA_RE.search(line):
            findings.append({
                "post": label,
                "line": i,
                "match": line.strip()[:80],
            })
        if _CTA_HTML_RE.search(line):
            findings.append({
                "post": label,
                "line": i,
                "match": line.strip()[:80],
            })
    return findings


# ── 4. featureimage URL 검사 ──────────────────────────────────────

def check_featureimage_url(frontmatter: str, label: str = "") -> list:
    """frontmatter의 featureimage가 올바른 R2 URL 형식인지 검사"""
    findings = []
    for m in re.finditer(r'^\s*featureimage\s*:\s*["\']?(.+?)["\']?\s*$', frontmatter, re.MULTILINE):
        url = m.group(1).strip().strip('"').strip("'")
        issues = []
        if url.startswith("/") or url.startswith("images/"):
            issues.append("상대경로 — R2 전체 URL이 아님")
        if "thumb_thumb_" in url:
            issues.append("이중 접두사(thumb_thumb_) — Phase 7 이전 포맷")
        if not url.startswith("http"):
            issues.append("URL이 http(s)://로 시작하지 않음")
        if issues:
            findings.append({
                "post": label,
                "line": m.start(),
                "url": url,
                "issues": issues,
            })
    return findings


# ── 5. R2 이미지 존재 검사 ──────────────────────────────────────

def check_images_exist(body: str, label: str = "", timeout: int = 5) -> list:
    """본문의 R2 이미지 URL에 HEAD 요청하여 실제 존재하는지 확인"""
    import urllib.request
    import urllib.error

    findings = []
    urls = set()
    for m in re.finditer(r'!\[.*?\]\((https?://[^\s)]+)\)', body):
        urls.add(m.group(1))

    for url in sorted(urls):
        if "r2.dev" not in url and "img." not in url:
            continue
        if url.endswith(".gif"):
            continue
        try:
            req = urllib.request.Request(url, method="HEAD")
            resp = urllib.request.urlopen(req, timeout=timeout)
            if resp.status != 200:
                findings.append({
                    "post": label,
                    "url": url,
                    "status": resp.status,
                })
        except Exception as e:
            findings.append({
                "post": label,
                "url": url,
                "error": str(e)[:80],
            })
    return findings


# ── 5b. 썸네일 존재 검사 ─────────────────────────────────────────

# ── Whitelist content check (Phase 10 v2: replaces blacklist patterns) ──
#
# DEPRECATED (kept for rollback safety): _PROMPT_SECTION_RE, _UNRESOLVED_MARKER_RE,
# check_prompt_leak, check_unresolved_markers, check_cta_leak
# New check uses whitelist — only known-good markdown elements pass.

_ALLOWED_HTML_TAGS = frozenset()

_WHITELIST_BLOCKED_PATTERNS = [
    (re.compile(r'<!--.*?-->', re.DOTALL), "HTML 주석이 본문에 포함됨"),
    (re.compile(r'<(?:meta|script|div|span|link|ins)\b', re.IGNORECASE), "허용되지 않는 HTML 태그"),
    (re.compile(r'\{.*"(?:image_type|chart_type|image_keyword|chart_data)".*\}'), "raw JSON이 본문에 포함됨"),
]


def check_content_by_whitelist(body: str) -> list:
    """Whitelist 기반 본문 검사: 허용 마크다운만 통과, 비허용 요소 경고.

    허용: ATX 헤딩, 단락, 리스트, GFM 표, 코드 펜스(비JSON), 이미지, 링크, 빈 줄
    경고: HTML 주석, <meta>/<script>/<div>/<span>/<link>/<ins>, raw JSON
    """
    issues = []

    # 1. 전체 블록 단위 패턴 검사 (멀티라인)
    for pattern, msg in _WHITELIST_BLOCKED_PATTERNS:
        matches = pattern.findall(body)
        if matches:
            issues.append(f"[whitelist] {msg} (발견: {len(matches)}건)")

    # 2. 라인 단위 whitelist 검증 (코드 블록 제외)
    in_code_block = False
    for lineno, line in enumerate(body.split("\n"), 1):
        stripped = line.strip()
        if not stripped:
            continue

        # 코드 블록 시작/종료
        if stripped.startswith("```"):
            lang = stripped[3:].strip().lower()
            if lang == "json":
                issues.append(f"[whitelist] 라인 {lineno}: JSON 코드 펜스가 본문에 포함됨")
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        # 프론트매터
        if line == "---" or stripped == "---":
            continue

        # 허용되는 마크다운 요소
        is_heading = bool(re.match(r'^#{1,6}\s', stripped))
        is_list = bool(re.match(r'^[-*+]\s|^\d+\.\s', stripped))
        is_table = bool(re.match(r'^\||^[-|:\s]+$', stripped))
        is_image = bool(re.match(r'!\[.*?\]\(https?://', stripped))
        is_link = bool(re.match(r'\[.*?\]\(https?://', stripped))

        if is_heading or is_list or is_table or is_image or is_link:
            continue

        # 나머지 텍스트는 단락으로 간주 (통과)
        # 단, HTML 댓글이나 태그는 위에서 전체 블록 검사로 잡힘

    return issues


def check_thumbnail(thumbnail_path, label: str = "") -> list:
    """thumbnail_path가 DB에 저장되어 있는지 검사"""
    if not thumbnail_path:
        return [{"post": label, "issue": "thumbnail_path = None — 썸네일 생성되지 않음"}]
    tp = Path(str(thumbnail_path))
    if not tp.exists():
        return [{"post": label, "issue": f"thumbnail_path 파일 없음: {thumbnail_path}"}]
    return []


# ── 6. Hugo 빌드 검사 ────────────────────────────────────────────

def check_hugo_build(skip: bool = False) -> list:
    """3개 Hugo 사이트 빌드 — 에러/경고 출력"""
    findings = []
    if skip:
        return findings

    hugo_bin = shutil.which("hugo") or "/opt/homebrew/bin/hugo"
    if not Path(hugo_bin).exists():
        return [{"site": "all", "type": "hugo_not_found"}]

    for name, site in HUGO_SITES.items():
        try:
            build = subprocess.run(
                [hugo_bin, "--gc", "--minify"],
                cwd=str(site["path"]),
                capture_output=True,
                text=True,
                timeout=120,
            )
            if build.returncode != 0:
                errors = [l for l in build.stderr.splitlines() if "ERROR" in l][:5]
                findings.append({
                    "site": name,
                    "type": "hugo_build_fail",
                    "returncode": build.returncode,
                    "details": errors or [build.stderr[:200]],
                })
            else:
                warnings = [l.strip() for l in build.stderr.splitlines()
                           if "WARN" in l or "crossorigin" in l.lower()
                           or "integrity" in l.lower()]
                if warnings:
                    findings.append({
                        "site": name,
                        "type": "hugo_build_warning",
                        "details": warnings[:5],
                    })
        except subprocess.TimeoutExpired:
            findings.append({
                "site": name,
                "type": "hugo_build_timeout",
            })

    return findings


# ── DB 조회 ───────────────────────────────────────────────────────

def get_chain_posts(chain_id: int) -> list:
    """DB에서 체인의 포스트 목록 조회 (draft_md 기반)"""
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    posts = db.execute(
        """SELECT id, slug, title, status, step,
                  hugo_file_path, published_url,
                  thumbnail_path, thumbnail_source,
                  draft_md
           FROM chain_posts
           WHERE chain_id = ?
           ORDER BY step ASC""",
        (chain_id,),
    ).fetchall()
    db.close()
    return [dict(p) for p in posts]


# ── frontmatter 분리 ──────────────────────────────────────────────

def _split_frontmatter(text: str) -> tuple:
    """(frontmatter, body) 분리. frontmatter가 없으면 ('', text)"""
    t = text.lstrip()
    if t.startswith("---"):
        end = t.find("---", 3)
        if end != -1:
            return (t[3:end].strip(), t[end + 3:].strip())
    return ("", t)


# ── 메인 audit 함수 ───────────────────────────────────────────────

def scan_chain_posts(chain_id: int, quick: bool = False, fix: bool = False) -> dict:
    """체인의 모든 포스트에 대해 7개 검사 실행"""
    results = {
        "chain_id": chain_id,
        "prompt_leak": [],
        "unresolved_markers": [],
        "cta_leak": [],
        "whitelist": [],
        "featureimage_url": [],
        "images_exist": [],
        "thumbnail_missing": [],
        "hugo_build": [],
    }

    posts = get_chain_posts(chain_id)
    if not posts:
        results["_error"] = f"Chain #{chain_id} — DB에 포스트 없음"
        return results

    for p in posts:
        label = f'#{p["id"]} step{p["step"]} "{p["title"][:30]}"'
        body = p["draft_md"] or ""
        fm, content = _split_frontmatter(body)

        results["prompt_leak"].extend(check_prompt_leak(content, label))
        results["unresolved_markers"].extend(check_unresolved_markers(body, label))
        results["cta_leak"].extend(check_cta_leak(content, label))
        results["whitelist"].extend(check_content_by_whitelist(body))
        results["featureimage_url"].extend(check_featureimage_url(fm, label))
        results["images_exist"].extend(check_images_exist(content, label))
        results["thumbnail_missing"].extend(check_thumbnail(p.get("thumbnail_path"), label))

    results["hugo_build"] = check_hugo_build(skip=quick)

    if fix:
        _auto_fix(results)

    return results


def scan_all_chains(quick: bool = False, fix: bool = False) -> dict:
    """모든 published 체인 전수검사"""
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    chains = db.execute(
        "SELECT id, seed, status FROM chains ORDER BY id ASC"
    ).fetchall()
    db.close()

    aggregated = {
        "chain_id": "all",
        "prompt_leak": [],
        "unresolved_markers": [],
        "cta_leak": [],
        "featureimage_url": [],
        "images_exist": [],
        "thumbnail_missing": [],
        "hugo_build": [],
    }

    for c in chains:
        cid = c["id"]
        if cid < 5:
            continue
        result = scan_chain_posts(cid, quick=quick, fix=fix)
        for key in aggregated:
            if key != "chain_id":
                aggregated[key].extend(result.get(key, []))

    aggregated["hugo_build"] = check_hugo_build(skip=quick)
    return aggregated


# ── --fix 모드 ────────────────────────────────────────────────────

def _auto_fix(results: dict):
    """발견된 문제를 draft_md에서 자동 수정"""
    fixed_labels = set()

    for f in results["prompt_leak"]:
        label = f["post"]
        if label in fixed_labels:
            continue
        _fix_prompt_leak_in_db(label)
        fixed_labels.add(label)
        print(f"  [fix] 프롬프트 릭 제거: {label}")

    for f in results["unresolved_markers"]:
        label = f["post"]
        if label in fixed_labels:
            continue
        _fix_markers_in_db(label)
        fixed_labels.add(label)
        print(f"  [fix] 미해소 마커 제거: {label}")

    for f in results["cta_leak"]:
        label = f["post"]
        if label in fixed_labels:
            continue
        _fix_cta_in_db(label)
        fixed_labels.add(label)
        print(f"  [fix] CTA 블록 제거: {label}")


def _extract_post_id(label: str) -> int:
    m = re.match(r'#(\d+)', label)
    return int(m.group(1)) if m else 0


def _update_draft_md(post_id: int, updater_fn):
    """DB에서 draft_md를 읽어 updater_fn 적용 후 저장"""
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    row = db.execute("SELECT id, draft_md FROM chain_posts WHERE id=?", (post_id,)).fetchone()
    if not row:
        db.close()
        return
    md = row["draft_md"] or ""
    new_md = updater_fn(md)
    if new_md != md:
        db.execute(
            "UPDATE chain_posts SET draft_md=?, updated_at=datetime('now','localtime') WHERE id=?",
            (new_md, post_id),
        )
        db.commit()
    db.close()


def _fix_prompt_leak_in_db(label: str):
    pid = _extract_post_id(label)
    if not pid:
        return

    def _strip(text):
        lines = text.splitlines(keepends=True)
        start = 0
        if lines and lines[0].strip() == "---":
            for i in range(1, len(lines)):
                if lines[i].strip() == "---":
                    start = i + 1
                    break
        out = lines[:start]
        for ln in lines[start:]:
            if ln.strip() and _PROMPT_SECTION_RE.match(ln.strip()):
                continue
            out.append(ln)
        return "".join(out)

    _update_draft_md(pid, _strip)


def _fix_markers_in_db(label: str):
    pid = _extract_post_id(label)
    if not pid:
        return

    def _strip(text):
        text = re.sub(r'<!--\s*(thumbnail|image)\s*:\s*.*?-->', '', text)
        text = re.sub(r'<!--\s*todo:\s*(image|chart)\s*-->', '', text)
        text = re.sub(r'<!--todo:(image|chart)-->', '', text)
        return text

    _update_draft_md(pid, _strip)


def _fix_cta_in_db(label: str):
    pid = _extract_post_id(label)
    if not pid:
        return

    def _strip(text):
        return re.sub(r'<div[^>]*>.*?더\s*(?:깊이\s*)?알아보기.*?</div>', '', text, flags=re.DOTALL)

    _update_draft_md(pid, _strip)


# ── 출력 ──────────────────────────────────────────────────────────

_CHECK_LABELS = {
    "prompt_leak": "프롬프트 릭",
    "unresolved_markers": "미해소 마커",
    "cta_leak": "CTA 블록",
    "whitelist": "본문 whitelist 위반",
    "featureimage_url": "featureimage URL",
    "images_exist": "R2 이미지 존재",
    "thumbnail_missing": "썸네일 생성",
    "hugo_build": "Hugo 빌드",
}


def print_results(results: dict):
    chain_id = results["chain_id"]
    print(f"\n{'='*55}")
    print(f"  audit_chain.py — Chain #{chain_id}")
    print(f"  ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
    print(f"{'='*55}")

    if results.get("_error"):
        print(f"\n  ⚠ {results['_error']}")
        return

    passed = 0
    failed = 0

    for key, label in _CHECK_LABELS.items():
        items = results.get(key, [])
        if not items:
            print(f"  ✓ {label}: 0건")
            passed += 1
        else:
            print(f"  ✗ {label}: {len(items)}건")
            failed += 1
            for item in items[:5]:
                if key == "prompt_leak":
                    print(f"    • {item['post']} L{item['line']} — \"{item['match']}\"")
                elif key == "unresolved_markers":
                    print(f"    • {item['post']} L{item['line']} — \"{item['match']}\"")
                elif key == "cta_leak":
                    print(f"    • {item['post']} L{item['line']} — \"{item['match']}\"")
                elif key == "featureimage_url":
                    print(f"    • {item['post']} — {item['url']}")
                    for iss in item.get("issues", []):
                        print(f"      → {iss}")
                elif key == "images_exist":
                    s = item.get('status', 'ERR')
                    e = item.get('error', '')
                    print(f"    • {item['post']} — HTTP {s} {e}")
                elif key == "thumbnail_missing":
                    print(f"    • {item['post']} — {item['issue']}")
                elif key == "hugo_build":
                    for d in item.get("details", []):
                        print(f"    • {item['site']}: {d}")
            if len(items) > 5:
                print(f"    ... 외 {len(items) - 5}건")

    total = passed + failed
    if failed == 0:
        print(f"\n  ═══════════════════════════════")
        print(f"   ✅ ALL PASS — {total}/{total} checks")
        print(f"  ═══════════════════════════════")
    else:
        print(f"\n  ═══════════════════════════════")
        print(f"   ❌ {failed} FAIL — {passed}/{total} checks")
        print(f"  ═══════════════════════════════")


# ── CLI ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="mc — 체인 발행 품질 감사")
    parser.add_argument("--chain-id", type=int, help="감사할 체인 ID")
    parser.add_argument("--all", action="store_true", help="모든 체인 전수검사")
    parser.add_argument("--fix", action="store_true", help="발견된 문제 자동 수정")
    parser.add_argument("--quick", action="store_true", help="Hugo 빌드 스킵")

    args = parser.parse_args()

    if not args.chain_id and not args.all:
        parser.print_help()
        print("\n에러: --chain-id N 또는 --all 을 지정하세요.")
        sys.exit(1)

    if not DB_PATH.exists():
        print(f"에러: DB를 찾을 수 없음 — {DB_PATH}")
        sys.exit(1)

    if args.chain_id:
        result = scan_chain_posts(args.chain_id, quick=args.quick, fix=args.fix)
    else:
        result = scan_all_chains(quick=args.quick, fix=args.fix)

    print_results(result)


if __name__ == "__main__":
    main()
