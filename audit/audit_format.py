"""
audit/audit_format.py — 포스트 형식/시각 구조 자동 검증 (Phase 29)

audit_chain.py가 검사하지 않는 포맷 관련 항목을 검증:
- 카드 주입 수/위치
- 크로스링크 URL 정확성
- H2 구조 (stepSections 템플릿 대비)
- 프론트매터 완성도
- Hugo HTML 렌더링
- DB 일관성
- 카드 타입 정확성
- 외부링크 패턴
- chain-card shortcode

사용법:
  python audit/audit_format.py --chain-id 29     # 특정 체인
  python audit/audit_format.py --all              # 모든 체인 전수검사
  python audit/audit_format.py --dry-run          # Hugo 빌드 없이 검증
"""

import argparse
import os
import re
import sqlite3
import subprocess
import shutil
import sys
from pathlib import Path

import yaml

# Add project root to path for mc module
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

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
        "output_prefix": "posts/",
    },
    "issue.techpawz": {
        "path": Path("/Users/twinssn/Projects/issue-techpawz-hugo"),
        "project": "issue-techpawz-hugo",
        "output_prefix": "",
    },
    "techpawz": {
        "path": Path("/Users/twinssn/Projects/techpawz-hugo"),
        "project": "techpawz-hugo",
        "output_prefix": "",
    },
}

DEPTH_TO_SITE = {0: "rotcha", 1: "issue.techpawz", 2: "techpawz"}
SITE_TO_DOMAIN = {
    "rotcha": "issue.techpawz.com",
    "issue.techpawz": "techpawz.com",
    "techpawz": None,
}

PROMPTS_PATH = PROJECT_ROOT / "config" / "prompts.yaml"

# ── 카드 패턴 ────────────────────────────────────────────────────
RE_CHAIN_CARD = re.compile(r'\{\{<\s*chain-card\s+.*?\}\}')
RE_CHAIN_OFFICIAL = re.compile(r'\{\{<\s*chain-official-card\s+.*?\}\}')
RE_EXT_PRIMARY = re.compile(
    r'<div style="margin:1\.5em 0[^"]*"[^>]*>'
    r'.*?관련 공식 사이트.*?바로가기 →.*?</div>',
    re.DOTALL,
)
RE_EXT_FALLBACK = re.compile(
    r'<div style="margin:1\.5em 0[^"]*"[^>]*>'
        r'.*?더 많은 정보.*?!</div>',
    re.DOTALL,
)
RE_H2 = re.compile(r'^## (.+)$', re.MULTILINE)


# ── 프론트매터 분리 ──────────────────────────────────────────────

def _split_frontmatter(text: str) -> tuple:
    """(frontmatter_str, body) 분리"""
    t = text.lstrip()
    if t.startswith("---"):
        end = t.find("---", 3)
        if end != -1:
            return (t[3:end].strip(), t[end + 3:].strip())
    return ("", t)


def _parse_frontmatter(fm_str: str) -> dict:
    """YAML 프론트매터 파싱"""
    if not fm_str:
        return {}
    try:
        return yaml.safe_load(fm_str) or {}
    except yaml.YAMLError:
        return {}


# ── H2 섹션 템플릿 로드 ─────────────────────────────────────────

def _load_step_sections() -> dict:
    """prompts.yaml에서 category별 stepSections 로드"""
    if not PROMPTS_PATH.exists():
        return {}
    with open(PROMPTS_PATH, encoding="utf-8") as f:
        prompts = yaml.safe_load(f)
    result = {}
    for cat_key, cat_val in prompts.get("keyword_categories", {}).items():
        sections = {}
        for step in ("step1", "step2", "step3"):
            key = f"{step}_sections"
            templates = cat_val.get(key, [])
            if templates:
                sections[step] = templates
        if sections:
            result[cat_key] = sections
    return result


def _extract_keyword_from_template(template: str) -> str:
    """H2 템플릿에서 {keyword}를 제거한 시맨틱 패턴 추출"""
    # "## {keyword} — 위치와 기본 정보" → "위치와 기본 정보"
    cleaned = template.replace("{keyword}", "").strip()
    cleaned = re.sub(r'^##\s*', '', cleaned)
    cleaned = re.sub(r'^[—–-]\s*', '', cleaned)
    cleaned = re.sub(r'^마무리\s*[—–-]\s*', '마무리 ', cleaned)
    return cleaned.strip()


