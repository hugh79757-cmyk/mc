"""
chain_publisher_core.py — 발행 코어 (Phase 3) - mde2 패턴 적용

draft_md를 실제 사이트에 발행하고 published_url 반환.
blog_key의 publisher_type에 따라 Hugo/Blogger/Manual 분기 처리.
"""

import os
import re
import shutil
import json
import subprocess
import tempfile
import logging
import time
import urllib.request
import urllib.error
import urllib.parse
import yaml
from pathlib import Path
from datetime import datetime
from typing import List

from mc.cta import replace_ai_cta, detect_ai_cta
from mc.leak_defense import strip_leaks, strip_frontmatter_meta_leaks, get_plan_text_patterns  # Phase 35: 발행 safety net + frontmatter 메타 릭 방어; Phase 36: 파손 초안 게이트
from mc_paths import load_config, CHAIN_CONFIG_PATH

from frontmatter_utils import ensure_frontmatter  # noqa: F401 — frontmatter 처리 단일 진실 공급원 (Phase 26)
from url_utils import extract_domain  # noqa: F401 — URL 처리 단일 진실 공급원 (Phase 26)

from constants import (  # noqa: F401 — 상수 단일 진실 공급원 (Phase 26)
    AUTHORITY_DOMAINS, SKIP_DOMAINS, HTML_TAG_RE, R2_IMAGE_DOMAINS,
)

from image.r2_uploader import get_r2_config, upload_all_images, HUGO_R2_DOMAINS
from chain_db import check_duplicate, log_publish
from chain_models import (
    CleanedDraft, DeployValidationError, BodyExtractionError,
    ImageGenerationError, Result, ErrorCategory,
)

import markdown_processor  # noqa: E402 — Phase 26 W4: MarkdownProcessor 파이프라인 위임 (03-04)


logger = logging.getLogger(__name__)


def _request_safe_url(url: str) -> str:
    """HTTP 요청용 URL로 변환하되 host와 기존 percent-encoding은 보존한다."""
    parts = urllib.parse.urlsplit(url)
    safe_path = urllib.parse.quote(parts.path, safe="/%:@!$&'()*+,;=-._~")
    safe_query = urllib.parse.quote(parts.query, safe="=&%:@/?+!$'()*+,;=-._~")
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, safe_path, safe_query, ""))


def _check_url_accessible(url: str) -> None:
    """HEAD 요청으로 URL 접근 가능 여부를 확인한다. 불가능 시 DeployValidationError."""
    try:
        _safe_url = _request_safe_url(url)
        _head_req = urllib.request.Request(_safe_url, method="HEAD")
        with urllib.request.urlopen(_head_req, timeout=10) as _head_resp:
            if _head_resp.status >= 400:
                raise DeployValidationError(
                    f"featureimage HEAD 응답 오류 ({_head_resp.status}): {url}"
                )
    except urllib.error.HTTPError as _he:
        raise DeployValidationError(
            f"featureimage 접근 불가 (HTTP {_he.code}): {url}"
        ) from _he
    except urllib.error.URLError as _ue:
        raise DeployValidationError(
            f"featureimage 연결 실패: {url} ({_ue.reason})"
        ) from _ue
    except DeployValidationError:
        raise
    except Exception as _e:
        logger.warning(f"[verify] featureimage HEAD 검증 스킵 (네트워크 오류): {_e}")


def _validate_hugo_frontmatter_text(text: str) -> None:
    """발행 파일 저장 전 frontmatter를 YAML로 한 번만 검증한다."""
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not match:
        raise DeployValidationError("frontmatter opener/closer 누락")
    try:
        data = yaml.safe_load(match.group(1))
    except Exception as exc:
        raise DeployValidationError(f"frontmatter YAML 파싱 실패: {exc}") from exc
    if not isinstance(data, dict) or not data.get("title") or not data.get("slug"):
        raise DeployValidationError("frontmatter 필수 필드(title/slug) 누락")


# R2_IMAGE_DOMAINS / HTML_TAG_RE 정의는 constants.py 로 이동 (단일 진실 공급원)


def _extract_clean_body(raw: str) -> CleanedDraft:
    """
    흰색 목록(whitelist) 방식: 유효한 마크다운 요소만 추출.
    frontmatter와 body를 분리하여 반환.
    허용: ATX 헤딩, 단락, 리스트, 표, 코드 펜스(非JSON), 이미지, 링크
    거부: HTML 주석, <meta>/<script>/<div>, raw JSON, CTA 블록
    """
    frontmatter = ""
    body = raw

    if raw.lstrip().startswith("---"):
        rest = raw[3:].lstrip("\n")
        closer = re.search(r'^---\s*$', rest, re.MULTILINE)
        if closer:
            frontmatter = rest[:closer.start()]
            body = rest[closer.end():].lstrip("\n")
        else:
            # closer 없는 malformed frontmatter: 첫 빈 줄을 경계로 분리
            lines = rest.split("\n")
            fm_lines = []
            body_start = 0
            for i, line in enumerate(lines):
                stripped = line.strip()
                if not stripped:
                    body_start = i + 1
                    break
                if re.match(r'^[a-zA-Z_][\w]*\s*:', stripped):
                    fm_lines.append(stripped)
                    body_start = i + 1
                else:
                    body_start = i
                    break
            frontmatter = "\n".join(fm_lines)
            body = "\n".join(lines[body_start:]).lstrip("\n")

    # 헬퍼: 중괄호 깊이 카운팅으로 JSON 블록(메타 키 포함) 탐지
    def _is_json_block_with_meta(lines: List[str], idx: int) -> bool:
        """lines[idx:]부터 중괄호 깊이 카운팅으로 JSON 블록 완성 여부 및 메타 키 포함 여부 판단"""
        depth = 0
        block_lines = []
        for j in range(idx, min(len(lines), idx + 100)):  # 최대 100줄 앞까지
            l = lines[j]
            block_lines.append(l)
            for ch in l:
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
            if depth == 0 and block_lines:
                block_text = "\n".join(block_lines)
                if '"image_type"' in block_text or '"chart_type"' in block_text:
                    try:
                        json.loads(block_text)
                        return True
                    except (json.JSONDecodeError, TypeError):
                        return False
            elif depth < 0:
                break
        return False

    allowed_lines = []
    in_code_block = False
    skip_json_block = False
    skip_raw_json_block = False
    raw_json_depth = 0

    lines = body.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # 코드 펜스 JSON 블록 스킵 중
        if skip_json_block:
            if stripped.startswith("```"):
                skip_json_block = False
            i += 1
            continue

        # 일반 코드 블록 토글
        if stripped.startswith("```"):
            lang = stripped[3:].strip()
            if lang.lower() == "json":
                skip_json_block = True
                i += 1
                continue
            else:
                in_code_block = not in_code_block
                allowed_lines.append(line)
                i += 1
                continue

        if in_code_block:
            allowed_lines.append(line)
            i += 1
            continue

        if not stripped:
            allowed_lines.append("")
            i += 1
            continue

        is_heading = bool(re.match(r'^#{1,6}\s', stripped))
        is_list = bool(re.match(r'^[-*+]\s|^\d+\.\s', stripped))
        is_table = bool(re.match(r'^\||^[-|:\s]+$', stripped))
        is_image = bool(re.match(r'!\[.*?\]\(https?://', stripped))
        is_link = bool(re.match(r'\[.*?\]\(https?://', stripped))
        is_html_comment = stripped.startswith("<!--")
        is_html_tag = bool(HTML_TAG_RE.search(stripped))

        # 줄 단위 → 블록 단위 JSON 탐지로 강화
        is_raw_json = _is_json_block_with_meta(lines, i)

        if is_html_comment or is_html_tag or is_raw_json:
            # raw JSON 블록인 경우 블록 끝까지 스킵
            if is_raw_json:
                skip_raw_json_block = True
                raw_json_depth = 0
                # 현재 줄부터 중괄호 카운팅으로 블록 끝 찾기
                for j in range(i, min(len(lines), i + 100)):
                    l = lines[j]
                    for ch in l:
                        if ch == '{':
                            raw_json_depth += 1
                        elif ch == '}':
                            raw_json_depth -= 1
                    if raw_json_depth == 0:
                        i = j + 1
                        skip_raw_json_block = False
                        break
                else:
                    i += 1
                continue
            i += 1
            continue

        if is_heading or is_list or is_table or is_image or is_link:
            allowed_lines.append(line)
            i += 1
            continue

        allowed_lines.append(line)
        i += 1

    clean_body = "\n".join(allowed_lines)
    clean_body = re.sub(r'\n{3,}', '\n\n', clean_body).strip()

    if not clean_body:
        raise BodyExtractionError("본문에서 유효한 마크다운 요소를 찾을 수 없습니다")

    return CleanedDraft(frontmatter=frontmatter, body=clean_body)


