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
from mc_paths import (
    ensure_5000_on_path, load_config, load_prompts, get_chain_blog_key,
    PROMPTS_PATH, DRAFTS_DIR,
)

ensure_5000_on_path()

from shared.ai_writer import generate
from shared.publishers.hugo_writer import _write_hugo_post

import chain_db as db
from chain_deriver import derive_chain


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

        if use_new_image:
            blog_key = get_chain_blog_key(post["depth"])
            full_prompt = img_build(
                post.get("image_keyword", post.get("target_keyword", "")),
                blog_key,
                chain_type=chain.get("chain_type", "depth"),
                step=post.get("step", 1),
            )
            image_path = img_gen(full_prompt, slug=post.get("slug", f"post-{post_id}"))
            if image_path:
                image_url = f"/images/{image_path.name}"
                db.update_post_image(post_id, image_url)
                if post.get("draft_md"):
                    updated = img_inject(
                        post["draft_md"], post.get("slug", ""),
                        blog_key, post.get("step", 1), post["title"],
                    )
                    db.update_post_draft(post_id, updated, post.get("slug", ""))
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
                  blog_overrides: dict = None) -> None:
    """
    역순(Step 3→2→1) 발행.
    mode: "auto" | "interactive" | "manual"
    """
    from chain_publisher_core import PublisherCore

    config = load_config()
    core = PublisherCore(config)

    posts = db.get_chain_posts_ordered(chain_id, direction="desc")
    if not posts:
        print(f"[mc] Chain #{chain_id} has no posts")
        return

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

        url, method = core.publish_post(blog_key, draft_md, slug, title, labels)
        if url:
            db.update_published_url(post["id"], url, method)
            print(f"  [publish] ✅ Step {step} published: {url}")
        else:
            db.update_post_status(post["id"], "failed",
                                  error_log=f"publish failed to {blog_key}")
            print(f"  [publish] Step {step} failed")

    db.update_chain_status(chain_id, "published" if mode == "auto" else "manual_pending")
    print(f"\n[mc] Chain #{chain_id} publish complete")


# ── Phase 3: 카드 주입 ───────────────────────────────────────────

def inject_cards_chain(chain_id: int) -> None:
    """Step 1→2→3 정순으로 next 카드 주입."""
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
        content = post.get("draft_md", "")

        if not content or not next_post.get("published_url"):
            print(f"  [inject] Step {step}: missing content or next URL, skipping")
            continue

        updated = injector.inject_cards(
            content=content,
            next_title=next_post["title"],
            next_url=next_post["published_url"],
            blog_key=blog_key,
            direction=direction,
        )

        if updated != content:
            blog_cfg = config["sites"].get(blog_key, {})
            hugo_file = post.get("hugo_file_path", "")
            if os.path.exists(hugo_file):
                with open(hugo_file, "w", encoding="utf-8") as f:
                    f.write(updated)
                core._git_push(blog_cfg.get("hugo_root", ""))
                db.update_card_injected(post["id"])
                print(f"  [inject] ✅ Step {step} card injected")
            else:
                print(f"  [inject] Step {step}: hugo file not found ({hugo_file})")


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
              publish_mode: str = None, blog_overrides: dict = None) -> int:
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
    drafted = draft_chain(chain_id, seed)
    print(f"\n[mc] Draft complete: {len(drafted)} posts")

    if draft_only:
        return chain_id

    generate_chain_images(chain_id)
    if image_only:
        return chain_id

    if publish_mode:
        publish_chain(chain_id, mode=publish_mode, blog_overrides=blog_overrides)
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
    parser.add_argument("--inject", action="store_true", help="Card injection only")
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

    # Publish only (existing chain)
    if args.publish and args.chain_id:
        blog_overrides = {}
        if args.blog_step1:
            blog_overrides[1] = args.blog_step1
        if args.blog_step2:
            blog_overrides[2] = args.blog_step2
        if args.blog_step3:
            blog_overrides[3] = args.blog_step3
        publish_chain(args.chain_id, mode="auto", blog_overrides=blog_overrides)
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

        run_chain(
            args.seed,
            dry_run=args.dry_run,
            draft_only=args.draft,
            image_only=args.image,
            chain_type=args.chain_type,
            publish_mode=publish_mode,
            blog_overrides=blog_overrides or None,
        )
    elif args.chain_id:
        chain = db.get_chain(args.chain_id)
        if chain:
            print(f"Chain #{args.chain_id}: seed='{chain['seed']}', "
                  f"type={chain['chain_type']}, status={chain['status']}")
            print("Use --publish, --inject, or --schedule to act on this chain.")
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
