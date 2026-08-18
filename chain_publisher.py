"""
mc — 체인 퍼블리셔 CLI (Phase 3)

엔드-투-엔드 파이프라인:
  1. 시드 키워드 → 체인 주제 도출 (chain_deriver.derive_chain)
  2. 각 뎁스별 글 초안 작성 (chain_drafter.draft_chain)
  3. 각 뎁스별 이미지 생성 (image.*)
  4. 역순 발행 + 카드 주입 (chain_publisher_core + chain_card_injector)

사용법:
  python chain_publisher.py --seed "츄니토리"                      # 전체
  python chain_publisher.py --seed "츄니토리" --dry-run            # derive only
  python chain_publisher.py --seed "츄니토리" --draft              # derive+draft
  python chain_publisher.py --seed "츄니토리" --image              # derive+draft+image
  python chain_publisher.py --seed "츄니토리" --publish            # derive→draft→image→publish
  python chain_publisher.py --seed "츄니토리" --publish-interactive # 1개씩 승인
  python chain_publisher.py --seed "츄니토리" --publish-manual     # 수동 발행
  python chain_publisher.py --chain-id 5 --publish                 # 기존 체인 발행
  python chain_publisher.py --chain-id 5 --inject                  # 카드 주입만
  python chain_publisher.py --chain-id 5 --schedule --launchd --hour 9 --minute 0
"""

import argparse
import os
import sys
import time
import urllib.parse
import urllib.request
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from mc_paths import (
    ensure_5000_on_path, load_config, load_prompts, get_chain_blog_key,
    PROMPTS_PATH, DRAFTS_DIR,
)

ensure_5000_on_path()

from shared.ai_writer import generate
from shared.publishers.hugo_writer import _write_hugo_post

import chain_db as db
from chain_deriver import derive_chain
from chain_publisher_core import (
    DeployValidationError, BodyExtractionError, ImageGenerationError
)

# Image package imports
from image import generate_image as img_gen
from image import build_full_prompt as img_build
from image import inject_images_into_draft as img_inject
from image.thumbnail import generate_thumbnail as img_thumb
from image.thumbnail import add_text_overlay

# 스키마 검증 함수 import
from chain_drafter import _validate_draft_schema

# ── 안전장치: 비의도 체인 발행 금지 ──
# 내역: chain 19(킨다·chain20과 slug 중복·photo/2990자·비의도), chain 27(포천·chain28과 slug 중복·photo/2742/3426자·비의도)
# 의도: chain 20(킨다-s3·chart/3770자), chain 28(포천-s1/s2·chart)
_NON_INTENDED_CHAINS: set[int] = {19, 27}


# ── Phase 7: Preflight Check ──