# BUG-006 (Phase 36 T3): 파손 초안(계획텍스트 대부분) 발행 선차단 비율 게이트.
# draft_md 본문 라인 중 계획텍스트 특유 지시 문구 매칭 라인 비율이 이 값을
# 초과하면 발행 중단. 실측: 10006 52.2%, 10007 34.8%, 정상 초안 0% (conftest 샘플).
PLAN_TEXT_RATIO_THRESHOLD = 0.20


def check_plan_text_ratio(
    draft_md: str, threshold: float = PLAN_TEXT_RATIO_THRESHOLD
) -> dict:
    """draft_md 계획텍스트(지시 문구) 밀도 검사 (BUG-006).

    frontmatter를 제외한 본문의 비어있지 않은 라인 중, 계획텍스트 특유 지시
    문구(get_plan_text_patterns: reasoning_leak.ultra_high_signals + plan_text_gate)
    에 매칭하는 라인 수 / 전체 라인 수 비율을 계산한다.

    Args:
        draft_md: 발행할 원본 초안 마크다운.
        threshold: 차단 임계 비율 (기본 PLAN_TEXT_RATIO_THRESHOLD).

    Returns:
        {
            "ratio": float,          # 매칭 라인 비율 (0.0~1.0)
            "matching_lines": int,   # 매칭된 라인 수
            "total_lines": int,      # 검사 대상(비어있지 않은) 본문 라인 수
            "blocked": bool,         # ratio > threshold
            "matches": list[str],    # 매칭 라인 샘플 (최대 10개)
        }
    """
    _patterns = get_plan_text_patterns()
    _body_lines = []
    _in_fm = False
    for _raw_line in (draft_md or "").splitlines():
        _stripped = _raw_line.strip()
        if _stripped == "---":
            _in_fm = not _in_fm
            continue
        if _in_fm:
            continue
        if _stripped:
            _body_lines.append(_raw_line)

    _total = len(_body_lines)
    _matching = [
        ln for ln in _body_lines
        if any(_pat.search(ln) for _pat in _patterns)
    ]
    _ratio = (len(_matching) / _total) if _total else 0.0
    return {
        "ratio": round(_ratio, 4),
        "matching_lines": len(_matching),
        "total_lines": _total,
        "blocked": _ratio > threshold,
        "matches": _matching[:10],
    }


def _write_stage_log(stage: str, slug: str, stdout: str, stderr: str) -> None:
    """발행 단계별 stdout/stderr를 logs/에 파일로 보존 (관측성 확보).

    성공/실패 구분 없이 항상 기록 — 실패 재현 시 원인 추적용.
    """
    try:
        _log_dir = Path(__file__).resolve().parent / "logs"
        _log_dir.mkdir(parents=True, exist_ok=True)
        _ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        _p = _log_dir / f"{stage}_{slug}_{_ts}.log"
        _p.write_text(
            f"=== STDOUT ===\n{stdout or ''}\n\n=== STDERR ===\n{stderr or ''}\n",
            encoding="utf-8",
        )
    except Exception:
        pass


def _verify_before_deploy(hugo_path: Path, slug: str, image_meta: dict = None) -> None:
    """
    2단계 검증 게이트:
      1단계: 소스 index.md 검증 (JSON/HTML주석/CTA/featureimage/chart데이터)
      2단계: Hugo 빌드 산출물 HTML 검증 (광고 수/깨진 이미지/오염 태그)
    검증 실패 시 DeployValidationError 발생 → 배포 중단.
    """
    target_dir = hugo_path / "content" / "posts" / slug
    index_md = target_dir / "index.md"

    if not index_md.exists():
        raise DeployValidationError(f"index.md 없음: {index_md}")

    content = index_md.read_text(encoding="utf-8")

    json_fence = re.search(r'```json\s*\n?\{', content)
    if json_fence:
        raise DeployValidationError("index.md에 JSON 코드 펜스 잔류")

    # Phase 19: also catch bare JSON (fence stripped but content remains)
    bare_json = re.search(r'(?<!\`)\n\s*\{\s*"image_type"', content)
    if bare_json:
        raise DeployValidationError(
            f"index.md에 bare JSON 잔류: {bare_json.group()[:60]}"
        )

    html_comment = re.search(r'<!--.*?-->', content, re.DOTALL)
    if html_comment:
        raise DeployValidationError(
            f"index.md에 HTML 주석 잔류: {html_comment.group()[:60]}"
        )

    html_tag = HTML_TAG_RE.search(content)
    if html_tag:
        # W3(card_injector shortcode 전환) 완료 전까지 WARNING으로 운영
        logger.warning(
            f"[verify] index.md에 HTML 태그 잔류 (W3 완료 후 ERROR로 승격): {html_tag.group()[:60]}"
        )

    featureimage_match = re.search(r'^featureimage:\s*["\']?(.*?)["\']?\s*$', content, re.MULTILINE)
    if featureimage_match:
        fi_url = featureimage_match.group(1).strip()
        if not fi_url:
            raise DeployValidationError("featureimage가 빈 값")
        if not fi_url.startswith("http"):
            raise DeployValidationError(f"featureimage가 유효한 URL이 아님: {fi_url}")
        from urllib.parse import urlparse
        _fi_host = (urlparse(fi_url).hostname or "").lower()
        _allowed_proxy_hosts = {
            "img.rotcha.kr",
            "img-issue.techpawz.com",
            "img.techpawz.com",
        }
        if not any(domain in fi_url for domain in R2_IMAGE_DOMAINS) and _fi_host not in _allowed_proxy_hosts:
            raise DeployValidationError(
                f"featureimage가 R2 도메인이 아님: {fi_url} "
                f"(허용 접두사: {', '.join(R2_IMAGE_DOMAINS)}; 허용 호스트: {', '.join(sorted(_allowed_proxy_hosts))})"
            )
        # featureimage 재검증: HEAD 요청으로 R2 URL 접근 가능 확인
        _check_url_accessible(fi_url)

    if image_meta:
        if image_meta.get("chart_type") and not image_meta.get("chart_data"):
            raise DeployValidationError("chart_type 설정됨 but chart_data 비어있음")

    logger.info(f"[verify] 소스 검증 통과: {slug}")

    html_output = hugo_path / "public" / "posts" / slug / "index.html"
    if not html_output.exists():
        alt_path = hugo_path / "public" / slug / "index.html"
        if alt_path.exists():
            html_output = alt_path
        else:
            logger.warning(f"[verify] Hugo 빌드 산출물 없음, 산출물 검증 스킵: {html_output}")
            return

    rendered = html_output.read_text(encoding="utf-8")

    ad_slot_count = len(re.findall(r'class=["\']ad-(?:incontent|bottom|slot)', rendered))
    if ad_slot_count > 3:
        raise DeployValidationError(
            f"Hugo 산출물에 광고 슬롯 {ad_slot_count}개 — 허용치(3개) 초과"
        )

    image_refs = re.findall(r'src=["\']([^"\']+)["\']', rendered)
    broken_count = 0
    for ref in image_refs:
        if ref.startswith("http") or ref.startswith("data:"):
            continue
        ref_path = hugo_path / "public" / ref.lstrip("/")
        if not ref_path.exists():
            broken_count += 1
            logger.warning(f"[verify] 깨진 이미지 참조: {ref}")
    if broken_count > 0:
        raise DeployValidationError(f"산출물에 깨진 이미지 참조 {broken_count}개")

    json_residue = re.search(r'```json|image_type|chart_type|"image_keyword"', rendered)
    if json_residue:
        raise DeployValidationError(
            f"Hugo 산출물에 JSON 잔류: {json_residue.group()[:40]}"
        )

    logger.info(f"[verify] 산출물 검증 통과: {slug}")