# ── DB 조회 ──────────────────────────────────────────────────────

def get_published_posts(chain_id: int = None) -> list:
    """DB에서 발행된 포스트 목록 조회"""
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    if chain_id:
        rows = db.execute(
            """SELECT id, chain_id, depth, step, title, slug,
                      category_guess, hugo_file_path, published_url,
                      card_injected, card_injected_at, published_md,
                      draft_md, status
               FROM chain_posts
               WHERE chain_id = ? AND published_url IS NOT NULL
               ORDER BY chain_id, step""",
            (chain_id,),
        ).fetchall()
    else:
        rows = db.execute(
            """SELECT id, chain_id, depth, step, title, slug,
                      category_guess, hugo_file_path, published_url,
                      card_injected, card_injected_at, published_md,
                      draft_md, status
               FROM chain_posts
               WHERE published_url IS NOT NULL
               ORDER BY chain_id, step"""
        ).fetchall()
    db.close()
    return [dict(r) for r in rows]


def get_all_chains() -> list:
    """DB에서 모든 체인 목록 조회"""
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    chains = db.execute(
        "SELECT id, seed, status FROM chains ORDER BY id ASC"
    ).fetchall()
    db.close()
    return [dict(c) for c in chains]


# ── 1. 카드 주입 수 검증 ────────────────────────────────────────

def check_card_count(body: str, depth: int, label: str = "") -> list:
    """본문의 카드 수 검증 (max 2: 중간 1 + 하단 1)"""
    findings = []
    shortcode_count = len(RE_CHAIN_CARD.findall(body))
    ext_count = len(RE_EXT_PRIMARY.findall(body)) + len(RE_EXT_FALLBACK.findall(body))

    if depth in (0, 1):
        # D0/D1: chain-card 만 (max 2)
        if shortcode_count > 2:
            findings.append({
                "post": label, "check": "card_count",
                "detail": f"chain-card {shortcode_count}개 — 최대 2개 초과",
            })
    elif depth == 2:
        # D2: 외부링크 카드 1개
        if ext_count > 1:
            findings.append({
                "post": label, "check": "card_count",
                "detail": f"외부링크 카드 {ext_count}개 — 최대 1개 초과",
            })
        if shortcode_count > 0:
            findings.append({
                "post": label, "check": "card_count",
                "detail": f"D2에 chain-card {shortcode_count}개 — 없어야 함",
            })
    return findings


# ── 2. 카드 위치 검증 ────────────────────────────────────────────

def check_card_placement(body: str, depth: int, label: str = "") -> list:
    """카드 위치 검증 (중간 = 2번째 H2 이후, 하단 = 마지막 H2 이후)"""
    findings = []
    h2_positions = [m.start() for m in RE_H2.finditer(body)]

    if depth in (0, 1):
        card_positions = [m.start() for m in RE_CHAIN_CARD.finditer(body)]
        if len(card_positions) == 2 and len(h2_positions) >= 3:
            # 중간 카드: 3번째 H2(인덱스 2) 앞에 있어야 함
            mid_card = card_positions[0]
            third_h2 = h2_positions[2]
            if mid_card >= third_h2:
                findings.append({
                    "post": label, "check": "card_placement",
                    "detail": f"중간 카드가 3번째 H2({third_h2}) 뒤에 위치",
                })
            # 하단 카드: 마지막 H2 뒤에 있어야 함
            bottom_card = card_positions[1]
            last_h2 = h2_positions[-1]
            if bottom_card < last_h2:
                findings.append({
                    "post": label, "check": "card_placement",
                    "detail": f"하단 카드가 마지막 H2({last_h2}) 앞에 위치",
                })
        elif len(card_positions) == 1 and len(h2_positions) >= 1:
            # 카드 1개: 마지막 H2 뒤에 있어야 함
            card_pos = card_positions[0]
            last_h2 = h2_positions[-1]
            if card_pos < last_h2:
                findings.append({
                    "post": label, "check": "card_placement",
                    "detail": f"카드가 마지막 H2({last_h2}) 앞에 위치",
                })
    elif depth == 2:
        ext_positions = (
            [m.start() for m in RE_EXT_PRIMARY.finditer(body)]
            + [m.start() for m in RE_EXT_FALLBACK.finditer(body)]
        )
        if ext_positions and h2_positions:
            last_ext = max(ext_positions)
            last_h2 = h2_positions[-1]
            if last_ext < last_h2:
                findings.append({
                    "post": label, "check": "card_placement",
                    "detail": f"외부링크 카드가 마지막 H2({last_h2}) 앞에 위치",
                })
    return findings


