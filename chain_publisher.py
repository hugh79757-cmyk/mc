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
from mc_paths import (
    ensure_5000_on_path, load_config, load_prompts, get_chain_blog_key,
    PROMPTS_PATH, DRAFTS_DIR,
)

ensure_5000_on_path()

from shared.ai_writer import generate
from shared.publishers.hugo_writer import _write_hugo_post

import chain_db as db
from chain_deriver import derive_chain

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

def generate_image_remote(image_prompt: str, image_keyword: str, pollinations_cfg: dict) -> str:
    base_url = pollinations_cfg["base_url"]
    width = pollinations_cfg.get("width", 1024)
    height = pollinations_cfg.get("height", 768)
    rate_limit = pollinations_cfg.get("rate_limit_seconds", 15)

    encoded_prompt = urllib.parse.quote(image_prompt)
    image_url = f"{base_url}{encoded_prompt}.jpg?width={width}&height={height}&model=flux"

    print(f"  [publisher] Image URL: {image_url[:100]}...")
    try:
        req = urllib.request.Request(image_url, method="HEAD")
        with urllib.request.urlopen(req, timeout=30) as resp:
            print(f"  [publisher]     Response: {resp.status}")
    except Exception as e:
        print(f"  [publisher]     {e}")

    print(f"  [publisher]     {rate_limit}s rate limit...")
    time.sleep(rate_limit)
    return image_url


# ── 체인 이미지 생성 ──

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


def generate_chain_images(chain_id: int) -> None:
    use_new_image = False
    img_gen = img_build = img_inject = None
    try:
        from image import generate_image as img_gen
        from image import build_full_prompt as img_build
        from image import inject_images_into_draft as img_inject
        use_new_image = True
        print("[publisher] image/ package loaded (local file download)")
    except ImportError as e:
        print(f"[publisher] image/ package not found ({e}), using legacy URL")

    chain = db.get_chain(chain_id)
    if not chain:
        print(f"[publisher] Chain #{chain_id} not found")
        return

    config = load_config()
    pol_cfg = config.get("pollinations", {})
    posts = db.get_chain_posts(chain_id)
    db.update_chain_status(chain_id, "generating")

    for i, post in enumerate(posts):
        post_id = post["id"]
        print(f"\n  [publisher] Image {i+1}/{len(posts)} — post #{post_id}")

        # 정규 필드(image_meta.content_image_path) 기준 완결 판정 — 반쪽 백필 방지
        _meta_raw = post.get("image_meta")
        _meta = json.loads(_meta_raw) if isinstance(_meta_raw, str) else (_meta_raw or {})
        if _meta.get("content_image_path"):
            print(f"    ↷ 이미지 보유 (post #{post_id}): {_meta.get('content_image_path')} — 스킵")
            continue

        _slug = post.get("slug") or f"post-{post_id}"
        # 디스크-DB 교차확인: 파일은 있으나 image_meta.content_image_path 미결속 → 재생성 금지, 백필만
        _disk = _find_disk_image(_slug)
        if _disk:
            _abs = str(_disk)
            db.update_content_image(post_id, _abs, "pollinations")
            db.update_post_image(post_id, f"/images/{_disk.name}")
            print(f"    ↷ 디스크 파일 백필 (post #{post_id}): {_abs}")
            _write_image_log(post_id, _slug,
                             f"IMAGE BACKFILL post_id={post_id}\ndisk={_abs}\nimage_meta.content_image_path set via update_content_image\n")
            continue

        if use_new_image:
            blog_key = get_chain_blog_key(post["depth"])
            full_prompt = img_build(
                post.get("image_keyword", post.get("target_keyword", "")),
                blog_key,
                chain_type=chain.get("chain_type", "depth"),
                step=post.get("step", 1),
            )
            image_result = img_gen(full_prompt, slug=_slug)
            if image_result and image_result.ok:
                image_path = image_result.value
                image_url = f"/images/{image_path.name}"
                db.update_content_image(post_id, str(image_path), "pollinations")
                db.update_post_image(post_id, image_url)
                _write_image_log(post_id, _slug, f"IMAGE GEN OK post_id={post_id}\nurl={image_url}\ncontent_image_path set\n")
                if post.get("draft_md"):
                    updated = img_inject(
                        post["draft_md"], post.get("slug", ""),
                        blog_key, post.get("step", 1), post["title"],
                    )
                    db.update_post_draft(post_id, updated, post.get("slug", ""))
            else:
                _err = getattr(image_result, "error", "img_gen returned None/empty")
                print(f"  [publisher] ⚠️ 이미지 생성 실패 (post #{post_id}, slug={_slug}): {_err}")
                _write_image_log(post_id, _slug,
                                f"IMAGE GEN FAIL post_id={post_id}\nerror={_err}\nfull_prompt={full_prompt[:500]}\n")
        else:
            image_url = generate_image_remote(
                post["image_prompt"], post["image_keyword"], pol_cfg,
            )
            post["image_url"] = image_url
            db.update_post_image(post_id, image_url)

        if i < len(posts) - 1:
            print(f"  [publisher]     waiting {pol_cfg.get('rate_limit_seconds', 15)}s...")
            time.sleep(pol_cfg.get("rate_limit_seconds", 15))

    db.update_chain_status(chain_id, "image_generated")
    print(f"\n  [publisher] Chain #{chain_id} images done")