# ── Wrangler 실행 헬퍼 ───────────────────────────────────────────────────────

def _get_wrangler_cmd(args: list) -> list:
    """
    wrangler 실행 커맨드를 반환합니다.
    brew/npm 설치 방식에 관계없이 node + wrangler.js 직접 호출로
    [Errno 2] wrangler.real 오류를 완전히 우회합니다.

    우선순위:
      1. npm 글로벌 wrangler.js  (/opt/homebrew/lib/node_modules/wrangler/bin/wrangler.js)
      2. brew wrangler.js        (libexec 하위 rglob 탐색)
      3. npx wrangler            (폴백)
      4. wrangler 직접           (최후 폴백)
    """
    node_bin = shutil.which("node") or "/opt/homebrew/bin/node"

    # 1순위: npm 글로벌 설치 경로 (npm install -g wrangler)
    npm_wrangler_js = Path("/opt/homebrew/lib/node_modules/wrangler/bin/wrangler.js")
    if npm_wrangler_js.exists() and Path(node_bin).exists():
        return [node_bin, str(npm_wrangler_js)] + args

    # 2순위: brew 설치 경로 탐색 (cloudflare-wrangler formula)
    brew_base = Path("/opt/homebrew/opt/cloudflare-wrangler")
    if brew_base.exists():
        candidates = sorted(brew_base.rglob("wrangler.js"))
        if candidates and Path(node_bin).exists():
            return [node_bin, str(candidates[0])] + args

    # 3순위: npx 폴백
    npx_bin = shutil.which("npx")
    if npx_bin:
        return [npx_bin, "--yes", "wrangler"] + args

    # 4순위: 최후 폴백 (PATH에 있는 wrangler 직접 실행)
    wrangler_bin = shutil.which("wrangler")
    if wrangler_bin:
        return [wrangler_bin] + args

    raise FileNotFoundError(
        "wrangler를 찾을 수 없습니다.\n"
        "해결: npm install -g wrangler"
    )


def _run_wrangler(args: list, cwd: str = None, env: dict = None) -> tuple:
    """
    wrangler 명령 실행 → (returncode, stdout, stderr)
    hugh79757 profile 강제 + 타 계정 env 변수 제거.
    """
    cmd = _get_wrangler_cmd(["--profile", "hugh79757"] + args)

    if env is None:
        env = os.environ.copy()
    # 모든 Cloudflare 계정 관련 env 변수 제거 → hugh79757 profile만 사용
    for _k in list(env.keys()):
        if "CLOUDFLARE" in _k.upper() or "CF_" in _k.upper():
            env.pop(_k, None)
    env["PATH"] = "/opt/homebrew/bin:/opt/homebrew/opt/node/bin:" + env.get("PATH", "")
    logger.info(f"[Wrangler] profile=hugh79757 cmd={' '.join(cmd)}")

    result = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    return result.returncode, result.stdout, result.stderr


class PublisherCore:
    def __init__(self, config: dict = None):
        self.config = config or load_config()
        self._blogger_clients = {}

    # ── Blog lookup ─────────────────────────────────────────

    def get_blog(self, blog_key: str) -> dict:
        site = self.config.get("sites", {}).get(blog_key)
        if not site:
            raise KeyError(f"Unknown blog_key: {blog_key}")
        return site

    # ── Main entry ──────────────────────────────────────────

    def publish_post(
        self,
        blog_key: str,
        draft_md: str,
        slug: str,
        title: str,
        labels: list = None,
        chain_type: str = "depth",
        post_id: int = None,
    ) -> tuple:
        """
        blog_key의 publisher_type에 따라 분기.
        Returns: (published_url, publish_method, file_path)
        """
        blog_cfg = self.get_blog(blog_key)
        ptype = blog_cfg.get("publisher_type", "manual")

        if ptype == "hugo":
            return self._publish_hugo(blog_cfg, draft_md, slug, title, labels, post_id=post_id)
        elif ptype == "blogger":
            return self._publish_blogger(blog_cfg, draft_md, slug, title, labels)
        else:
            return self._publish_manual(blog_cfg, draft_md, slug, title)

    # ── Hugo publish (mde2 패턴) ────────────────────────────────────────

    def _publish_hugo(
        self, blog_cfg: dict, draft_md: str, slug: str, title: str,
        labels: list = None, post_id: int = None,
    ) -> tuple:
        """Hugo 사이트에 발행: R2 이미지 업로드 + 파일 복사 + hugo build + wrangler deploy"""
        # BUG-006 (Phase 36 T3): 파손 초안 발행 선차단 게이트 — draft_md 원문을
        # 정제 파이프라인 이전 최초 지점에서 검사. 계획텍스트 비율이 임계치를
        # 초과하면 이미지 생성/DB 쓰기/Hugo 빌드/배포로 진행되기 전에 차단한다.
        _plan_report = check_plan_text_ratio(draft_md)
        if _plan_report["blocked"]:
            logger.error(
                f"[PLAN-TEXT-GATE] 계획텍스트 비율 {_plan_report['ratio']*100:.1f}% "
                f"(임계치 {PLAN_TEXT_RATIO_THRESHOLD*100:.0f}%) 초과로 발행 차단: {slug} "
                f"(matching={_plan_report['matching_lines']}/{_plan_report['total_lines']})"
            )
            for _plan_line in _plan_report["matches"][:3]:
                logger.error(f"  ⚠ 계획텍스트: {_plan_line[:80]}")
            raise DeployValidationError(
                f"파손 초안 차단 (계획텍스트 {_plan_report['ratio']*100:.1f}% > "
                f"임계치 {PLAN_TEXT_RATIO_THRESHOLD*100:.0f}%): {slug} "
                f"(matching={_plan_report['matching_lines']}/{_plan_report['total_lines']})"
            )

        # 1. 임시 디렉토리에 draft 저장
        with tempfile.TemporaryDirectory() as post_temp_dir:
            post_temp_dir = Path(post_temp_dir)
            draft_path = post_temp_dir / "post.md"
            draft_path.write_text(draft_md, encoding="utf-8")

            hugo_path = Path(blog_cfg["hugo_root"])
            content_dir = blog_cfg.get("content_dir", "content/posts")
            cf_project = blog_cfg.get("cf_pages_project", "")
            theme = blog_cfg.get("theme", "PaperMod")