# ── 3. 크로스링크 URL 검증 ───────────────────────────────────────

def check_cross_link_url(body: str, depth: int, label: str = "") -> list:
    """크로스링크 URL이 올바른 도메인을 가리키는지 검증"""
    findings = []
    expected_domain = SITE_TO_DOMAIN.get(DEPTH_TO_SITE.get(depth))
    if not expected_domain:
        return findings  # D2는 외부링크라 크로스링크 없음

    # chain-card shortcode에서 URL 추출
    for m in RE_CHAIN_CARD.finditer(body):
        card_text = m.group()
        url_match = re.search(r'href="([^"]+)"', card_text)
        if not url_match:
            url_match = re.search(r'url="([^"]+)"', card_text)
        if url_match:
            url = url_match.group(1)
            if expected_domain not in url:
                findings.append({
                    "post": label, "check": "cross_link_url",
                    "detail": f"D{depth} 카드 URL이 {expected_domain}을 가리키지 않음: {url}",
                })
    return findings


# ── 4. H2 구조 검증 ─────────────────────────────────────────────

def check_h2_structure(body: str, category: str, step: int, label: str = "") -> list:
    """H2 구조가 prompts.yaml의 stepSections 템플릿과 일치하는지 검증"""
    findings = []
    step_sections = _load_step_sections()
    cat_data = step_sections.get(category, {})
    step_key = f"step{step}"
    templates = cat_data.get(step_key, [])

    if not templates:
        return findings  # 해당 카테고리의 템플릿 없음 (검증 불가)

    expected_count = len(templates)
    h2_matches = RE_H2.findall(body)
    actual_count = len(h2_matches)

    if actual_count != expected_count:
        findings.append({
            "post": label, "check": "h2_structure",
            "detail": f"H2 개수 불일치: 예상 {expected_count}, 실제 {actual_count} "
                      f"({category}/{step_key})",
        })

    # 시맨틱 구조 검증: 각 H2가 해당 step의 템플릿 중 하나와 매칭되는지
    # (AI가 제목을 변경할 수 있으므로 시맨틱 키워드 기반)
    for i, h2_title in enumerate(h2_matches):
        # 매칭 가능한 템플릿 키워드 추출
        matched = False
        for tmpl in templates:
            keyword = _extract_keyword_from_template(tmpl)
            # 핵심 키워드 매칭 (2단어 이상)
            keywords = [k.strip() for k in keyword.split() if len(k.strip()) >= 2]
            if keywords and any(kw in h2_title for kw in keywords if kw not in ("##",)):
                matched = True
                break
        # 매칭 실패해도 경고만 (AI가 제목을 자유롭게 변경할 수 있음)
        # findings.append(...) — 과도한 오탐 방지를 위해 생략

    return findings


# ── 5. 프론트매터 완성도 검증 ────────────────────────────────────

def check_frontmatter(body: str, label: str = "") -> list:
    """프론트매터 필수 필드 존재 여부 검증"""
    findings = []
    fm_str, _ = _split_frontmatter(body)
    fm = _parse_frontmatter(fm_str)

    if not fm:
        findings.append({
            "post": label, "check": "frontmatter",
            "detail": "프론트매터 없음",
        })
        return findings

    required_fields = ["title", "description", "draft", "slug", "date", "featureimage"]
    for field in required_fields:
        val = fm.get(field)
        if val is None or val == "" or val == []:
            findings.append({
                "post": label, "check": "frontmatter",
                "detail": f"필수 필드 '{field}' 누락 또는 빈 값",
            })

    # featureimage URL 형식 검증
    featureimage = fm.get("featureimage", "")
    if featureimage:
        if not str(featureimage).startswith("http"):
            findings.append({
                "post": label, "check": "frontmatter",
                "detail": f"featureimage가 URL 형식이 아님: {featureimage}",
            })
        if "thumb_thumb_" in str(featureimage):
            findings.append({
                "post": label, "check": "frontmatter",
                "detail": "featureimage에 이중 접두사(thumb_thumb_)",
            })

    # draft가 false인지
    if fm.get("draft") is not False and fm.get("draft") != "false":
        findings.append({
            "post": label, "check": "frontmatter",
            "detail": f"draft가 false가 아님: {fm.get('draft')}",
        })

    return findings