# ── Hugo 게시 (Legacy) ──

def publish_post(post: dict, body_md: str, image_url: str, config: dict) -> dict:
    blog_key = get_chain_blog_key(post["depth"])
    site_cfg = config["sites"][blog_key]
    site_path = site_cfg["site_path"]
    blog_id = site_cfg["blog_id"]

    category = post.get("category", "일반")
    tags = post.get("tags", [post.get("target_keyword", "")])

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
    defaults = mapping.get(chain_type, ["rotcha", "infohot", "techpawz"])
    return defaults[step - 1] if step <= len(defaults) else "rotcha"


def publish_chain(chain_id: int, mode: str = "auto",
                  blog_overrides: dict = None,
                  theme_override: str = None,
                  cf_project_override: str = None) -> None:
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
        return
    from chain_publisher_core import PublisherCore

    config = load_config()
    core = PublisherCore(config)

    posts = db.get_chain_posts_ordered(chain_id, direction="desc")
    if not posts:
        print(f"[mc] Chain #{chain_id} has no posts")
        return

    # 누락 이미지 자동 보완 (기존 체인 발행 시 이미지 생성 누락 방지)
    _missing = [p for p in posts if not p.get("image_url")]
    if _missing:
        print(f"[mc] ⚠️ 이미지 누락 {len(_missing)}건 → 이미지 생성/백필 실행")
        try:
            generate_chain_images(chain_id)
        except Exception as _e:
            print(f"[mc] 이미지 보완 실패 (발행 계속): {_e}")
        posts = db.get_chain_posts_ordered(chain_id, direction="desc")

    print(f"\n{'='*60}")
    print(f"[mc] Publishing chain #{chain_id} (reverse order: 3→2→1)")
    print(f"{'='*60}")

    db.update_chain_status(chain_id, "generating")

    for i, post in enumerate(posts):
        step = post.get("step", 1)
        blog_key = _get_blog_for_step(chain_id, step, config, blog_overrides)
        draft_md = post.get("draft_md", "")
        slug = post.get("slug", f"chain-{chain_id}-s{step}")
        title = post["title"]
        labels = [post.get("target_keyword", ""), post.get("category_guess", "일반")]

        if not draft_md:
            print(f"  [publish] Step {step}: no draft, skipping")
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

        url, method, file_path = core.publish_post(blog_key, draft_md, slug, title, labels)
        if url:
            db.update_published_url(post["id"], url, method)
            if file_path:
                db.update_post_published(post["id"], file_path)
            print(f"  [publish] ✅ Step {step} published: {url}")
        else:
            db.update_post_status(post["id"], "failed",
                                  error_log=f"publish failed to {blog_key}")
            print(f"  [publish] Step {step} failed")

    db.update_chain_status(chain_id, "published" if mode == "auto" else "manual_pending")
    print(f"\n[mc] Chain #{chain_id} publish complete")


# ── Phase 5: 카드 주입 (draft_md 기반) ──────────────────────────────

def inject_cards_chain(chain_id: int) -> None:
    """Step 1→2→3 정순으로 next 카드 주입 (draft_md 기반 + 재발행)."""
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

    print(f"\n{'='*60}")
    print(f"[mc] Injecting cards for chain #{chain_id}")
    print(f"{'='*60}")

    for i in range(len(posts) - 1):
        post = posts[i]
        next_post = posts[i + 1]
        step = post.get("step", 1)
        blog_key = _get_blog_for_step(chain_id, step, config)
        direction = chain.get("chain_type", "depth")

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
        )
        if success:
            db.update_card_injected(post["id"])
            print(f"  [inject] ✅ Step {step} card injected & re-published")
        else:
            print(f"  [inject] Step {step}: draft_md missing, skipping")


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
              use_context: bool = False) -> int:
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

    if draft_only:
        return chain_id

    generate_chain_images(chain_id)
    if image_only:
        return chain_id

    if publish_mode:
        publish_chain(chain_id, mode=publish_mode, blog_overrides=blog_overrides,
                      theme_override=theme_override, cf_project_override=cf_project_override)
        if publish_mode != "manual":
            inject_cards_chain(chain_id)
    else:
        # Legacy full pipeline
        print(f"\n{'='*60}\n[mc] Publishing chain #{chain_id}\n{'='*60}\n")
        posts = db.get_chain_posts(chain_id)
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
                print(f"  [publisher] Publish failed: {err}")
        db.update_chain_status(chain_id, "completed")

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
                        help="Enable Naver search context for drafting")
    parser.add_argument("--no-search", action="store_true",
                        help="Disable search context (default)")
    
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

    if args.inject_card and args.chain_id:
        inject_cards_chain(args.chain_id)
        sys.exit(0)

    if args.publish_interactive and args.chain_id:
        publish_chain(args.chain_id, mode="interactive")
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

        use_context = args.search and not args.no_search

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
            use_context = args.search and not args.no_search
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