# 2. 썸네일 보장 + R2 이미지 업로드
            r2_prefix, r2_domain = get_r2_config(str(hugo_path))
            assets_dir = post_temp_dir / "assets"
            assets_dir.mkdir(parents=True, exist_ok=True)

            # DB에서 post 조회 (image_meta JSON으로 통합)
            from chain_db import get_conn, update_thumbnail as _db_update_thumb
            _conn = get_conn()
            if post_id:
                _row = _conn.execute(
                    "SELECT id, step, image_meta FROM chain_posts WHERE id = ? AND slug = ?",
                    (post_id, slug),
                ).fetchone()
            else:
                _row = _conn.execute(
                    "SELECT id, step, image_meta FROM chain_posts WHERE slug = ?",
                    (slug,),
                ).fetchone()
            _conn.close()

            if not _row:
                raise DeployValidationError(f"chain_posts에 slug 없음: {slug}")
            _post_id = _row["id"]
            _step = _row["step"] or 1
            _image_meta_raw = _row["image_meta"]
            if not _image_meta_raw:
                raise DeployValidationError(f"image_meta 누락: slug={slug}")
            _image_meta = json.loads(_image_meta_raw)

            # image_meta JSON에서 모든 값 추출 (레거시 개별 컬럼 대체)
            _thumb_abs = _image_meta.get("thumbnail_path")
            _thumb_src = _image_meta.get("thumbnail_source")
            _kw = _image_meta.get("image_keyword")
            _has_content_image = bool(_image_meta.get("content_image_path"))
            _img_type = _image_meta.get("image_type", "none")
            _chart_type = _image_meta.get("chart_type")
            _img_keyword = _image_meta.get("image_keyword")

            # Phase 7: thumbnail_path 없으면 생성 (멱등성: 이미 있으면 스킵)
            if not _thumb_abs or not Path(_thumb_abs).exists():
                if not _kw:
                    logger.warning(f"[Hugo] image_keyword 없음, 썸네일 생성 스킵: {slug}")
                else:
                    from image.thumbnail import generate_thumbnail as _gen_thumb
                    _res = _gen_thumb(title=title, keyword=_kw, slug=slug, step=_step)
                    if _res:
                        _thumb_abs, _thumb_src = _res
                        if _post_id:
                            _db_update_thumb(_post_id, str(_thumb_abs), _thumb_src)
                    else:
                        logger.warning(f"[Hugo] 썸네일 생성 실패: {slug}")
            else:
                logger.info(f"[Hugo] thumbnail_path 이미 설정, 재생성 스킵: {_thumb_abs}")

            # 썸네일을 assets_dir에 복사 (R2 업로드 대상)
            if _thumb_abs and Path(_thumb_abs).exists():
                shutil.copy2(Path(_thumb_abs), assets_dir / Path(_thumb_abs).name)

            # Phase 8: content_image (chart 또는 photo) — image_meta JSON 기반
            if _post_id and not _has_content_image:
                if _img_type == "chart":
                    _chart_data_raw = _image_meta.get("chart_data")
                    if _chart_type and _chart_data_raw:
                        try:
                            import json as _json
                            from pillow_chart import render_chart
                            from mc_paths import load_config as _load_cfg
                            _cfg = _load_cfg()
                            _chart_data = _chart_data_raw if isinstance(_chart_data_raw, dict) else _json.loads(_chart_data_raw)
                            _font_path = _cfg.get("chart", {}).get("font", "assets/fonts/NotoSansKR-Regular.otf")
                            _chart_path, _chart_src = render_chart(
                                chart_type=_chart_type,
                                chart_data=_chart_data,
                                title=title,
                                slug=slug,
                                font_path=_font_path,
                                config=_cfg,
                            )
                            from chain_db import update_content_image as _db_update_content
                            _db_update_content(_post_id, str(_chart_path), _chart_src)
                            # assets_dir에 복사
                            shutil.copy2(_chart_path, assets_dir / Path(_chart_path).name)
                        except FileNotFoundError as e:
                            logger.error(f"Chart font missing: {e}. Fallback to photo.")
                        except Exception as e:
                            logger.error(f"Chart generation failed: {e}. Fallback to photo.")

                elif _img_type == "photo":
                    _photo_path = None
                    _photo_src = None

                    # Phase 13 R1: try real photo search first
                    try:
                        from image.search_providers import search_body_image
                        _body_result = search_body_image(_kw or title, slug=slug, step=_step)
                        if _body_result:
                            _photo_path, _photo_src = _body_result
                    except Exception:
                        pass  # fall through to Pollinations

                    if not _photo_path:
                        # Fallback: Unsplash/Pexels (Pollinations/Krea 사용 안 함)
                        try:
                            from image.thumbnail import generate_content_image as _gen_photo
                            _photo_result = _gen_photo(_kw or title, slug=slug, step=_step)
                            if _photo_result and _photo_result.ok:
                                _photo_path = _photo_result.value
                                _photo_src = "unsplash"
                        except Exception as _e:
                            logger.warning(f"[Hugo] Photo fallback 실패: {_e}")

                    if not _photo_path:
                        raise ImageGenerationError(
                            f"Photo 생성 실패: {slug} (image_keyword={_img_keyword})"
                        )

                    if _photo_path and Path(_photo_path).exists():
                        from chain_db import update_content_image as _db_update_content
                        _db_update_content(_post_id, str(_photo_path), _photo_src or "pollinations")
                        shutil.copy2(_photo_path, assets_dir / Path(_photo_path).name)
                        logger.info(f"[Hugo] photo content_image 생성: {_photo_path} (source={_photo_src})")

            # Phase 3/7-b: <!--todo:image--> / <!--todo:chart--> 마커 → 실제 이미지 URL로 حل
            # draft_md에 미해결 마커가 있으면 image_url DB 값을 사용하여 assets/에 복사
            if ("<!--todo:image-->" in draft_md or "<!--todo:chart-->" in draft_md) and post_id:
                try:
                    from chain_db import get_post as _db_get_post
                    _db_post = _db_get_post(post_id)
                    _db_image_url = (_db_post or {}).get("image_url", "") if _db_post else ""
                except Exception:
                    _db_image_url = ""
                if _db_image_url:
                    _img_filename = _db_image_url.lstrip("/").replace("images/", "")
                    _src_path = Path("output/images") / _img_filename

                    if _src_path.exists():
                        shutil.copy2(_src_path, assets_dir / _img_filename)
                        # 마커를 실제 이미지 경로로 교체
                        draft_md = draft_md.replace("<!--todo:image-->", f"/images/{_img_filename}")
                        draft_md = draft_md.replace("<!--todo:chart-->", f"/images/{_img_filename}")
                        logger.info(f"[Hugo] 마커 해결: <!--todo:image--> → /images/{_img_filename}")

            # Phase 3/7: 본문 이미지(Pollinations)를 output/images/ → assets_dir 복사
            _output_images = Path("output/images")
            if _output_images.exists():
                for _img_ref in re.findall(r'/images/([\w\-]+\.(?:jpg|jpeg|png|webp))', draft_md):
                    _src = _output_images / _img_ref
                    if _src.exists():
                        shutil.copy2(_src, assets_dir / _img_ref)
                        logger.info(f"[Hugo] 본문 이미지 복사: {_img_ref}")

            url_map = {}
            if r2_prefix and r2_domain:
                url_map = upload_all_images(post_temp_dir, slug, r2_prefix, r2_domain)

            # R2 썸네일 URL 추출 (파일명 기반, 하드코딩 제거)
            r2_thumb_url = None
            if url_map:
                for _ln, _ru in url_map.items():
                    if "thumb" in _ln.lower():
                        r2_thumb_url = _ru
                        break
                if not r2_thumb_url:
                    r2_thumb_url = next(iter(url_map.values()), None)

            if not r2_thumb_url:
                logger.warning(f"[Hugo] R2 썸네일 URL 없음: {slug}")

            # 3. 포스트 번들 디렉토리 생성
            target_dir = hugo_path / content_dir / slug
            target_dir.mkdir(parents=True, exist_ok=True)
            existing_index = target_dir / "index.md"
            if existing_index.exists() and post_id:
                existing_text = existing_index.read_text(encoding="utf-8", errors="replace")
                existing_marker = re.search(r"^mc_post_id:\s*['\"]?(\d+)", existing_text, re.MULTILINE)
                if existing_marker and existing_marker.group(1) != str(post_id):
                    raise DeployValidationError(
                        f"stale Hugo bundle 차단: {existing_index} belongs to post_id={existing_marker.group(1)}"
                    )

            # 구형 평면 파일 정리
            stale_flat = hugo_path / content_dir / f"{slug}.md"
            if stale_flat.exists():
                stale_flat.unlink()
                logger.info(f"[Hugo] 구형 평면 파일 제거: {stale_flat}")

            # 3. draft_md 파싱: frontmatter와 본문 분리 + fields 수정
            _fm_fields = {}
            _rest_body = draft_md
            if draft_md.lstrip().startswith("---"):
                _rest_after_opener = draft_md[3:].lstrip("\n")
                _closer = re.search(r'^---\s*$', _rest_after_opener, re.MULTILINE)
                _fm_lines = _rest_after_opener
                if _closer:
                    _fm_lines = _rest_after_opener[:_closer.start()]
                    _rest_body = _rest_after_opener[_closer.end():].lstrip("\n")
                # Parse FM key:value pairs + locate body start
                _body_start = 0
                _fm_raw_lines = _fm_lines.splitlines(True)
                for _i, _raw_line in enumerate(_fm_raw_lines):
                    _line = _raw_line.strip()
                    if not _line or re.match(r'^[a-zA-Z_][\w]*\s*:', _line):
                        _body_start = _i + 1
                        if _line and ":" in _line:
                            _k, _v = _line.split(":", 1)
                            _fm_fields[_k.strip()] = _v.strip()
                    else:
                        break
                if not _closer:
                    _rest_body = "".join(_fm_raw_lines[_body_start:])
            _rest_body = re.sub(r'^featureimage:\s*["\']*\s*["\']\s*$', '', _rest_body, flags=re.MULTILINE)

            # 수정: draft→false, slug, date, featureimage 강제
            _fm_fields["draft"] = "false"
            _fm_fields["slug"] = f'"{slug}"'
            if post_id:
                _fm_fields["mc_post_id"] = str(post_id)
            if "date" not in _fm_fields:
                _fm_fields["date"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")
            if r2_thumb_url:
                _fm_fields["featureimage"] = f'"{r2_thumb_url}"'

            # SEO 메타 보강: description 150자 제한
            desc = _fm_fields.get("description", "").strip().strip('"').strip("'")
            if desc:
                if len(desc) > 150:
                    logger.warning(f"[SEO] description 150자 초과 ({len(desc)}자): {slug} — 잘라서 저장")
                    desc = desc[:147] + "..."
                _fm_fields["description"] = f'"{desc}"'

            # SEO 메타: images 배열에 og:image URL 포함 (Blowfish/PaperMod 호환)
            if r2_thumb_url:
                _fm_fields["images"] = f'["{r2_thumb_url}"]'

            # frontmatter 재조립
            _new_fm_lines = ["---"]
            for _k, _v in _fm_fields.items():
                _new_fm_lines.append(f"{_k}: {_v}")
            if r2_thumb_url and theme == "PaperMod":
                _new_fm_lines.append("cover:")
                _new_fm_lines.append(f'  image: "{r2_thumb_url}"')
            _new_fm_lines.append("---")
            _fixed = "\n".join(_new_fm_lines) + "\n\n" + _rest_body

            index_md = target_dir / "index.md"
            _validate_hugo_frontmatter_text(_fixed)
            index_md.write_text(_fixed, encoding="utf-8")

            # 4. 본문 이미지 경로 R2 URL로 교체
            text = index_md.read_text(encoding="utf-8")
            if url_map:
                for local_name, r2_url in url_map.items():
                    text = text.replace("/images/" + local_name, r2_url)
                    text = text.replace("assets/" + local_name, r2_url)

            # 본문 이미지 placeholder 교체: <!--todo:image--> / <!--todo:chart--> / <!-- image: desc -->
            # (sanitize보다 먼저 실행 — sanitize가 마커를 삭제하므로)
            _content_img_url = None
            if url_map:
                for _ln, _ru in url_map.items():
                    _low = _ln.lower()
                    if "thumb" not in _low and _ln.endswith((".jpg", ".jpeg", ".png", ".webp")):
                        _content_img_url = _ru
                        break
            if _content_img_url:
                _alt_prefix = (title or "image")[:30]
                def _img_repl(m):
                    _d = m.group(1).strip() if m.lastindex else _alt_prefix
                    return f"![{_d}]({_content_img_url})"
                text = re.sub(r"<!--\s*image:\s*(.*?)\s*-->", _img_repl, text)
                text = re.sub(r"<!--todo:image-->", f"![{_alt_prefix}]({_content_img_url})", text)
                text = re.sub(r"<!--todo:chart-->", f"![{_alt_prefix}]({_content_img_url})", text)

            try:
                cleaned = _extract_clean_body(text)
                # Phase 35: 발행 safety net — reasoning leak 문단 제거 (T4).
                # _clean_markdown_symbols(파이프 이스케이프)보다 먼저 적용해
                # 릭 문단을 본문에서 제거한다 (Phase 35 방향 B 발행 안전망).
                cleaned_body, _rl_report = strip_leaks(cleaned.body, context="body")
                if _rl_report["reasoning_leak"]["removed"] > 0:
                    logger.warning(
                        f"[T4-GATE] reasoning leak 문단 {_rl_report['reasoning_leak']['removed']}건 제거: {slug}"
                    )
                # Phase 13 R2: clean markdown symbols before FM reassembly
                cleaned_body = _clean_markdown_symbols(cleaned_body)
                # Phase 22: SEO - 이미지 alt 텍스트 자동 추가
                cleaned_body = _ensure_image_alt(cleaned_body, title)
                # 프론트매터 보존: 본문만 정제(sanitize)하고 _fixed 에 조립된 FM 블록을 재결합.
                # FM을 버리면 no-FM 파일이 되어 Blowfish/PaperMod 테마가 페이지를 빌드에서 제외함(404).
                # NOTE: _fixed 는 closing "---" 뒤에 개행 2개(\n\n)로 끝나므로, regex도 \n+로 허용
                _fm_match = re.search(r'^---\n.*?\n---\n+', _fixed, re.DOTALL)
                _fm_block = _fm_match.group(0) if _fm_match else ""
                text = _fm_block + cleaned_body if _fm_block else cleaned.body

                # Phase 35: frontmatter 메타 필드(description/title) 릭 방어 —
                # 초고특이도 패턴(계열 1/2/3)을 메타 값에 한정 검사.
                # description: 매칭 시그니처 제거(정화), title: 발행 차단.
                text, _fm_meta_report = strip_frontmatter_meta_leaks(text)
                if _fm_meta_report["blocked"]:
                    _blocked_fields = ",".join(_fm_meta_report["blocked_fields"])
                    logger.error(
                        f"[FM-META-GATE] frontmatter 메타 릭 감지로 발행 차단: {slug} "
                        f"(fields={_blocked_fields}) matches={_fm_meta_report['matches'][:3]}"
                    )
                    raise DeployValidationError(
                        f"frontmatter 메타 릭 차단: {slug} — {_blocked_fields} "
                        f"({_fm_meta_report['matches'][0]['match'][:40]}...)"
                    )
                if _fm_meta_report["removed"] > 0:
                    logger.warning(
                        f"[FM-META-GATE] frontmatter description 릭 정화 {_fm_meta_report['removed']}건: {slug}"
                    )
            except BodyExtractionError as e:
                logger.error(f"본문 추출 실패: {e}")
                return ("", "hugo", "")
            # D8: CTA 텍스트 릭 스캐너 — 본문에 CTA 문구/플레이스홀더 직접 노출 검출
            # Phase 22: mc.cta.detect_ai_cta / replace_ai_cta 사용
            _leaks_found = detect_ai_cta(text)
            if _leaks_found:
                logger.warning(f"[D8-GATE] CTA/placeholder leak detected in {slug} — {len(_leaks_found)} matches")
                for leak in _leaks_found:
                    _ctx = text[max(0, leak['position']-20):leak['position']+len(leak['match'])+20].replace('\n', ' ')
                    logger.warning(f"  ⚠ CTA leak: '{leak['match']}' @ pos {leak['position']} (ctx: ...{_ctx}...)")
                # 자동 제거: AI CTA 문구 제거
                text = replace_ai_cta(text)
                logger.warning(f"[D8-GATE] Auto-removed {len(_leaks_found)} leak(s) from {slug}")
            _validate_hugo_frontmatter_text(text)
            index_md.write_text(text, encoding="utf-8")

            # 4-b. R2 교체 결과를 DB published_md에 저장 (card injection용)
            if post_id:
                try:
                    from chain_db import update_post_published_md
                    update_post_published_md(post_id, text)
                except Exception as _e:
                    logger.warning(f"published_md 저장 실패 (post #{post_id}): {_e}")

            # 5. Hugo 빌드
            hugo_bin = shutil.which("hugo") or "/opt/homebrew/bin/hugo"
            env = os.environ.copy()
            env["PATH"] = "/opt/homebrew/bin:" + env.get("PATH", "")

            # leaf bundle 방지: content/posts/index.md 존재 시 삭제
            rogue = hugo_path / "content" / "posts" / "index.md"
            if rogue.exists():
                rogue.unlink()
                print(f"[guard] Removed rogue index.md from {hugo_path}")

            build = subprocess.run(
                [hugo_bin, "--gc", "--minify"],
                cwd=str(hugo_path),
                env=env,
                capture_output=True,
                text=True,
                timeout=120,
            )
            _write_stage_log("hugo_build", slug, build.stdout, build.stderr)
            if build.returncode != 0:
                raise DeployValidationError(
                    f"Hugo 빌드 실패: returncode={build.returncode}, slug={slug}, stderr={build.stderr[:300]}"
                )

            try:
                _verify_before_deploy(hugo_path, slug, _image_meta)
            except DeployValidationError as e:
                error_msg = str(e)
                if "index.md" in error_msg:
                    stage = "index.md 검증"
                elif "Hugo 산출물" in error_msg:
                    stage = "HTML 산출물 검증"
                else:
                    stage = "검증"
                logger.error(f"배포 검증 실패: {e} | slug={slug} | stage={stage}")
                return ("", "hugo", "")

            # 6. Wrangler 배포
            if cf_project:
                public_dir = hugo_path / "public"
                rc, stdout, stderr = _run_wrangler(
                    ["pages", "deploy", str(public_dir), "--project-name", cf_project, "--commit-dirty=true", "--commit-message", "deploy"],
                    cwd=str(hugo_path),
                )
                _write_stage_log("wrangler_deploy", slug, stdout, stderr)
                if rc != 0:
                    logger.error(f"Wrangler 배포 실패 (rc={rc}): {stderr[:2000]}")
                    return ("", "hugo", "")

            # 7. 발행 로그 기록 (URL 포함)
            blog_id = blog_cfg.get("blog_id", "")
            permalink_pattern = blog_cfg.get("permalink_pattern", "/posts/:slug/")
            published_url = f"{blog_cfg['base_url']}{permalink_pattern.replace(':slug', slug)}"
            log_publish(blog_id, slug, published_url, "hugo")

            return (published_url, "hugo", str(target_dir / "index.md"))

    # ── Blogger publish (mde2 패턴) ─────────────────────────────────────

    def _publish_blogger(
        self, blog_cfg: dict, draft_md: str, slug: str, title: str, labels: list = None
    ) -> tuple:
        """Blogger API로 발행: R2 업로드 + 2-layer dedup + 마크다운 정제"""
        import markdown

        # 1. 중복 체크 (DB 1차 방어)
        blog_id = blog_cfg.get("blog_id", "")
        if check_duplicate(blog_id, slug):
            logger.info(f"[Blogger 중복방지] DB에 이미 발행 기록 있음 — 스킵: {title}")
            return ("", "blogger", "")

        # 2. 마크다운 본문 추출 및 정제
        body = self._strip_frontmatter(draft_md)
        try:
            cleaned = _extract_clean_body(body)
            # Phase 13 R2: clean markdown symbols
            body = _clean_markdown_symbols(cleaned.body)
        except BodyExtractionError as e:
            logger.error(f"Blogger 본문 추출 실패: {e}")
            return ("", "blogger", "")

        # 3. R2 이미지 업로드 (재시도 3회)
        r2_prefix = blog_cfg.get("r2_prefix")
        r2_domain = blog_cfg.get("r2_domain")
        if not r2_prefix or not r2_domain:
            site_name_lower = blog_cfg.get("name", "").lower()
            for key, (prefix, domain) in HUGO_R2_DOMAINS.items():
                if key in site_name_lower:
                    r2_prefix = prefix
                    r2_domain = domain
                    break
            else:
                r2_prefix = r2_prefix or "images/issue-techpawz"
                r2_domain = r2_domain or "https://img.issue.techpawz.com"

        # 임시 디렉토리에 draft 저장
        with tempfile.TemporaryDirectory() as post_temp_dir:
            post_temp_dir = Path(post_temp_dir)
            draft_path = post_temp_dir / "post.md"
            draft_path.write_text(draft_md, encoding="utf-8")

            url_map = {}
            MAX_RETRIES = 3
            for attempt in range(MAX_RETRIES):
                url_map = upload_all_images(post_temp_dir, slug, r2_prefix, r2_domain)
                if url_map:
                    if attempt > 0:
                        logger.info(f"[Blogger] R2 업로드 성공 ({attempt+1}/{MAX_RETRIES}회차): {title}")
                    break
                if attempt < MAX_RETRIES - 1:
                    wait = 2 ** attempt
                    logger.warning(f"[Blogger] R2 업로드 실패 ({attempt+1}/{MAX_RETRIES}), {wait}초 후 재시도...")
                    time.sleep(wait)

        # 4. 본문 이미지 경로 → R2 절대 URL 변환
        if url_map:
            for local_name, r2_url in url_map.items():
                body = body.replace(f"assets/{local_name}", r2_url)
                body = body.replace(local_name, r2_url)
        else:
            logger.warning(f"[Blogger] R2 업로드 모두 실패 — 로컬 이미지 참조 제거: {title}")

        # R2에 업로드되지 않은 로컬 이미지 참조 제거 (깨진 링크 방지)
        all_thumb_names = {"thumbnail.webp", "cover.webp", "thumbnail.png"}
        uploaded = set(url_map.keys())
        missing_thumbs = all_thumb_names - uploaded
        if missing_thumbs:
            for name in missing_thumbs:
                body = re.sub(
                    r'!\[([^\]]*)\]\(\s*' + re.escape(name) + r'\s*\)',
                    '',
                    body
                )
            logger.info(f"[Blogger] 업로드 실패한 썸네일 참조 제거: {missing_thumbs}")

        # assets/ 내 업로드 실패 파일 참조 제거
        body = re.sub(r'!\[([^\]]*)\]\(assets/[^)]+\)', '', body)

        html = markdown.markdown(body, extensions=["tables", "fenced_code"])

        # 5. 썸네일을 HTML 앞에 삽입
        thumb_url = None
        for thumb_name in ["thumbnail.webp", "cover.webp", "thumbnail.png"]:
            if thumb_name in url_map:
                thumb_url = url_map[thumb_name]
                break
        if thumb_url:
            thumb_tag = '<img src="' + thumb_url + '" alt="' + title + '" style="max-width:100%;margin-bottom:20px">'
            html = thumb_tag + "\n" + html

        # 6. Blogger API 인증 및 발행
        try:
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build
        except ImportError:
            logger.error("google-api 패키지 미설치")
            return ("", "blogger", "")

        scopes = ["https://www.googleapis.com/auth/blogger"]
        creds = None
        creds_file = blog_cfg.get("blogger_credentials", "")
        token_path = Path(creds_file).parent / "blogger_token.json" if creds_file else None

        if token_path and token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), scopes)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            elif creds_file and Path(creds_file).exists():
                flow = InstalledAppFlow.from_client_secrets_file(creds_file, scopes)
                creds = flow.run_local_server(port=0)
            else:
                return ("", "blogger", "")
            if token_path:
                token_path.write_text(creds.to_json())

        try:
            service = build("blogger", "v3", credentials=creds)

            # 2차 방어: Blogger API 검색 (동일 제목 게시물 존재)
            try:
                request = service.posts().search(blogId=blog_id, q=title)
                result = request.execute()
                items = result.get("items", [])
                for item in items:
                    existing_title = item.get("title", "").strip()
                    if existing_title == title.strip():
                        logger.info(f"[Blogger API 중복체크] 동일 제목 게시물 존재 — 스킵: {title}")
                        return ("", "blogger", "")
            except Exception as e:
                logger.warning(f"Blogger API 중복 체크 실패: {e}")

            post_body = {"kind": "blogger#post", "title": title, "content": html}
            result = service.posts().insert(blogId=blog_id, body=post_body, isDraft=False).execute()
            post_url = result.get("url", "")

            # 7. 발행 로그 기록
            log_publish(blog_id, slug, post_url, "blogger")

            return (post_url, "blogger", "")
        except Exception as e:
            logger.error(f"Blogger 에러: {str(e)[:200]}")
            return ("", "blogger", "")

    # ── Manual publish ──────────────────────────────────────

    def _publish_manual(
        self, blog_cfg: dict, draft_md: str, slug: str, title: str
    ) -> tuple:
        """수동 발행: HTML 파일 저장 + 클립보드 복사 + URL 입력 대기."""
        html = self._md_to_html(draft_md)
        manual_dir = Path(__file__).resolve().parent / "output" / "manual"
        manual_dir.mkdir(parents=True, exist_ok=True)
        output_path = manual_dir / f"{slug}.html"
        output_path.write_text(html, encoding="utf-8")

        # macOS pbcopy
        try:
            proc = subprocess.Popen(
                ["pbcopy"], stdin=subprocess.PIPE, text=True
            )
            proc.communicate(input=html)
            print(f"  [publisher] 📋 HTML copied to clipboard: {output_path}")
        except FileNotFoundError:
            print(f"  [publisher] 📄 HTML saved to: {output_path}")

        url = input("  [publisher] 발행된 URL 입력: ").strip()
        return (url, "manual", str(output_path))

    # ── Hub page publish (Phase 6) ─────────────────────────

    def publish_hub_page(self, hub_draft: dict) -> tuple:
        """
        허브 페이지 발행: Hugo build + Wrangler deploy.
        hub_draft: { 'content_dir': str, 'slug': str, 'draft_md': str }

        Hugo 빌드 + wrangler pages deploy 실행.
        Returns: (published_url, 'hugo', file_path)
        """
        rotcha_cfg = self.get_blog("rotcha")
        hugo_path = Path(rotcha_cfg["hugo_root"])
        content_dir = hub_draft.get("content_dir", "content/hub")
        slug = hub_draft["slug"]

        target_dir = hugo_path / content_dir / slug
        target_dir.mkdir(parents=True, exist_ok=True)
        index_md = target_dir / "index.md"
        index_md.write_text(hub_draft["draft_md"], encoding="utf-8")

        # Hugo build
        hugo_bin = shutil.which("hugo") or "/opt/homebrew/bin/hugo"
        env = os.environ.copy()
        env["PATH"] = "/opt/homebrew/bin:" + env.get("PATH", "")
        build = subprocess.run(
            [hugo_bin, "--gc", "--minify"],
            cwd=str(hugo_path),
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if build.returncode != 0:
            logger.error(f"[Hub] Hugo build failed: {build.stderr[:300]}")
            return ("", "hugo", "")

        # Wrangler deploy
        cf_project = rotcha_cfg.get("cf_pages_project", "rotcha-blog")
        if cf_project:
            public_dir = hugo_path / "public"
            rc, stdout, stderr = _run_wrangler(
                [
                    "pages", "deploy", str(public_dir),
                    "--project-name", cf_project,
                    "--commit-dirty=true",
                    "--commit-message", "deploy: hub-page",
                ],
                cwd=str(hugo_path),
            )
            if rc != 0:
                logger.error(f"[Hub] Wrangler deploy failed (rc={rc}): {stderr[:2000]}")
                return ("", "hugo", "")

        # URL
        permalink = rotcha_cfg.get("permalink_pattern", "/posts/:slug/")
        published_url = f"{rotcha_cfg['base_url']}/hub/{slug}/"
        blog_id = rotcha_cfg.get("blog_id", "")
        log_publish(blog_id, f"hub-{slug}", published_url, "hugo")

        logger.info(f"[Hub] Published: {published_url}")
        return (published_url, "hugo", str(index_md))

    # ── Content update (카드 주입용) ─────────────────────────

    def update_post_content(
        self,
        blog_key: str,
        post_id_or_path: str,
        new_content: str,
        is_html: bool = False,
    ):
        """발행된 글 본문 업데이트."""
        blog_cfg = self.get_blog(blog_key)
        ptype = blog_cfg.get("publisher_type", "manual")

        if ptype == "hugo":
            hugo_file = blog_cfg.get("hugo_file_path") or post_id_or_path
            if os.path.exists(hugo_file):
                with open(hugo_file, "w", encoding="utf-8") as f:
                    f.write(new_content)
        elif ptype == "blogger":
            html = new_content if is_html else self._md_to_html(new_content)
            client = self._get_blogger_client()
            client.update_post(blog_cfg["blog_id"], post_id_or_path, html)

    # ── Helpers ─────────────────────────────────────────────

    @staticmethod
    def _strip_frontmatter(md: str) -> str:
        """본문에서 Hugo frontmatter (---...---) 제거."""
        if md.startswith("---"):
            end = md.find("---", 3)
            if end != -1:
                return md[end + 3:].strip()
        return md

    def _md_to_html(self, md: str) -> str:
        """마크다운 → HTML 변환."""
        import markdown

        return markdown.markdown(
            md, extensions=["extra", "codehilite", "toc"]
        )

    def _get_blogger_client(self):
        """BloggerClient lazy singleton (blog_id별 캐싱)."""
        from shared.publishers.blogger_client import BloggerClient

        if "_default" not in self._blogger_clients:
            self._blogger_clients["_default"] = BloggerClient()
        return self._blogger_clients["_default"]

    def _git_push(self, repo_path: str):
        """Hugo 사이트 git add/commit/push (카드 주입용)."""
        try:
            subprocess.run(
                ["git", "-C", repo_path, "add", "-A"],
                capture_output=True, timeout=30, check=False,
            )
            subprocess.run(
                ["git", "-C", repo_path, "commit", "-m", "mc: auto-publish"],
                capture_output=True, timeout=30, check=False,
            )
            subprocess.run(
                ["git", "-C", repo_path, "push"],
                capture_output=True, timeout=60, check=False,
            )
        except subprocess.TimeoutExpired:
            print("  [publisher] ⚠️ git push timeout")
        except Exception as e:
            print(f"  [publisher] ⚠️ git push error: {e}")


def _ensure_image_alt(text: str, title: str) -> str:
    """
    이미지 마크다운에서 alt 텍스트가 비어있으면 자동 채우기.

    ![](url) → ![{title[:30]}](url)
    ![alt](url) → 그대로 유지 (이미 alt가 있음)

    Args:
        text: 마크다운 본문
        title: 포스트 제목 (alt 텍스트 생성용)

    Returns:
        alt 텍스트가 보완된 텍스트
    """
    if not title:
        title = "image"

    def repl(m):
        alt = m.group(1)
        url = m.group(2)
        if not alt or alt.strip() == "":
            alt = title[:30]
        return f"![{alt}]({url})"

    return re.sub(r'!\[([^\]]*)\]\((https?://[^)]+)\)', repl, text)


# ── Phase 13 R2: Markdown symbol cleanup ──────────────────────────


def _clean_markdown_symbols(body: str) -> str:
    """
    Clean markdown symbols that would leak as literal text in rendered HTML.
    Operates on body text only (frontmatter already extracted).

    Phase 26 W4 (03-04): 알고리즘 단일 진실 공급원이
    ``markdown_processor.MarkdownProcessor.clean_symbols`` 로 이동되어
    본 함수는 위임(wrapper)만 수행한다. 기존 호출부/동작은 불변.
    """
    return markdown_processor.processor.clean_symbols(body)


def _sanitize_markdown_body(body: str) -> str:
    """발행 전 본문 1차 정제 파이프라인 (MarkdownProcessor.process 위임).

    Phase 26 W4 (03-04) 신설. 심볼 클리닝(_clean_markdown_symbols)만으로는
    커버하지 못하는 펜스 자동 수정 + 프롬프트/CTA 릭 방어까지 포함한
    전체 정제 경로의 진입점. 기존 호출부는 변경하지 않는다.
    (quick 20260801: clean_symbols 내부에서 fix_tables 표 보정이 선행된다 —
    header 다음 separator 누락 시 삽입, header 단독 잘린 빈 표는 제거)

    Args:
        body: 정제할 마크다운 본문 (frontmatter 는 이미 분리된 상태 권장).

    Returns:
        fix_fences → strip_leaks → clean_symbols(+fix_tables) 순서로 정제된 본문.
    """
    return markdown_processor.processor.process(body, leak_context="body")


# ── Phase 26 W4: 설정 JSON-Schema 검증 (03-03) ──────────────────────
# config/schema.yaml (JSON-Schema draft-07) 로 설정 파일을 로드 시점에
# 검증하는 훅. 기존 mc_paths.load_config 동작/호출자는 변경하지 않는다.

class ConfigValidationError(ValueError):
    """설정 파일이 config/schema.yaml 의 JSON-Schema 를 위반할 때 발생."""


def validate_config(config: dict, config_name: str = "chain_config.yaml") -> list:
    """config dict 를 config/schema.yaml 의 해당 서브스키마로 검증.

    Args:
        config: yaml 로 로드된 설정 dict.
        config_name: "prompts.yaml" | "chain_config.yaml" — 적용할
            서브스키마 선택 (그 외 이름은 chain_config 스키마 적용).

    Returns:
        오류 메시지 리스트 (비어 있으면 검증 통과).
    """
    import yaml as _yaml
    import jsonschema
    from mc_paths import CONFIG_DIR

    schema_path = os.path.join(CONFIG_DIR, "schema.yaml")
    with open(schema_path, encoding="utf-8") as _f:
        schema = _yaml.safe_load(_f)

    sub_key = "prompts" if config_name == "prompts.yaml" else "chain_config"
    sub = schema.get(sub_key)
    if sub is None:
        return [f"schema.yaml 에 '{sub_key}' 서브스키마 없음"]

    # jsonschema 4.26+ (referencing) 는 $ref 를 검증 문서 기준으로 해석한다.
    # 서브스키마에 definitions 를 병합해 #/definitions/* 참조가 해석되도록 한다.
    doc = dict(sub)
    doc["definitions"] = schema.get("definitions", {})

    validator = jsonschema.Draft7Validator(doc)
    return [
        f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}"
        for e in sorted(validator.iter_errors(config), key=lambda e: [str(p) for p in e.path])
    ]


def load_and_validate_config(config_name: str = "chain_config.yaml") -> dict:
    """mc_paths.load_config 로 로드한 뒤 schema.yaml 로 검증.

    실패 시 ConfigValidationError 를 발생시킨다 (파일명 + 오류 목록 포함).
    기존 mc_paths.load_config 의 동작/호출자는 변경하지 않는다.
    """
    config = load_config(config_name)
    errors = validate_config(config, config_name)
    if errors:
        detail = "\n".join(f"  - {e}" for e in errors)
        raise ConfigValidationError(
            f"[config] {config_name} 스키마 검증 실패 ({len(errors)}건):\n{detail}"
        )
    return config