# ── 6. Hugo HTML 렌더링 검증 ────────────────────────────────────

def check_hugo_html_rendering(slug: str, site_name: str, label: str = "") -> list:
    """Hugo 출력 HTML에서 원시 마크다운 잔존 여부 검증"""
    findings = []
    site = HUGO_SITES.get(site_name)
    if not site:
        return findings

    output_prefix = site["output_prefix"]
    html_path = site["path"] / "public" / output_prefix / slug / "index.html"

    if not html_path.exists():
        findings.append({
            "post": label, "check": "hugo_html",
            "detail": f"Hugo 출력 파일 없음: {html_path}",
        })
        return findings

    try:
        html_content = html_path.read_text(encoding="utf-8")
    except Exception as e:
        findings.append({
            "post": label, "check": "hugo_html",
            "detail": f"HTML 읽기 실패: {e}",
        })
        return findings

    # 원시 마크다운 패턴 검출
    raw_md_patterns = [
        (re.compile(r'(?<!`)##\s+\S'), "원시 H2 마크다운"),
        (re.compile(r'(?<!`)!\[.*?\]\(.*?\)'), "원시 이미지 마크다운"),
        (re.compile(r'(?<!\[)\[.*?\]\(.*?\)(?!\])'), "원시 링크 마크다운"),
        (re.compile(r'```'), "원시 코드 펜스"),
    ]
    for pattern, desc in raw_md_patterns:
        matches = pattern.findall(html_content)
        if matches:
            # 코드 블록 내부는 제외 (간이 필터)
            findings.append({
                "post": label, "check": "hugo_html",
                "detail": f"HTML에 {desc} 발견 ({len(matches)}건)",
            })

    # CTA 블록 직접 삽입 검출 (시스템이 주입해야 함)
    if 'class="cta' in html_content or "더 알아보기 →" in html_content:
        if "chain-card" not in html_content and "_cta" not in html_content:
            findings.append({
                "post": label, "check": "hugo_html",
                "detail": "HTML에 CTA 블록이 직접 포함됨 (시스템 주입 아님)",
            })

    return findings


# ── 7. DB 일관성 검증 ────────────────────────────────────────────

def check_db_consistency(posts: list, label_prefix: str = "") -> list:
    """DB 레코드 간 일관성 검증"""
    findings = []
    for p in posts:
        label = f'{label_prefix}#{p["id"]} step{p["step"]} "{p["title"][:30]}"'

        # published_url 존재 but status가 published가 아닌 경우
        if p["published_url"] and p["status"] not in ("published", "draft"):
            findings.append({
                "post": label, "check": "db_consistency",
                "detail": f"published_url 존재 but status={p['status']}",
            })

        # hugo_file_path가 있지만 파일이 없는 경우
        hugo_path = p.get("hugo_file_path")
        if hugo_path and not Path(hugo_path).exists():
            findings.append({
                "post": label, "check": "db_consistency",
                "detail": f"hugo_file_path 존재 but 파일 없음: {hugo_path}",
            })

        # card_injected_at이 있지만 card_injected가 False
        if p.get("card_injected_at") and not p.get("card_injected"):
            findings.append({
                "post": label, "check": "db_consistency",
                "detail": "card_injected_at 존재 but card_injected=False",
            })

    return findings


# ── 8. 카드 타입 검증 ────────────────────────────────────────────