def _preflight_check() -> bool:
    """
    E2E 실행 전 필수 사항 확인.
    False 반환 시 발행 중단.
    """
    from pathlib import Path

    # 1. Unsplash (Primary) — ERROR
    if not os.environ.get('UNSPLASH_ACCESS_KEY'):
        print("ERROR: UNSPLASH_ACCESS_KEY not set in .env")
        print("발급: https://unsplash.com/developers")
        return False

    # 2. Pexels (Fallback 1) — WARN
    if not os.environ.get('PEXELS_API_KEY'):
        print("WARN: PEXELS_API_KEY not set. Fallback: Unsplash→Pollinations.")
        print("발급(선택): https://www.pexels.com/api/")

    # 3. Pollinations (Fallback 2) — 키 불필요, 체크 제외

    # 4. 한글 폰트 — WARN
    font_candidates = [
        Path("assets/fonts/NotoSansKR-Regular.otf"),
        Path("/System/Library/Fonts/PingFang.ttc"),
        Path("/usr/share/fonts/truetype/nanum/NanumGothic.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    ]
    if not any(p.exists() for p in font_candidates):
        print("WARN: No Korean font found. PIL text overlay renders as squares.")
        print("설치: https://fonts.google.com/noto/specimen/Noto+Sans+KR")

    # 5. 차트 폰트 — WARN
    chart_font = load_config().get("chart", {}).get("font", "")
    if chart_font and not Path(chart_font).exists():
        system_fonts = [
            Path("/System/Library/Fonts/PingFang.ttc"),
            Path("/usr/share/fonts/truetype/nanum/NanumGothic.ttf"),
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        ]
        if not any(p.exists() for p in system_fonts):
            print("WARN: No Korean font for chart. image_type=chart will fallback to photo.")

    # 6. output/images/ — 자동 생성
    Path("output/images").mkdir(parents=True, exist_ok=True)

    return True


# ── 이미지 생성 (Legacy) ──


# ── 체인 이미지 생성 ──
from image.thumbnail import _infer_source_from_path

def _write_image_log(post_id: int, slug: str, message: str) -> None:
    """이미지 생성 성공/실패 결과를 logs/에 보존 (관측성)."""
    try:
        import os as _os
        from datetime import datetime as _dt
        _log_dir = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "logs")
        _os.makedirs(_log_dir, exist_ok=True)
        _ts = _dt.now().strftime("%Y%m%d_%H%M%S")
        _p = _os.path.join(_log_dir, f"image_gen_{post_id}_{slug}_{_ts}.log")
        with open(_p, "w", encoding="utf-8") as _f:
            _f.write(message)
    except Exception:
        pass


def _find_disk_image(slug: str):
    """output/images/{slug}_*.webp|.jpg|.png 중 첫 매칭 반환 (디스크-DB 교차확인용). 없으면 None."""
    try:
        from pathlib import Path as _P
        _base = _P(__file__).parent / "output" / "images"
        if not _base.exists():
            return None
        for _pat in (f"{slug}_*.webp", f"{slug}_*.jpg", f"{slug}_*.png"):
            _m = sorted(_base.glob(_pat))
            if _m:
                return _m[0]
        return None
    except Exception:
        return None


use_new_image = False
img_gen = img_build = img_inject = img_thumb = None
try:
    from image import generate_image as img_gen
    from image import build_full_prompt as img_build
    from image import inject_images_into_draft as img_inject
    from image import generate_thumbnail as img_thumb
    use_new_image = True
    print("[publisher] image/ package loaded (local file download)")
except ImportError as e:
    print(f"[publisher] image/ package not found ({e}), using legacy URL")


def _process_post_image(post: dict, blog_key: str, chain_type: str) -> int:
    """단일 포스트 이미지 생성 (ThreadPoolExecutor용). Returns post_id."""
    post_id = post["id"]
    print(f"\n  [publisher] Image — post #{post_id}")

    # 정규 필드(image_meta.content_image_path) 기준 완결 판정 — 반쪽 백필 방지
    _meta_raw = post.get("image_meta")
    _meta = json.loads(_meta_raw) if isinstance(_meta_raw, str) else (_meta_raw or {})
    if _meta.get("content_image_path"):
        print(f"    ↷ 이미지 보유 (post #{post_id}): {_meta.get('content_image_path')} — 스킵")
        return post_id

    _slug = post.get("slug") or f"post-{post_id}"
    # 디스크-DB 교차확인: 파일은 있으나 image_meta.content_image_path 미결속 → 재생성 금지, 백필만
    _disk = _find_disk_image(_slug)
    if _disk:
        _abs = str(_disk)
        db.update_content_image(post_id, _abs, "stock")
        db.update_post_image(post_id, f"/images/{_disk.name}")
        print(f"    ↷ 디스크 파일 백필 (post #{post_id}): {_abs}")
        _write_image_log(post_id, _slug,
                         f"IMAGE BACKFILL post_id={post_id}\ndisk={_abs}\nimage_meta.content_image_path set via update_content_image\n")
        # 백필 경로에서도 본문 이미지 삽입(figure 치환) 수행 — 미수행 시 마커/맨 경로가
        # 그대로 남아 발행 후 raw URL 텍스트로 노출되는 버그 방지.
        if img_inject and post.get("draft_md"):
            _updated = img_inject(
                post["draft_md"], post.get("slug", ""),
                blog_key, post.get("step", 1), post["title"],
            )
            db.update_post_draft(post_id, _updated, post.get("slug", ""))
        return post_id

    if use_new_image:
        full_prompt = img_build(
            post.get("image_keyword", post.get("target_keyword", "")),
            blog_key,
            chain_type=chain_type,
            step=post.get("step", 1),
        )
        # DB image_prompt를 실제 전달값으로 갱신 (W3)
        db.update_post_image_prompt(post_id, full_prompt)

        # Retry with exponential backoff
        max_retries = 3
        base_wait = 2
        image_result = None
        for attempt in range(max_retries):
            image_result = img_gen(full_prompt, slug=_slug)
            if image_result and image_result.ok:
                break
            _err = getattr(image_result, "error", "img_gen returned None/empty")
            if attempt < max_retries - 1:
                wait_time = base_wait * (2 ** attempt)
                print(f"  [publisher] ⚠️ 이미지 생성 실패 (post #{post_id}, attempt {attempt+1}/{max_retries}): {_err}")
                print(f"  [publisher]     Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"  [publisher] ⚠️ 이미지 생성 실패 (post #{post_id}, slug={_slug}): {_err}")
                _write_image_log(post_id, _slug,
                                f"IMAGE GEN FAIL post_id={post_id}\nerror={_err}\nfull_prompt={full_prompt[:500]}\n")
                return post_id

        if not image_result or not image_result.ok:
            return post_id

        image_path = image_result.value
        # Upload content image to R2, then set image_url to thumbnail R2 URL (for og:image)
        try:
            from image.r2_uploader import get_r2_client, _resolve_bucket
            import os
            r2_client = get_r2_client()
            _r2_prefix = {
                "rotcha": "images/rotcha",
                "issue.techpawz": "images/issue-techpawz",
                "techpawz": "images/techpawz",
            }.get(blog_key, f"images/{blog_key}")
            _bucket = _resolve_bucket(_r2_prefix)
            # Upload content image to R2
            _content_key = f"{_r2_prefix}/{_slug}/{image_path.name}"
            with open(image_path, "rb") as f:
                r2_client.put_object(
                    Bucket=_bucket,
                    Key=_content_key,
                    Body=f.read(),
                    ContentType="image/webp"
                )
            content_r2_url = f"{os.getenv('R2_PUBLIC_URL')}/{_content_key}"
            db.update_content_image(post_id, str(image_path), _infer_source_from_path(image_path))
            db.update_post_image(post_id, f"/images/{image_path.name}")
            _write_image_log(post_id, _slug, f"IMAGE GEN OK post_id={post_id}\ncontent_r2={content_r2_url}\n")
        except Exception as e:
            db.update_content_image(post_id, str(image_path), _infer_source_from_path(image_path))
            db.update_post_image(post_id, f"/images/{image_path.name}")
            _write_image_log(post_id, _slug, f"IMAGE GEN OK (R2 upload failed: {e})\n")

        # Generate thumbnail from content image (로컬 파일 재사용, API 호출 없음)
        try:
            print(f"  [publisher] Generating thumbnail from content image for post #{post_id}...")
            thumb_path = add_text_overlay(
                image_path,
                post["title"],
                subtitle=post.get("image_keyword", post.get("target_keyword", "")),
                target_size=(1024, 1024),
            )
            print(f"  [publisher] Thumbnail generated from content image: {thumb_path}")
            # R2 upload (기존 코드 유지 — thumb_key 경로, put_object)
            _thumb_source = _infer_source_from_path(image_path)  # content image과 동일한 소스
            thumb_source = _thumb_source
            from image.r2_uploader import get_r2_client, _resolve_bucket
            import os
            r2_client = get_r2_client()
            _r2_prefix = {
                "rotcha": "images/rotcha",
                "issue.techpawz": "images/issue-techpawz",
                "techpawz": "images/techpawz",
            }.get(blog_key, f"images/{blog_key}")
            _bucket = _resolve_bucket(_r2_prefix)
            thumb_key = f"{_r2_prefix}/{_slug}/{thumb_path.name}"
            with open(thumb_path, "rb") as f:
                r2_client.put_object(
                    Bucket=_bucket,
                    Key=thumb_key,
                    Body=f.read(),
                    ContentType="image/webp"
                )
            thumb_r2_url = f"{os.getenv('R2_PUBLIC_URL')}/{thumb_key}"
            db.update_post_image(post_id, thumb_r2_url)
            meta = json.loads(post.get("image_meta", "{}")) if post.get("image_meta") else {}
            meta["thumbnail_r2_url"] = thumb_r2_url
            meta["thumbnail_source"] = thumb_source
            meta["thumbnail_path"] = str(thumb_path)
            db.update_image_meta(post_id, meta)
            print(f"  [publisher] Thumbnail uploaded to R2: {thumb_r2_url}")
        except Exception as e:
            print(f"  [publisher] ⚠️ Thumbnail generation from content image failed: {e}")
            import traceback
            traceback.print_exc()

        if post.get("draft_md"):
            updated = img_inject(
                post["draft_md"], post.get("slug", ""),
                blog_key, post.get("step", 1), post["title"],
            )
            db.update_post_draft(post_id, updated, post.get("slug", ""))
    else:
        # Pollinations 사용 금지 (손가락 왜곡 등 품질 문제). 스톡(image 패키지)
        # 로드 실패 시 이미지 없이 명시적 실패 처리 — AI 생성 fallback 절대 금지.
        print(f"  [publisher] \u274c 스톡 이미지 모듈(use_new_image) 미로드 "
              f"— post #{post_id} 이미지 생성 건너뜀 (Pollinations 금지)")
        db.update_post_status(post_id, "image_failed",
                              error_log="stock image module unavailable; pollinations disabled")

    return post_id


def generate_chain_images(chain_id: int) -> None:
    chain = db.get_chain(chain_id)
    if not chain:
        print(f"[publisher] Chain #{chain_id} not found")
        return

    config = load_config()
    posts = db.get_chain_posts(chain_id)
    chain_type = chain.get("chain_type", "depth")
    db.update_chain_status(chain_id, "generating")

    # Prepare blog_key for each post
    blog_keys = {}
    for post in posts:
        blog_keys[post["id"]] = get_chain_blog_key(post["depth"])

    print(f"\n  [publisher] Generating images for {len(posts)} posts (parallel)...")
    start_time = time.time()

    post_ids = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(_process_post_image, post, blog_keys[post["id"]], chain_type): post["id"]
            for post in posts
        }
        for future in as_completed(futures):
            post_id = futures[future]
            try:
                result = future.result()
                post_ids.append(result)
            except Exception as e:
                print(f"  [publisher] ⚠️ Post #{post_id} image generation failed: {e}")
                import traceback
                traceback.print_exc()

    elapsed = time.time() - start_time
    print(f"\n  [publisher] Chain #{chain_id} images done in {elapsed:.1f}s (parallel)")

    db.update_chain_status(chain_id, "image_generated")


# ── Hugo 게시 (Legacy) ──

def publish_post(post: dict, body_md: str, image_url: str, config: dict) -> dict:
    blog_key = get_chain_blog_key(post["depth"])
    site_cfg = config["sites"][blog_key]
    site_path = site_cfg["site_path"]
    blog_id = site_cfg["blog_id"]

    category = post.get("category", "일반")
    tags = post.get("tags") or post.get("target_keyword", "")

    if image_url:
        img_md = f'\n\n![{post.get("image_keyword", "image")}]({image_url})\n\n'
        if "<!-- image:" in body_md:
            body_md = body_md.split("<!-- image:")[0] + img_md
        else:
            body_md = img_md + body_md

    slug = post.get("slug") or post.get("image_keyword") or post["title"].lower().replace(" ", "-")

    print(f"  [publisher] Publishing to {blog_key} ({site_path})")
    result = _write_hugo_post(
        blog_cfg={"site_path": site_path, "blog_id": blog_id},
        title=post["title"],
        body_md=body_md,
        slug=slug,
        category=category,
        tags=tags,
        thumbnail_url=image_url if image_url else None,
        is_draft=False,
    )
    return result


# ── Phase 3: 역순 발행 ────────────────────────────────────────────

def _get_blog_for_step(chain_id: int, step: int, config: dict,
                       blog_overrides: dict = None) -> str:
    """step(1/2/3)에 해당하는 blog_key 반환. CLI 오버라이드 우선."""
    if blog_overrides and step in blog_overrides:
        return blog_overrides[step]
    chain = db.get_chain(chain_id)
    chain_type = chain["chain_type"] if chain else "depth"
    mapping = config.get("chain_blog_mapping", {}).get("default", {})
    defaults = mapping.get(chain_type, ["rotcha", "issue.techpawz", "techpawz"])
    return defaults[step - 1] if step <= len(defaults) else "rotcha"


def _validate_chain_post_identity(chain_id: int, posts: list[dict]) -> bool:
    """현재 chain의 seed와 post 메타데이터가 섞이지 않았는지 발행 전에 확인한다."""
    chain = db.get_chain(chain_id)
    seed = str((chain or {}).get("seed") or "").strip()
    mismatches = []
    for post in posts:
        if post.get("chain_id") != chain_id:
            mismatches.append((post.get("id"), "chain_id"))
        target = str(post.get("target_keyword") or "").strip()
        seed_key = " ".join(seed.split())
        target_key = " ".join(target.split())
        same_chain_topic = (
            not seed_key
            or not target_key
            or target_key == seed_key
            or target_key.startswith(seed_key + " ")
        )
        if seed_key and target_key and not same_chain_topic:
            mismatches.append((post.get("id"), f"target_keyword={target}"))
        if not post.get("slug"):
            mismatches.append((post.get("id"), "slug_missing"))
    if mismatches:
        print(f"[mc] BLOCKED: Chain #{chain_id} post identity mismatch: {mismatches}")
        return False
    return True


def publish_chain(chain_id: int, mode: str = "auto",
                  blog_overrides: dict = None,
                  theme_override: str = None,
                  cf_project_override: str = None) -> bool:
    """
    역순(Step 3→2→1) 발행.
    mode: "auto" | "interactive" | "manual"
    theme_override: Hugo 테마 강제 지정 (PaperMod/Blowfish)
    cf_project_override: Cloudflare Pages 프로젝트명 강제 지정
    """
    if chain_id in _NON_INTENDED_CHAINS:
        _intended = {19: 20, 27: 28}
        print(f"[mc] BLOCKED: Chain #{chain_id}는 비의도 체인입니다 "
              f"(의도 체인=#{_intended.get(chain_id)}, "
              f"slug 중복으로 덮어쓰기 방지). 발행을 건너뜁니다.")
        print(f"[mc] 제거하려면 _NON_INTENDED_CHAINS에서 {chain_id}를 삭제하세요.")
        return False
    from chain_publisher_core import PublisherCore

    config = load_config()
    core = PublisherCore(config)

    posts = db.get_chain_posts_ordered(chain_id, direction="desc")
    if not posts:
        print(f"[mc] Chain #{chain_id} has no posts")
        return False
    if not _validate_chain_post_identity(chain_id, posts):
        db.update_chain_status(chain_id, "failed")
        return False

    # 누락 이미지 자동 보완 (기존 체인 발행 시 이미지 생성 누락 방지)
    _missing = [p for p in posts if not p.get("image_url")]
    if _missing:
        print(f"[mc] ⚠️ 이미지 누락 {len(_missing)}건 → 이미지 생성/백필 실행")
        try:
            generate_chain_images(chain_id)
        except Exception as _e:
            print(f"[mc] 이미지 보완 실패 (발행 계속): {_e}")
        posts = db.get_chain_posts_ordered(chain_id, direction="desc")
        if not _validate_chain_post_identity(chain_id, posts):
            db.update_chain_status(chain_id, "failed")
            return False

    print(f"\n{'='*60}")
    print(f"[mc] Publishing chain #{chain_id} (reverse order: 3→2→1)")
    print(f"{'='*60}")

    db.update_chain_status(chain_id, "generating")
    failed_steps = []

    for i, post in enumerate(posts):
        step = post.get("step", 1)
        blog_key = _get_blog_for_step(chain_id, step, config, blog_overrides)
        draft_md = post.get("draft_md", "")
        slug = post.get("slug", f"chain-{chain_id}-s{step}")
        title = post["title"]
        labels = [post.get("target_keyword", ""), post.get("category_guess", "일반")]

        if not draft_md:
            print(f"  [publish] Step {step}: no draft, skipping")
            failed_steps.append(step)
            continue

        print(f"\n  [publish] Step {step} → {blog_key} ({mode})")

        if mode == "interactive":
            input(f"    Press Enter to publish Step {step} to {blog_key}... ")

        # Phase 5: 런타임 오버라이드 적용
        if theme_override or cf_project_override:
            site_cfg = config["sites"].get(blog_key, {})
            if theme_override:
                site_cfg["theme"] = theme_override
            if cf_project_override:
                site_cfg["cf_pages_project"] = cf_project_override
            config["sites"][blog_key] = site_cfg

        try:
            url, method, file_path = core.publish_post(blog_key, draft_md, slug, title, labels, post_id=post["id"])
        except DeployValidationError as e:
            print(f"  [PUBLISH-FAIL] Step {step} ({blog_key}): 배포 검증 실패 — {e}")
            url, method, file_path = "", "hugo", ""
        except BodyExtractionError as e:
            print(f"  [PUBLISH-FAIL] Step {step} ({blog_key}): 본문 추출 실패 — {e}")
            url, method, file_path = "", "hugo", ""
        except ImageGenerationError as e:
            print(f"  [PUBLISH-FAIL] Step {step} ({blog_key}): 이미지 생성 실패 — {e}")
            url, method, file_path = "", "hugo", ""
        except Exception as e:
            print(f"  [PUBLISH-FAIL] Step {step} ({blog_key}): 예기치 않은 오류 — {e}")
            url, method, file_path = "", "hugo", ""

        if url:
            db.update_published_url(post["id"], url, method)
            if file_path:
                db.update_post_published(post["id"], file_path)
            print(f"  [publish] ✅ Step {step} published: {url}")
        else:
            db.update_post_status(post["id"], "failed",
                                  error_log=f"publish failed to {blog_key}")
            failed_steps.append(step)
            print(f"  [publish] Step {step} failed")

    if failed_steps:
        db.update_chain_status(chain_id, "failed")
        print(f"\n[mc] Chain #{chain_id} publish failed; steps={failed_steps}")
        return False

    db.update_chain_status(chain_id, "published" if mode == "auto" else "manual_pending")
    print(f"\n[mc] Chain #{chain_id} publish complete")
    return True


# ── Phase 5: 카드 주입 (draft_md 기반) ──────────────────────────────

def inject_cards_chain(chain_id: int, deploy: bool = True) -> None:
    """3단계 카드 주입: Depth 0→1 다음 글 카드, Depth 2→외부 링크 카드.

    Args:
        chain_id: 대상 체인 ID
        deploy: True면 주입 후 Hugo 빌드 + Wrangler 배포까지 실행.
                False면 파일 쓰기까지만 (batch backfill에서 사용).
    """
    if chain_id in _NON_INTENDED_CHAINS:
        _intended = {19: 20, 27: 28}
        print(f"[mc] BLOCKED: Chain #{chain_id}는 비의도 체인입니다 "
              f"(의도 체인=#{_intended.get(chain_id)}, "
              f"slug 중복으로 덮어쓰기 방지). 카드 주입을 건너뜁니다.")
        return
    from chain_card_injector import CardInjector
    from chain_publisher_core import PublisherCore

    config = load_config()
    injector = CardInjector(config)
    core = PublisherCore(config)

    chain = db.get_chain(chain_id)
    if not chain:
        print(f"[mc] Chain #{chain_id} not found")
        return

    posts = db.get_chain_posts_ordered(chain_id, direction="asc")
    if len(posts) < 2:
        print(f"[mc] Not enough posts for card injection")
        return
    if any(not p.get("published_url") for p in posts):
        print(f"[mc] Card injection blocked: chain #{chain_id} has unpublished posts")
        return

    seed_keyword = chain.get("seed", "")

    print(f"\n{'='*60}")
    print(f"[mc] Injecting cards for chain #{chain_id} ({len(posts)} posts)")
    print(f"{'='*60}")

    injected_blogs = set()
    for i in range(len(posts)):
        post = posts[i]
        step = post.get("step", 1)
        blog_key = _get_blog_for_step(chain_id, step, config)
        direction = chain.get("chain_type", "depth")
        is_last = (i == len(posts) - 1)

        if is_last:
            # Depth 2: 외부 링크 카드 (공신력 우선순위)
            success = injector.inject_into_post(
                publisher_core=core,
                post_id=post["id"],
                next_title="",
                next_url="",
                blog_key=blog_key,
                direction=direction,
                is_last=True,
                seed_keyword=seed_keyword,
            )
            if success:
                db.update_card_injected(post["id"])
                injected_blogs.add(blog_key)
                print(f"  [inject] ✅ Step {step} external link card injected")
            else:
                print(f"  [inject] Step {step}: draft_md missing, skipping")
        else:
            # Depth 0/1: 다음 글 카드
            next_post = posts[i + 1]
            if not next_post.get("published_url"):
                print(f"  [inject] Step {step}: missing next URL, skipping")
                continue

            success = injector.inject_into_post(
                publisher_core=core,
                post_id=post["id"],
                next_title=next_post["title"],
                next_url=next_post["published_url"],
                blog_key=blog_key,
                direction=direction,
                is_last=False,
                seed_keyword=seed_keyword,
            )
            if success:
                db.update_card_injected(post["id"])
                injected_blogs.add(blog_key)
                print(f"  [inject] ✅ Step {step} next card injected")
            else:
                print(f"  [inject] Step {step}: draft_md missing, skipping")

    # Deploy each blog once after all cards are injected
    if deploy and injected_blogs:
        print(f"\n[mc] Deploying {len(injected_blogs)} blog(s) after card injection...")
        _deploy_blogs_after_inject(injected_blogs, config)
    elif not deploy:
        print(f"\n[mc] Card files written (deploy skipped — batch mode).")


def backfill_card_injection() -> None:
    """발행 완료되었으나 카드 주입이 되지 않은 모든 체인에 카드 주입.

    모든 체인을 순회하며 card_injected=0인 포스트가 있는 체인을 찾아
    inject_cards_chain(deploy=False)로 주입만 수행한 후,
    마지막에 블로그별 1회씩 Hugo 빌드 + Wrangler 배포.
    """
    import chain_db as db
    from mc_paths import load_config

    config = load_config()

    # 모든 published/complete 체인 조회
    all_chains = db.get_all_chains()
    target_chains = []
    for c in all_chains:
        cid = c["id"]
        if c["status"] not in ("published", "complete"):
            continue
        posts = db.get_chain_posts_ordered(cid, direction="asc")
        if not posts:
            continue
        # card_injected=0인 포스트가 하나라도 있는 체인만 대상
        if any(not p.get("card_injected") for p in posts):
            target_chains.append(cid)

    if not target_chains:
        print("[mc] 모든 체인에 이미 카드가 주입되어 있습니다.")
        return

    print(f"\n{'='*60}")
    print(f"[mc] Backfill card injection: {len(target_chains)} chains")
    print(f"{'='*60}\n")

    all_injected_blogs = set()
    for cid in target_chains:
        inject_cards_chain(cid, deploy=False)
        # collect blogs from this chain
        posts = db.get_chain_posts_ordered(cid, direction="asc")
        for p in posts:
            step = p.get("step", 1)
            blog_key = _get_blog_for_step(cid, step, config)
            all_injected_blogs.add(blog_key)

    # Single deploy per blog after all injections
    if all_injected_blogs:
        print(f"\n{'='*60}")
        print(f"[mc] Batch deploy: {len(all_injected_blogs)} blog(s)")
        print(f"{'='*60}\n")
        _deploy_blogs_after_inject(all_injected_blogs, config)
        print(f"\n[mc] Backfill complete! {len(target_chains)} chains injected.")
    else:
        print("[mc] No blogs to deploy.")


def smoke_test(chain_id: int) -> dict:
    """
    발행 완료된 체인의 각 포스트 URL에 대해 smoke test 수행.

    검증:
    - HTTP 200 응답
    - <title> 태그 존재
    - og:image 메타태그 존재 → 해당 URL HTTP 200

    실패해도 경고만 출력 (롤백 없음).

    Returns:
        dict: {post_id: {"url": str, "status_code": int, "title_found": bool,
                         "og_image_url": str, "og_image_ok": bool, "overall": "pass"|"fail"}}
    """
    import requests as _requests
    import re as _re

    posts = db.get_chain_posts(chain_id)
    results = {}

    for post in posts:
        url = post.get("published_url")
        if not url:
            detail = {"url": "", "status_code": None, "title_found": False,
                      "og_image_url": None, "og_image_ok": False,
                      "overall": "fail", "error": "missing published_url"}
            results[post["id"]] = detail
            db.update_smoke_test_result(post["id"], "fail", detail)
            print(f"  [smoke] ❌ Post #{post['id']}: no published_url")
            continue

        detail = {"url": url, "status_code": None, "title_found": False,
                  "og_image_url": None, "og_image_ok": False, "error": None}

        try:
            resp = _requests.get(url, timeout=10, allow_redirects=True)
            detail["status_code"] = resp.status_code

            if resp.status_code == 200:
                # <title> 존재 확인
                title_match = _re.search(r'<title[^>]*>(.*?)</title>', resp.text, _re.IGNORECASE | _re.DOTALL)
                detail["title_found"] = bool(title_match and title_match.group(1).strip())

                # og:image URL 추출 및 검증
                og_match = _re.search(
                    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\'](.*?)["\']',
                    resp.text, _re.IGNORECASE
                )
                if og_match:
                    og_url = og_match.group(1)
                    detail["og_image_url"] = og_url
                    try:
                        og_resp = _requests.get(og_url, timeout=10, stream=True)
                        detail["og_image_ok"] = og_resp.status_code == 200
                        og_resp.close()
                    except Exception as e:
                        detail["og_image_ok"] = False
                        detail["error"] = f"og:image fetch failed: {e}"

            overall = "pass" if (resp.status_code == 200 and
                                  detail["title_found"] and
                                  detail["og_image_ok"]) else "fail"

        except Exception as e:
            overall = "fail"
            detail["error"] = str(e)

        detail["overall"] = overall
        results[post["id"]] = detail

        # DB 기록
        db.update_smoke_test_result(post["id"], overall, detail)

        status_icon = "✅" if overall == "pass" else "⚠️"
        print(f"  [smoke] {status_icon} Post #{post['id']}: {url} → {detail['status_code'] if 'resp' in locals() else 'ERR'}, title={'Y' if detail['title_found'] else 'N'}, og:image={'Y' if detail['og_image_ok'] else 'N'}")

    return results


def _deploy_blogs_after_inject(blog_keys: set, config: dict) -> None:
    """카드 주입 후 각 블로그별 Hugo 빌드 + Wrangler 배포 (1회씩)."""
    import subprocess
    import shutil as _shutil

    for blog_key in blog_keys:
        blog_cfg = config.get("sites", {}).get(blog_key, {})
        publisher_type = blog_cfg.get("publisher_type", "manual")
        if publisher_type != "hugo":
            continue

        hugo_root = blog_cfg.get("hugo_root") or blog_cfg.get("site_path")
        if not hugo_root:
            print(f"  [deploy] {blog_key}: hugo_root not found, skipping")
            continue

        cf_project = blog_cfg.get("cf_pages_project", "")
        print(f"  [deploy] {blog_key}: Hugo build + deploy (project={cf_project})")

        # Hugo build
        hugo_bin = _shutil.which("hugo") or "/opt/homebrew/bin/hugo"
        env = os.environ.copy()
        env["PATH"] = "/opt/homebrew/bin:" + env.get("PATH", "")
        build = subprocess.run(
            [hugo_bin, "--gc", "--minify"],
            cwd=hugo_root,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if build.returncode != 0:
            print(f"  [deploy] {blog_key}: Hugo build FAILED: {build.stderr[:200]}")
            continue

        # Wrangler deploy
        if cf_project:
            public_dir = os.path.join(hugo_root, "public")
            from chain_publisher_core import _run_wrangler
            rc, stdout, stderr = _run_wrangler(
                ["pages", "deploy", public_dir, "--project-name", cf_project,
                 "--commit-dirty=true", "--commit-message", "deploy: card-injection"],
                cwd=hugo_root,
            )
            if rc != 0:
                print(f"  [deploy] {blog_key}: Wrangler deploy FAILED: {stderr[:200]}")
            else:
                print(f"  [deploy] {blog_key}: ✅ Deployed")
        else:
            print(f"  [deploy] {blog_key}: no cf_pages_project, build only")


# ── Phase 3: 스케줄러 ────────────────────────────────────────────

def schedule_chain(chain_id: int, use_launchd: bool = False,
                   cron_expr: str = None, hour: int = 9, minute: int = 0) -> None:
    """체인 발행 스케줄 등록."""
    if use_launchd:
        from scheduler import LaunchdManager
        LaunchdManager().add_task(chain_id, hour=hour, minute=minute)
        print(f"[mc] launchd scheduled: Chain #{chain_id} at {hour}:{minute:02d}")
    else:
        from scheduler import CronManager
        cmd = f"cd {os.path.dirname(os.path.abspath(__file__))} && python3 chain_publisher.py --chain-id {chain_id} --publish"
        CronManager().add_task(cmd, cron_expr or "0 9 * * *",
                               description=f"mc-publish-chain-{chain_id}")
        print(f"[mc] Cron scheduled: Chain #{chain_id}")


def schedule_list() -> None:
    """등록된 스케줄 작업 목록."""
    from scheduler import CronManager, LaunchdManager
    cron_tasks = CronManager().list_tasks()
    launchd_tasks = LaunchdManager().list_tasks()
    print("\nCron tasks:")
    for t in cron_tasks:
        print(f"  {t['schedule']} {t['command'][:60]}...")
    print("\nLaunchd tasks:")
    for t in launchd_tasks:
        print(f"  {t['label']}")


def schedule_remove(chain_id: int, use_launchd: bool = False) -> None:
    """스케줄 작업 제거."""
    if use_launchd:
        from scheduler import LaunchdManager
        LaunchdManager().remove_task(f"com.mc.publisher.{chain_id}")
    else:
        from scheduler import CronManager
        cmd = f"cd {os.path.dirname(os.path.abspath(__file__))} && python3 chain_publisher.py --chain-id {chain_id} --publish"
        CronManager().remove_task(cmd)


# ── 워크플로우 ──

def run_chain(seed: str, dry_run: bool = False, draft_only: bool = False,
              image_only: bool = False, chain_type: str = None,
              publish_mode: str = None, blog_overrides: dict = None,
              theme_override: str = None, cf_project_override: str = None,
              use_context: bool = True, force: bool = False) -> int:
    config = load_config()
    chain_id = derive_chain(seed, chain_type=chain_type)
    if not chain_id:
        print("[mc] Chain derivation failed, aborting.")
        return 0

    if dry_run:
        chain = db.get_chain(chain_id)
        print(f"\n[mc] Dry-run — Chain #{chain['id']}: seed='{chain['seed']}', "
              f"type={chain['chain_type']}, status={chain['status']}")
        return chain_id

    from chain_drafter import draft_chain
    print(f"\n{'='*60}\n[mc] Drafting chain #{chain_id}\n{'='*60}\n")
    drafted = draft_chain(chain_id, seed, use_context=use_context)
    print(f"\n[mc] Draft complete: {len(drafted)} posts")

    # 스키마 검증 게이트
    print(f"\n{'─'*60}\n[mc] Validating draft schema...\n{'─'*60}\n")
    validation_passed = True

    for post in drafted:
        draft_md = post.get("draft_md", "")
        meta = post.get("meta")
        if not draft_md:
            print(f"  [ERROR] Post {post.get('step', 'N/A')} has empty draft")
            validation_passed = False
            break

        result, message = _validate_draft_schema(draft_md, meta)
        if result:
            print(f"  [OK] Post {post.get('step', 'N/A')} schema validation passed")
            # Phase 22: 품질 경고가 있으면 DB에 기록
            if message and message.startswith("quality_warning:"):
                warnings = [message.replace("quality_warning: ", "")]
                db.update_quality_warnings(post.get("id"), warnings)
        else:
            print(f"  [ERROR] Post {post.get('step', 'N/A')} schema validation failed: {message}")
            validation_passed = False
            break

    if not validation_passed:
        print(f"\n[ERROR] Schema validation failed for chain #{chain_id}")
        print("[ERROR] Publishing aborted due to schema violations")
        if not draft_only:
            print("Tip: Check draft files for missing H2 headings or image markers")
        return None

    print(f"\n[mc] All posts schema validation passed ✓")

    if draft_only:
        return chain_id

    generate_chain_images(chain_id)
    if image_only:
        return chain_id

    # ── Quality gate (Phase 47) ──────────────────────────────────
    if publish_mode:
        from quality.gate import run_all_checks, GateVerdict
        step_labels = {1: "rotcha", 2: "issue.techpawz", 3: "techpawz"}
        gate_posts = {}
        for post in db.get_chain_posts(chain_id):
            step = post.get("step", 0)
            blog_id = step_labels.get(step, f"step{step}")
            gate_posts[blog_id] = {
                "title": post.get("target_keyword", ""),
                "body_md": post.get("draft_md", ""),
                "html": "",  # not rendered yet; HTML check deferred to post-build
                "category": post.get("category_guess", ""),
            }

        if gate_posts:
            verdict = run_all_checks(str(chain_id), gate_posts)
            print(f"\n[mc] Quality gate: {verdict.action} (score={verdict.total_score})")
            if verdict.violations:
                for blog_id, viols in verdict.violations.items():
                    for v in viols:
                        print(f"  [{blog_id}] {v}")

            if verdict.action == "reject":
                print(f"[mc] Quality gate REJECTED (score {verdict.total_score} < 7.0)")
                print("[mc] Publish aborted. Fix violations and retry.")
                return None
            elif verdict.action == "review" and not force:
                print(f"[mc] Quality gate REVIEW (score {verdict.total_score} 7.0~8.9)")
                print("[mc] 수동 승인 필요. --force 로 강제 발행하거나 위반 사항을 수정하세요.")
                return None
            elif verdict.action == "review" and force:
                print(f"[mc] Quality gate REVIEW but --force enabled, proceeding")

    if publish_mode:
        published_ok = publish_chain(chain_id, mode=publish_mode, blog_overrides=blog_overrides,
                                     theme_override=theme_override, cf_project_override=cf_project_override)
        if not published_ok:
            print(f"[mc] Publish failed for chain #{chain_id}; cards and smoke test blocked")
            return None
        if publish_mode != "manual":
            inject_cards_chain(chain_id)
            # Phase 21: 발행 후 smoke test
            print(f"\n{'─'*60}\n[mc] Running smoke test for chain #{chain_id}\n{'─'*60}\n")
            smoke_test(chain_id)
    else:
        # Legacy full pipeline
        print(f"\n{'='*60}\n[mc] Publishing chain #{chain_id}\n{'='*60}\n")
        posts = db.get_chain_posts(chain_id)
        legacy_failed = []
        for i, post in enumerate(posts):
            post_id = post["id"]
            body_md = post.get("draft_md", "")
            image_url = post.get("image_url", "")
            pub_result = publish_post(post, body_md, image_url, config)
            if pub_result.get("success"):
                hugo_path = pub_result.get("file", "")
                db.update_post_published(post_id, hugo_path)
                print(f"  [publisher] Published: {hugo_path}")
            else:
                err = pub_result.get("error", "Unknown")
                db.update_post_status(post_id, "failed", error_log=err)
                legacy_failed.append(post["step"])
                print(f"  [publisher] Publish failed: {err}")
        if legacy_failed:
            db.update_chain_status(chain_id, "failed")
            print(f"\n[mc] Chain #{chain_id} legacy publish failed; steps={legacy_failed}")
            return None
        db.update_chain_status(chain_id, "completed")
        inject_cards_chain(chain_id)
        # Phase 21: 발행 후 smoke test
        print(f"\n{'─'*60}\n[mc] Running smoke test for chain #{chain_id}\n{'─'*60}\n")
        smoke_test(chain_id)

    print(f"\n{'='*60}\n[mc] Chain #{chain_id} completed!\n{'='*60}\n")
    return chain_id


# ── Phase 6: Loop Funnel ─────────────────────────────────

def cmd_hub(chain_id: int, dry_run: bool = False) -> bool:
    from draft_hub_page import draft_hub_page
    from chain_publisher_core import PublisherCore

    cfg = load_config()
    publisher = PublisherCore(cfg)

    print(f"\n{'='*60}\n[mc] 🌀 Hub page for chain #{chain_id}\n{'='*60}\n")
    ok, hub_slug = draft_hub_page(chain_id)
    if not ok:
        print(f"  [hub] ❌ {hub_slug}")
        return False

    if dry_run:
        hub_path = f"rotcha-blog/content/hub/{hub_slug}/index.md"
        url = f"https://rotcha.kr/hub/{hub_slug}/"
        print(f"  [hub] dry-run: draft at {hub_path}")
        print(f"  [hub] dry-run: would publish to {url}")
        return True

    hub_draft = {
        "content_dir": "content/hub",
        "slug": hub_slug,
        "draft_md": open(
            Path(cfg["sites"]["rotcha"]["hugo_root"])
            / "content" / "hub" / hub_slug / "index.md"
        ).read(),
    }

    url, method, path = publisher.publish_hub_page(hub_draft)
    if not url:
        print(f"  [hub] ❌ Publish failed")
        return False

    loop_chain = db.get_loop_chain(chain_id)
    if loop_chain:
        db.update_loop_chain_status(loop_chain["id"], hub_url=url, status="hub_published")

    print(f"  [hub] ✅ Published: {url}")
    return True


def cmd_spoke(chain_id: int, dry_run: bool = False) -> bool:
    from chain_publisher_core import PublisherCore
    from chain_card_injector import DualCTAInjector

    cfg = load_config()
    publisher = PublisherCore(cfg)
    injector = DualCTAInjector(cfg)

    posts = db.get_chain_posts(chain_id)
    loop_chain = db.get_loop_chain(chain_id)
    if not loop_chain:
        print(f"  [spoke] ❌ No loop chain found for #{chain_id}. Run --hub first.")
        return False

    hub_url = loop_chain.get("hub_url") or f"{cfg['loop']['hub_url_base']}/{loop_chain['hub_slug']}/"
    hub_title = f"{db.get_chain(chain_id)['seed']} — 완벽 가이드 모음"

    success = 0
    for p in posts:
        if p.get("loop_role") != "spoke":
            continue
        if dry_run:
            print(f"  [spoke] dry-run: would inject dual-CTA into post #{p['id']} ({p.get('slug')})")
            success += 1
            continue

        ok = injector.inject_into_post(
            publisher, p["id"], hub_url, hub_title
        )
        if ok:
            success += 1

    print(f"  [spoke] ✅ {success}/{len(posts)} spokes processed")
    return success > 0


def cmd_loop(chain_id: int, dry_run: bool = False) -> bool:
    print(f"\n{'='*60}\n[mc] 🔄 Full loop for chain #{chain_id}\n{'='*60}\n")

    if not cmd_hub(chain_id, dry_run):
        return False
    if not cmd_spoke(chain_id, dry_run):
        return False

    loop_chain = db.get_loop_chain(chain_id)
    if loop_chain:
        db.update_loop_chain_status(loop_chain["id"], status="loop_completed")

    print(f"\n  [loop] ✅ Chain #{chain_id} loop completed (hub + {len(db.get_chain_posts(chain_id))} spokes)")
    return True


# ── CLI ──

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="mc — Manual Chain Publisher")
    parser.add_argument("--seed", type=str, help="Seed keyword")
    parser.add_argument("--chain-id", type=int, help="Existing chain ID")

    # Pipeline stage flags
    parser.add_argument("--dry-run", action="store_true", help="Derive only")
    parser.add_argument("--draft", action="store_true", help="Derive + draft")
    parser.add_argument("--image", action="store_true", help="Derive + draft + image")
    parser.add_argument("--chain-type", choices=["depth", "swallow", "lateral"],
                        help="Force chain direction")

    # Phase 3: Publish flags
    parser.add_argument("--publish", action="store_true", help="Auto publish (reverse order)")
    parser.add_argument("--publish-interactive", action="store_true",
                        help="Publish one by one with confirmation")
    parser.add_argument("--publish-manual", action="store_true",
                        help="Manual publish (HTML + URL input)")
    parser.add_argument("--inject", action="store_true", help="Card injection only (legacy HTML)")

    # Phase 5: New flags
    parser.add_argument("--inject-card", action="store_true",
                        help="Card injection (draft_md based + re-publish)")
    parser.add_argument("--backfill-inject", action="store_true",
                        help="Backfill card injection into all chains missing cards")
    parser.add_argument("--theme-override", type=str,
                        help="Override Hugo theme (PaperMod|Blowfish)")
    parser.add_argument("--cf-pages-project", type=str,
                        help="Override Cloudflare Pages project name")

    # Phase 6: Loop Funnel flags
    parser.add_argument("--loop", action="store_true",
                        help="Full loop: hub + spoke dual-CTA")
    parser.add_argument("--hub", action="store_true",
                        help="Generate and publish hub page only")
    parser.add_argument("--spoke", action="store_true",
                        help="Inject dual-CTA and republish spokes")

    # Phase 7: Search context flags
    parser.add_argument("--search", action="store_true",
                        help="Enable Naver search context for drafting (default)")
    parser.add_argument("--no-search", action="store_true",
                        help="Disable Naver search context")

    parser.add_argument("--blog-step1", type=str, help="Blog key for step 1 (override)")
    parser.add_argument("--blog-step2", type=str, help="Blog key for step 2 (override)")
    parser.add_argument("--blog-step3", type=str, help="Blog key for step 3 (override)")

    # Phase 3: Schedule flags
    parser.add_argument("--schedule", action="store_true", help="Register scheduler")
    parser.add_argument("--schedule-list", action="store_true", help="List scheduled tasks")
    parser.add_argument("--schedule-remove", action="store_true",
                        help="Remove scheduled task")
    parser.add_argument("--cron", type=str, help="Cron expression (default: 0 9 * * *)")
    parser.add_argument("--launchd", action="store_true", help="Use macOS launchd")
    parser.add_argument("--hour", type=int, default=9, help="Schedule hour")
    parser.add_argument("--minute", type=int, default=0, help="Schedule minute")

    # Phase 7: Preflight
    parser.add_argument("--preflight", action="store_true",
                        help="Run preflight check (API keys, font, output dir)")

    args = parser.parse_args()

    # Schedule management
    if args.schedule_list:
        schedule_list()
        sys.exit(0)

    if args.schedule_remove and args.chain_id:
        schedule_remove(args.chain_id, use_launchd=args.launchd)
        sys.exit(0)

    if args.schedule and args.chain_id:
        schedule_chain(args.chain_id, use_launchd=args.launchd,
                       cron_expr=args.cron, hour=args.hour, minute=args.minute)
        sys.exit(0)

    # Card injection only
    if args.inject and args.chain_id:
        inject_cards_chain(args.chain_id)
        sys.exit(0)

    # Phase 6: Loop Funnel routing
    if (args.hub or args.spoke or args.loop) and args.chain_id:
        if args.hub:
            ok = cmd_hub(args.chain_id, args.dry_run)
        elif args.spoke:
            ok = cmd_spoke(args.chain_id, args.dry_run)
        elif args.loop:
            ok = cmd_loop(args.chain_id, args.dry_run)
        sys.exit(0 if ok else 1)

    # Phase 7: Preflight check
    if args.preflight:
        ok = _preflight_check()
        print(f"\n[mc] Preflight: {'PASS' if ok else 'FAIL'}")
        sys.exit(0 if ok else 1)

    # Publish only (existing chain)
    if args.publish and args.chain_id:
        if not _preflight_check():
            print("[mc] Preflight failed. Aborting publish.")
            sys.exit(1)
        blog_overrides = {}
        if args.blog_step1:
            blog_overrides[1] = args.blog_step1
        if args.blog_step2:
            blog_overrides[2] = args.blog_step2
        if args.blog_step3:
            blog_overrides[3] = args.blog_step3
        publish_chain(args.chain_id, mode="auto", blog_overrides=blog_overrides,
                      theme_override=args.theme_override, cf_project_override=args.cf_pages_project)
        inject_cards_chain(args.chain_id)
        sys.exit(0)

    if args.backfill_inject:
        backfill_card_injection()
        sys.exit(0)

    if args.inject_card and args.chain_id:
        inject_cards_chain(args.chain_id)
        sys.exit(0)

    if args.publish_interactive and args.chain_id:
        publish_chain(args.chain_id, mode="interactive")
        inject_cards_chain(args.chain_id)
        sys.exit(0)

    if args.publish_manual and args.chain_id:
        publish_chain(args.chain_id, mode="manual")
        sys.exit(0)

    # Full or partial pipeline
    if args.seed:
        publish_mode = None
        if args.publish:
            publish_mode = "auto"
        elif args.publish_interactive:
            publish_mode = "interactive"
        elif args.publish_manual:
            publish_mode = "manual"

        blog_overrides = {}
        if args.blog_step1:
            blog_overrides[1] = args.blog_step1
        if args.blog_step2:
            blog_overrides[2] = args.blog_step2
        if args.blog_step3:
            blog_overrides[3] = args.blog_step3

        use_context = not args.no_search

        run_chain(
            args.seed,
            dry_run=args.dry_run,
            draft_only=args.draft,
            image_only=args.image,
            chain_type=args.chain_type,
            publish_mode=publish_mode,
            blog_overrides=blog_overrides or None,
            theme_override=args.theme_override,
            cf_project_override=args.cf_pages_project,
            use_context=use_context,
        )
    elif args.chain_id:
        if args.draft:
            from chain_drafter import draft_chain
            chain = db.get_chain(args.chain_id)
            if not chain:
                print(f"Chain #{args.chain_id} not found.")
                sys.exit(1)
            print(f"\n{'='*60}\n[mc] Drafting chain #{args.chain_id}\n{'='*60}\n")
            use_context = not args.no_search
            drafted = draft_chain(args.chain_id, chain['seed'], use_context=use_context)
            print(f"\n[mc] Draft complete: {len(drafted)} posts")
            sys.exit(0)
        if args.image:
            generate_chain_images(args.chain_id)
            sys.exit(0)
        if args.dry_run:
            chain = db.get_chain(args.chain_id)
            if chain:
                print(f"Chain #{args.chain_id}: seed='{chain['seed']}', "
                      f"type={chain['chain_type']}, status={chain['status']}")
            sys.exit(0)
        chain = db.get_chain(args.chain_id)
        if chain:
            print(f"Chain #{args.chain_id}: seed='{chain['seed']}', "
                  f"type={chain['chain_type']}, status={chain['status']}")
            print("Use --draft, --image, --publish, --inject, or --schedule to act on this chain.")
        else:
            print(f"Chain #{args.chain_id} not found.")
    else:
        parser.print_help()
        print("\nExamples:")
        print("  python chain_publisher.py --seed '츄니토리'")
        print("  python chain_publisher.py --seed '츄니토리' --publish")
        print("  python chain_publisher.py --chain-id 5 --publish")
        print("  python chain_publisher.py --chain-id 5 --inject")
        print("  python chain_publisher.py --chain-id 5 --schedule --launchd")
        sys.exit(1)
