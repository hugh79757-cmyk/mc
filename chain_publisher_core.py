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
from pathlib import Path
from datetime import datetime

from mc_paths import ensure_mde2_on_path, load_config, CHAIN_CONFIG_PATH

ensure_mde2_on_path()

from app.services.r2_uploader import get_r2_config, upload_all_images, HUGO_R2_DOMAINS
from chain_db import check_duplicate, log_publish
from chain_models import (
    CleanedDraft, DeployValidationError, BodyExtractionError,
    ImageGenerationError, Result, ErrorCategory,
)


logger = logging.getLogger(__name__)


R2_IMAGE_DOMAINS = ("r2.dev", "img.")


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

    allowed_lines = []
    in_code_block = False

    for line in body.split("\n"):
        stripped = line.strip()

        if stripped.startswith("```"):
            lang = stripped[3:].strip()
            if lang.lower() == "json":
                try:
                    code_content = ""
                    temp_lines = []
                    for inner_line in body.split("\n"):
                        temp_lines.append(inner_line)
                    raise BodyExtractionError(
                        "JSON 코드 펜스는 본문에서 허용되지 않습니다. "
                        "AI 메타데이터는 parse_ai_output()에서 이미 추출되어야 합니다."
                    )
                except BodyExtractionError:
                    in_code_block = not in_code_block
                    continue
            else:
                in_code_block = not in_code_block
                allowed_lines.append(line)
                continue

        if in_code_block:
            allowed_lines.append(line)
            continue

        if not stripped:
            allowed_lines.append("")
            continue

        is_heading = bool(re.match(r'^#{1,6}\s', stripped))
        is_list = bool(re.match(r'^[-*+]\s|^\d+\.\s', stripped))
        is_table = bool(re.match(r'^\||^[-|:\s]+$', stripped))
        is_image = bool(re.match(r'!\[.*?\]\(https?://', stripped))
        is_link = bool(re.match(r'\[.*?\]\(https?://', stripped))
        is_html_comment = stripped.startswith("<!--")
        is_html_tag = bool(re.search(r'<(?:div|span|meta|script|ins|link|p |a |table|blockquote|figure|del)[\s>/]', stripped))
        is_raw_json = stripped.startswith("{") and ("image_type" in stripped or "chart_type" in stripped)

        if is_html_comment or is_html_tag or is_raw_json:
            continue

        if is_heading or is_list or is_table or is_image or is_link:
            allowed_lines.append(line)
            continue

        allowed_lines.append(line)

    clean_body = "\n".join(allowed_lines)
    clean_body = re.sub(r'\n{3,}', '\n\n', clean_body).strip()

    if not clean_body:
        raise BodyExtractionError("본문에서 유효한 마크다운 요소를 찾을 수 없습니다")

    return CleanedDraft(frontmatter=frontmatter, body=clean_body)


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

    html_comment = re.search(r'<!--.*?-->', content, re.DOTALL)
    if html_comment:
        raise DeployValidationError(
            f"index.md에 HTML 주석 잔류: {html_comment.group()[:60]}"
        )

    html_tag = re.search(
        r'<(?:div|span|meta|script|ins|link|p |a |table|blockquote|figure|del)[\s>/]',
        content,
    )
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
    ) -> tuple:
        """
        blog_key의 publisher_type에 따라 분기.
        Returns: (published_url, publish_method, file_path)
        """
        blog_cfg = self.get_blog(blog_key)
        ptype = blog_cfg.get("publisher_type", "manual")

        if ptype == "hugo":
            return self._publish_hugo(blog_cfg, draft_md, slug, title, labels)
        elif ptype == "blogger":
            return self._publish_blogger(blog_cfg, draft_md, slug, title, labels)
        else:
            return self._publish_manual(blog_cfg, draft_md, slug, title)

    # ── Hugo publish (mde2 패턴) ────────────────────────────────────────

    def _publish_hugo(
        self, blog_cfg: dict, draft_md: str, slug: str, title: str,
        labels: list = None,
    ) -> tuple:
        """Hugo 사이트에 발행: R2 이미지 업로드 + 파일 복사 + hugo build + wrangler deploy"""
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
            _row = _conn.execute(
                "SELECT id, image_meta FROM chain_posts WHERE slug = ?",
                (slug,),
            ).fetchone()
            _conn.close()

            if not _row:
                raise DeployValidationError(f"chain_posts에 slug 없음: {slug}")
            _post_id = _row["id"]
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
                    _res = _gen_thumb(title=title, keyword=_kw, slug=slug)
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
                    from image.pollinations_client import generate_image as _gen_photo
                    _photo_result = _gen_photo(_img_keyword, slug=slug)
                    if not _photo_result.ok:
                        _err = _photo_result.error
                        if _err.category in (ErrorCategory.TRANSIENT, ErrorCategory.RATE_LIMITED):
                            logger.warning(f"[Hugo] Photo 생성 일시적 실패 (재시도 대상): {_err.message}")
                        raise ImageGenerationError(
                            f"Photo 생성 실패: {slug} (image_keyword={_img_keyword}, error={_err.message})"
                        )
                    _photo_path = _photo_result.value
                    if Path(_photo_path).exists():
                        from chain_db import update_content_image as _db_update_content
                        _db_update_content(_post_id, str(_photo_path), "pollinations")
                        shutil.copy2(_photo_path, assets_dir / Path(_photo_path).name)
                        logger.info(f"[Hugo] photo content_image 생성: {_photo_path}")

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
            if "date" not in _fm_fields:
                _fm_fields["date"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")
            if r2_thumb_url:
                _fm_fields["featureimage"] = f'"{r2_thumb_url}"'

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
                # 프론트매터 보존: 본문만 정제(sanitize)하고 _fixed 에 조립된 FM 블록을 재결합.
                # FM을 버리면 no-FM 파일이 되어 Blowfish/PaperMod 테마가 페이지를 빌드에서 제외함(404).
                _fm_match = re.search(r'^---\n.*?\n---\n', _fixed, re.DOTALL)
                _fm_block = _fm_match.group(0) if _fm_match else ""
                text = _fm_block + cleaned.body if _fm_block else cleaned.body
            except BodyExtractionError as e:
                logger.error(f"본문 추출 실패: {e}")
                return ("", "hugo", "")
            index_md.write_text(text, encoding="utf-8")

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
                logger.error(f"배포 검증 실패: {e}")
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
            body = cleaned.body
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
                r2_prefix = r2_prefix or "images/informationhot"
                r2_domain = r2_domain or "https://img.informationhot.kr"

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