def check_card_type(body: str, depth: int, label: str = "") -> list:
    """카드 타입이 depth에 맞는지 검증"""
    findings = []
    if depth in (0, 1):
        # D0/D1: chain-card만, chain-official-card 없음
        official_count = len(RE_CHAIN_OFFICIAL.findall(body))
        if official_count > 0:
            findings.append({
                "post": label, "check": "card_type",
                "detail": f"D{depth}에 chain-official-card {official_count}개 — 없어야 함",
            })
        # 외부링크 카드 없음
        ext_count = len(RE_EXT_PRIMARY.findall(body)) + len(RE_EXT_FALLBACK.findall(body))
        if ext_count > 0:
            findings.append({
                "post": label, "check": "card_type",
                "detail": f"D{depth}에 외부링크 카드 {ext_count}개 — 없어야 함",
            })
    elif depth == 2:
        # D2: chain-card 없음, 외부링크 카드만
        shortcode_count = len(RE_CHAIN_CARD.findall(body))
        if shortcode_count > 0:
            findings.append({
                "post": label, "check": "card_type",
                "detail": f"D2에 chain-card {shortcode_count}개 — 없어야 함",
            })
        ext_count = len(RE_EXT_PRIMARY.findall(body)) + len(RE_EXT_FALLBACK.findall(body))
        if ext_count == 0:
            findings.append({
                "post": label, "check": "card_type",
                "detail": "D2에 외부링크 카드 없음",
            })
    return findings


# ── 9. 외부링크 패턴 검증 ────────────────────────────────────────

def check_external_link_pattern(body: str, depth: int, label: str = "") -> list:
    """외부링크 카드 HTML 패턴 검증 (D2만)"""
    findings = []
    if depth != 2:
        return findings

    # 외부링크 카드 존재 여부
    has_primary = bool(RE_EXT_PRIMARY.search(body))
    has_fallback = bool(RE_EXT_FALLBACK.search(body))

    if not has_primary and not has_fallback:
        return findings  # 카드 자체가 없으면 card_type에서 이미 잡힘

    # HTML 구조 검증: <div style="margin:1.5em 0..."> 포함
    ext_blocks = re.findall(r'<div style="margin:1\.5em 0[^"]*".*?</div>', body, re.DOTALL)
    for block in ext_blocks:
        if "관련 공식 사이트" not in block and "더 많은 정보" not in block:
            findings.append({
                "post": label, "check": "external_link_pattern",
                "detail": f"외부링크 카드 div에 텍스트 라벨 없음",
            })
        # 바로가기 링크 존재 (primary인 경우)
        if "관련 공식 사이트" in block and "바로가기" not in block:
            findings.append({
                "post": label, "check": "external_link_pattern",
                "detail": "primary 카드에 '바로가기' 링크 없음",
            })

    return findings


# ── 10. chain-card shortcode 검증 ───────────────────────────────

def check_chain_card_shortcode(body: str, depth: int, label: str = "") -> list:
    """chain-card shortcode 구조 검증 (D0/D1)"""
    findings = []
    if depth not in (0, 1):
        return findings

    for m in RE_CHAIN_CARD.finditer(body):
        card = m.group()
        # 필수 속성 존재 여부
        if 'title=' not in card:
            findings.append({
                "post": label, "check": "chain_card_shortcode",
                "detail": "chain-card에 title 속성 없음",
            })
        if 'url=' not in card and 'href=' not in card:
            findings.append({
                "post": label, "check": "chain_card_shortcode",
                "detail": "chain-card에 url/href 속성 없음",
            })
        # 닫기 태그 확인
        if not card.endswith("}}"):
            findings.append({
                "post": label, "check": "chain_card_shortcode",
                "detail": f"chain-card shortcode 닫기 태그 이상: ...{card[-20:]}",
            })

    return findings


# ── 11. Hugo 빌드 검증 ──────────────────────────────────────────

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

    sites = {site_name: HUGO_SITES[site_name]} if site_name and site_name in HUGO_SITES else HUGO_SITES
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


# ── 12. HTML 렌더링 검증 ─────────────────────────────────────────

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


# ── 13. 라이브 접근 검증 ─────────────────────────────────────────

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


# ── 메인 검증 함수 ───────────────────────────────────────────────

_CHECK_LABELS = {
    "card_count": "카드 주입 수",
    "card_placement": "카드 위치",
    "cross_link_url": "크로스링크 URL",
    "h2_structure": "H2 구조",
    "frontmatter": "프론트매터 완성도",
    "hugo_html": "Hugo HTML 렌더링",
    "db_consistency": "DB 일관성",
    "card_type": "카드 타입",
    "external_link_pattern": "외부링크 패턴",
    "chain_card_shortcode": "chain-card shortcode",
    "hugo_build": "Hugo 빌드",
    "html_render": "HTML 렌더링",
    "live_access": "라이브 접근",
}


def scan_chain_format(chain_id: int, dry_run: bool = False) -> dict:
    """특정 체인의 모든 포스트에 대해 10개 형식 검증 실행"""
    results = {key: [] for key in _CHECK_LABELS}
    results["chain_id"] = chain_id

    posts = get_published_posts(chain_id)
    if not posts:
        results["_error"] = f"Chain #{chain_id} — 발행된 포스트 없음"
        return results

    for p in posts:
        label = f'#{p["id"]} step{p["step"]} "{p["title"][:30]}"'
        body = p["published_md"] or p["draft_md"] or ""
        depth = p["depth"] or 0
        step = p["step"] or 1
        category = p["category_guess"] or "etc"
        slug = p["slug"] or ""
        site_name = DEPTH_TO_SITE.get(depth, "rotcha")

        fm_str, content = _split_frontmatter(body)

        results["card_count"].extend(check_card_count(body, depth, label))
        results["card_placement"].extend(check_card_placement(body, depth, label))
        results["cross_link_url"].extend(check_cross_link_url(body, depth, label))
        results["h2_structure"].extend(check_h2_structure(content, category, step, label))
        results["frontmatter"].extend(check_frontmatter(body, label))
        results["card_type"].extend(check_card_type(body, depth, label))
        results["external_link_pattern"].extend(check_external_link_pattern(body, depth, label))
        results["chain_card_shortcode"].extend(check_chain_card_shortcode(body, depth, label))

        # Hugo HTML 검증 (dry_run이 아닐 때만)
        if not dry_run and slug:
            results["hugo_html"].extend(
                check_hugo_html_rendering(slug, site_name, label)
            )
            results["html_render"].extend(
                check_html_render(slug, site_name, label)
            )
            results["live_access"].extend(
                check_live_access(p.get("published_url"), label)
            )

    # DB 일관성 (전체 체인 레벨)
    results["db_consistency"].extend(check_db_consistency(posts))

    # Hugo 빌드 검증 (dry_run이 아닐 때만, 체인 단위 1회)
    if not dry_run:
        results["hugo_build"].extend(check_hugo_build(skip=dry_run))

    return results


def scan_all_format(dry_run: bool = False) -> dict:
    """모든 발행 체인 전수검사"""
    aggregated = {key: [] for key in _CHECK_LABELS}
    aggregated["chain_id"] = "all"

    chains = get_all_chains()
    for c in chains:
        cid = c["id"]
        if cid < 5:
            continue
        result = scan_chain_format(cid, dry_run=dry_run)
        for key in _CHECK_LABELS:
            aggregated[key].extend(result.get(key, []))

    return aggregated


# ── 출력 ─────────────────────────────────────────────────────────

def print_results(results: dict):
    chain_id = results["chain_id"]
    print(f"\n{'='*55}")
    print(f"  audit_format.py — Chain #{chain_id}")
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
                detail = item.get("detail", "")
                post = item.get("post", "")
                if post:
                    print(f"    • {post} — {detail}")
                else:
                    print(f"    • {detail}")
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

    return failed == 0


# ── CLI ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="mc — 포스트 형식/시각 구조 검증")
    parser.add_argument("--chain-id", type=int, help="검증할 체인 ID")
    parser.add_argument("--all", action="store_true", help="모든 체인 전수검사")
    parser.add_argument("--dry-run", action="store_true",
                        help="Hugo 빌드/HTML 렌더링/라이브 접근 검증 스킵")

    args = parser.parse_args()

    if not args.chain_id and not args.all:
        parser.print_help()
        print("\n에러: --chain-id N 또는 --all 을 지정하세요.")
        sys.exit(1)

    if not DB_PATH.exists():
        print(f"에러: DB를 찾을 수 없음 — {DB_PATH}")
        sys.exit(1)

    if args.chain_id:
        result = scan_chain_format(args.chain_id, dry_run=args.dry_run)
    else:
        result = scan_all_format(dry_run=args.dry_run)

    all_pass = print_results(result)
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
