#!/usr/bin/env python3
"""
mc — Manual Chain CLI (Phase 14)

단일 진입점: mc <keyword> → derive → draft → image → publish

사용법:
  mc 업클로젯                        # full pipeline
  mc 업클로젯 --dry-run              # derive only
  mc 업클로젯 --draft                # derive + draft
  mc 업클로젯 --image                # derive + draft + image (skip publish)
  mc 업클로젯 --skip-publish         # same as --image
  mc 업클로젯 --publish              # explicit full pipeline
  mc 업클로젯 --site rotcha          # single-site override
  mc 업클로젯 --background           # background execution
  mc --chain-id 66 --resume          # resume from interrupted step
  mc --chain-id 66 --draft           # existing chain operations
  mc --help                          # this help
"""

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# ─────────────────────────────────────────────────────────────────
# Project root setup — cli/mc.py is at project_root/cli/mc.py
# ─────────────────────────────────────────────────────────────────
_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
_PROJECT_ROOT_STR = str(_PROJECT_ROOT)
sys.path[:] = [_p for _p in sys.path if _p != _PROJECT_ROOT_STR]
sys.path.insert(0, _PROJECT_ROOT_STR)
import importlib
if "mc" in sys.modules and not hasattr(sys.modules["mc"], "__path__"):
    del sys.modules["mc"]
importlib.import_module("mc")

# ─────────────────────────────────────────────────────────────────
# Logging setup
# ─────────────────────────────────────────────────────────────────
_LOG_DIR = _PROJECT_ROOT / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)


def _setup_logging(force_flush: bool = True) -> logging.Logger:
    """
    Set up dual logging: stdout (INFO, user-facing) + file (DEBUG, detailed).
    Each emit triggers a flush when force_flush=True (real-time stage visibility).
    """
    logger = logging.getLogger("mc")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    today = datetime.now().strftime("%Y%m%d")
    log_file = _LOG_DIR / f"mc-cli-{today}.log"

    # File handler — DEBUG, all details, flush on each emit
    if force_flush:
        class _FlushFileHandler(logging.FileHandler):
            def emit(self, record):
                super().emit(record)
                self.flush()
        fh = _FlushFileHandler(str(log_file), encoding="utf-8", mode="a")
    else:
        fh = logging.FileHandler(str(log_file), encoding="utf-8", mode="a")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    # Stdout handler — INFO, user-facing, flush immediately
    if force_flush:
        class _FlushStreamHandler(logging.StreamHandler):
            def emit(self, record):
                super().emit(record)
                self.flush()
        sh = _FlushStreamHandler(sys.stdout)
    else:
        sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(logging.INFO)
    sh.setFormatter(logging.Formatter("[mc] %(message)s"))

    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger


# ─────────────────────────────────────────────────────────────────
# Site override helper
# ─────────────────────────────────────────────────────────────────
_SITE_BLOG_KEY = {
    "rotcha": "rotcha",
    "issue.techpawz": "issue.techpawz",
    "techpawz": "techpawz",
    "aikorea24": "aikorea24",
}


def _build_blog_overrides(site: str | None) -> dict | None:
    """Map --site to blog_overrides dict for publish_chain."""
    if not site:
        return None
    key = _SITE_BLOG_KEY.get(site)
    if not key:
        return None
    # All 3 steps go to the same site
    return {1: key, 2: key, 3: key}


# ─────────────────────────────────────────────────────────────────
# Delegation imports — chain_publisher.py is NOT modified
# ─────────────────────────────────────────────────────────────────


def _run_full(keyword: str, args, logger: logging.Logger) -> int:
    """
    R1: mc <keyword> → full pipeline (or subset via stage flags).

    Delegates to chain_publisher.run_chain() which handles:
      derive → draft → schema validation → image → publish → card injection.
    """
    from chain_publisher import run_chain

    # Determine pipeline stage
    if args.dry_run:
        publish_mode = None
        draft_only = False
        image_only = False
        stage_desc = "dry-run (derive only)"
    elif args.draft:
        publish_mode = None
        draft_only = True
        image_only = False
        stage_desc = "draft (derive + draft)"
    elif args.image or args.skip_publish:
        publish_mode = None
        draft_only = False
        image_only = True
        stage_desc = "image (derive + draft + image)"
    else:
        # Default: full pipeline
        publish_mode = "auto"
        draft_only = False
        image_only = False
        stage_desc = "full pipeline"

    blog_overrides = _build_blog_overrides(args.site)

    logger.info(f"Starting chain: keyword='{keyword}', stage={stage_desc}")
    if args.site:
        logger.info(f"Site override: {args.site}")

    start = datetime.now()

    # _ensure_frontmatter is now implemented in chain_drafter.py (Phase 14 P1).
    # draft_chain calls _ensure_frontmatter internally — no patch needed.
    # Phase 20: --search global default (default=True), --no-search to disable
    use_context = not args.no_search
    if args.search and args.no_search:
        logger.error("Cannot specify both --search and --no-search")
        return 1

    chain_id = run_chain(
        seed=keyword,
        dry_run=args.dry_run,
        draft_only=draft_only,
        image_only=image_only,
        publish_mode=publish_mode,
        blog_overrides=blog_overrides,
        use_context=use_context,
    )

    elapsed = (datetime.now() - start).total_seconds()

    if chain_id:
        logger.info(f"Chain #{chain_id} completed in {elapsed:.1f}s — stage={stage_desc}")
        logger.info(f"Run 'mc --chain-id {chain_id} --resume' to continue later")
    else:
        logger.error(f"Chain failed for keyword='{keyword}'")

    return chain_id if chain_id else 1


# ─────────────────────────────────────────────────────────────────
# Resume — Wave 2 stub (filled in during W2)
# ─────────────────────────────────────────────────────────────────

def _resume_chain(chain_id: int, site_override: str | None, logger: logging.Logger) -> int:
    """
    R3: Resume chain from interrupted step.

    State detection:
      - Any post missing draft_md     → run draft_chain()
      - Any post missing image_url    → run generate_chain_images()
      - Any post missing published_url → run publish_chain() + inject_cards_chain()
      - All complete                  → "already complete", exit 0

    Args:
        chain_id: Chain ID to resume
        site_override: Single-site override (or None)
        logger: Logger instance

    Returns:
        0 on success, 1 on error
    """
    from chain_publisher import (
        _preflight_check,
        generate_chain_images,
        publish_chain,
        inject_cards_chain,
    )
    from chain_drafter import draft_chain
    import chain_db as db

    # ── Validate chain exists ────────────────────────────────────
    chain = db.get_chain(chain_id)
    if not chain:
        logger.error(f"Chain #{chain_id} not found")
        return 2  #明确的 exit code 2 for "not found"

    # ── Already complete? ────────────────────────────────────────
    if chain["status"] == "completed":
        logger.info(f"Chain #{chain_id} already completed. Nothing to resume.")
        return 0

    posts = db.get_chain_posts(chain_id)
    if not posts:
        logger.error(f"Chain #{chain_id} has no posts")
        return 1

    seed = chain["seed"]
    blog_overrides = _build_blog_overrides(site_override)
    step_labels = {1: "rotcha", 2: "issue.techpawz", 3: "techpawz"}

    logger.info(f"Resuming chain #{chain_id} (seed='{seed}', status={chain['status']})")
    if site_override:
        logger.info(f"Site override: {site_override}")

    # ── Step 1: Draft (missing draft_md) ─────────────────────────
    missing_draft = [p for p in posts if not p.get("draft_md")]
    if missing_draft:
        logger.info(f"[resume] Draft: {len(missing_draft)}/{len(posts)} posts missing — running draft_chain()")
        draft_chain(chain_id, seed)
        posts = db.get_chain_posts(chain_id)  # refresh after mutation
    else:
        logger.info(f"[resume] Draft: all {len(posts)} posts have drafts — skipping")

    # ── Step 2: Image (missing image_url) ─────────────────────────
    missing_image = [p for p in posts if not p.get("image_url")]
    if missing_image:
        logger.info(f"[resume] Image: {len(missing_image)}/{len(posts)} posts missing — running generate_chain_images()")
        if not _preflight_check():
            logger.warning("[resume] Preflight check failed — image generation may fail")
        generate_chain_images(chain_id)
        posts = db.get_chain_posts(chain_id)  # refresh
    else:
        logger.info(f"[resume] Image: all {len(posts)} posts have images — skipping")

    # ── Step 3: Publish (missing published_url) ───────────────────
    missing_publish = [p for p in posts if not p.get("published_url")]
    if missing_publish:
        logger.info(f"[resume] Publish: {len(missing_publish)}/{len(posts)} posts missing — running publish_chain()")
        publish_chain(chain_id, mode="auto", blog_overrides=blog_overrides)
        inject_cards_chain(chain_id)
        posts = db.get_chain_posts(chain_id)  # refresh for final status
    else:
        logger.info(f"[resume] Publish: all {len(posts)} posts have published_url — skipping")

    # ── Final status ──────────────────────────────────────────────
    final_chain = db.get_chain(chain_id)
    final_posts = db.get_chain_posts(chain_id)
    all_done = all(p.get("published_url") for p in final_posts)

    if all_done:
        db.update_chain_status(chain_id, "completed")
        logger.info(f"Chain #{chain_id} fully completed via resume")
    else:
        still_missing = [p["id"] for p in final_posts if not p.get("published_url")]
        logger.warning(f"Chain #{chain_id} resume finished but {len(still_missing)} posts still unpublished: {still_missing}")

    logger.info(f"Resume complete for chain #{chain_id}")
    return 0


def _draft_existing(chain_id: int, logger: logging.Logger) -> int:
    """Handle --chain-id N --draft (existing chain draft)."""
    from chain_publisher import generate_chain_images
    from chain_drafter import draft_chain
    import chain_db as db

    chain = db.get_chain(chain_id)
    if not chain:
        logger.error(f"Chain #{chain_id} not found")
        return 1

    logger.info(f"Drafting existing chain #{chain_id} (seed='{chain['seed']}')")
    from chain_drafter import draft_chain as dc
    dc(chain_id, chain["seed"])
    logger.info(f"Chain #{chain_id} draft complete")
    return 0


def _image_existing(chain_id: int, logger: logging.Logger) -> int:
    """Handle --chain-id N --image (existing chain image generation)."""
    from chain_publisher import generate_chain_images

    logger.info(f"Generating images for existing chain #{chain_id}")
    generate_chain_images(chain_id)
    logger.info(f"Chain #{chain_id} image generation complete")
    return 0


# ─────────────────────────────────────────────────────────────────
# Queue command handler (Phase 23)
# ─────────────────────────────────────────────────────────────────

def _cmd_queue(args, logger: logging.Logger) -> int:
    """Handle mc queue subcommands."""
    from mc.queue import add_keyword, get_next_keyword, list_queue, remove_keyword

    if args.queue_action == "add":
        result = add_keyword(args.keyword, args.category, args.priority)
        if result["success"]:
            print(f"[queue] ✅ Added: {result['keyword']} (priority={args.priority})")
        else:
            print(f"[queue] ⚠️ Duplicate: {result['keyword']} (existing: {result['existing_status']})")

    elif args.queue_action == "list":
        items = list_queue(args.status)
        if not items:
            print("[queue] Empty")
            return 0
        for item in items:
            print(f"  {item['priority']} | {item['status']:12} | {item['keyword']:30} | {item.get('category', '-')}")

    elif args.queue_action == "next":
        item = get_next_keyword()
        if item:
            print(f"[queue] Next: {item['keyword']} (id={item['id']}, priority={item['priority']})")
        else:
            print("[queue] No pending keywords")

    elif args.queue_action == "remove":
        if remove_keyword(args.keyword):
            print(f"[queue] ✅ Removed: {args.keyword}")
        else:
            print(f"[queue] ⚠️ Not found or not pending: {args.keyword}")

    return 0


# ─────────────────────────────────────────────────────────────────
# Auto command handler (Phase 23)
# ─────────────────────────────────────────────────────────────────

def _cmd_auto(args, logger: logging.Logger) -> int:
    """mc auto — 큐에서 다음 키워드를 꺼내 run_chain() 실행."""
    from mc.queue import get_next_keyword, mark_done, mark_failed
    from chain_publisher import run_chain
    import traceback

    # dry-run: 키워드만 꺼내서 보여주고 실행 안 함
    if args.dry_run:
        item = get_next_keyword()
        if not item:
            print("[auto] No pending keywords in queue. Exiting.")
            return 0
        print(f"[auto] Dry-run: would process '{item['keyword']}' (id={item['id']}, priority={item['priority']})")
        return 0

    item = get_next_keyword()
    if not item:
        print("[auto] No pending keywords in queue. Exiting.")
        return 0

    keyword = item["keyword"]
    queue_id = item["id"]
    print(f"[auto] Processing: {keyword} (id={queue_id}, priority={item['priority']})")

    try:
        chain_id = run_chain(keyword, publish_mode="auto", use_context=True)
        if chain_id:
            mark_done(queue_id, chain_id)
            print(f"[auto] ✅ Chain #{chain_id} completed for '{keyword}'")

            # 성공 알림 (실패해도 발행 중단 안 함)
            try:
                from mc.notify import send_success
                send_success(f"Chain #{chain_id} published", f"Keyword: {keyword}")
            except Exception:
                pass
        else:
            mark_failed(queue_id, "run_chain returned None")
            print(f"[auto] ❌ Failed: run_chain returned None")
            return 1
    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}"
        traceback.print_exc()
        mark_failed(queue_id, error_msg)
        print(f"[auto] ❌ Failed: {error_msg}")

        # 실패 알림
        try:
            from mc.notify import send_alert
            send_alert(f"mc auto failed: {keyword}", error_msg, level="error")
        except Exception:
            pass
        return 1

    return 0


# ─────────────────────────────────────────────────────────────────
# Background execution — Wave 3
# ─────────────────────────────────────────────────────────────────

def _run_background(keyword: str, args, logger: logging.Logger) -> int:
    """
    R5: Run pipeline in background (detached subprocess).

    Launches `python -m cli.mc <keyword> [flags] --pid-file <path>` in a detached session.
    stdout/stderr redirected to the daily log file.
    PID file: logs/mc-cli-<ts>.pid — deleted by subprocess on exit via atexit.
    """
    import subprocess
    import sys
    from datetime import datetime as _dt

    today = _dt.now().strftime("%Y%m%d")
    ts = _dt.now().strftime("%Y%m%d_%H%M%S")
    log_file = str(_LOG_DIR / f"mc-cli-{today}.log")
    pid_file = str(_LOG_DIR / f"mc-cli-{ts}.pid")

    # Build argv for the subprocess
    argv = [sys.executable, "-m", "cli.mc", "run", keyword]
    if args.dry_run:
        argv.append("--dry-run")
    elif args.draft:
        argv.append("--draft")
    elif args.image or args.skip_publish:
        argv.append("--image")
    elif args.publish:
        argv.append("--publish")
    if args.site:
        argv.extend(["--site", args.site])
    if getattr(args, "no_search", False):
        argv.append("--no-search")
    elif getattr(args, "search", False):
        argv.append("--search")
    argv.extend(["--pid-file", pid_file])

    # Open log file (append mode) for subprocess output
    log_fh = open(log_file, "a", encoding="utf-8")

    proc = subprocess.Popen(
        argv,
        stdout=log_fh,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        cwd=str(_PROJECT_ROOT),
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )

    # Write subprocess PID to file (subprocess will overwrite with its own PID via atexit)
    Path(pid_file).write_text(str(proc.pid), encoding="utf-8")

    # Console: single-line summary
    print(
        f"[mc] Chain started in background — "
        f"PID={proc.pid}  log={log_file}  pid_file={pid_file}",
        file=sys.stdout,
        flush=True,
    )

    return 0


# ─────────────────────────────────────────────────────────────────
# Cost summary — Wave 3
# ─────────────────────────────────────────────────────────────────

def _log_cost_summary(logger: logging.Logger, chain_id: int, start_time: datetime) -> None:
    """R6: Log cost summary at end of pipeline run."""
    import chain_db as db

    posts = db.get_chain_posts(chain_id)
    elapsed = (datetime.now() - start_time).total_seconds()
    image_count = sum(1 for p in posts if p.get("image_url"))
    urls = [p.get("published_url", "N/A") for p in posts]

    logger.info("=" * 50)
    logger.info(f"Cost Summary — Chain #{chain_id}")
    logger.info(f"  Elapsed: {elapsed:.1f}s")
    logger.info(f"  Posts: {len(posts)}")
    logger.info(f"  Images: {image_count}")
    if urls:
        logger.info("  URLs:")
        for url in urls:
            logger.info(f"    - {url}")
    today = datetime.now().strftime("%Y%m%d")
    logger.info(f"  Log file: logs/mc-cli-{today}.log")
    logger.info("=" * 50)


# ─────────────────────────────────────────────────────────────────
# Queue command handlers (Phase 23)
# ─────────────────────────────────────────────────────────────────

def _cmd_queue(args, logger: logging.Logger) -> int:
    """Handle mc queue subcommands."""
    from mc.queue import add_keyword, get_next_keyword, list_queue, remove_keyword

    if args.queue_action == "add":
        result = add_keyword(args.keyword, args.category, args.priority)
        if result["success"]:
            print(f"[queue] ✅ Added: {result['keyword']} (id={result['id']}, priority={args.priority})")
        else:
            print(f"[queue] ⚠️ Duplicate: {result['keyword']} (existing status: {result['existing_status']})")

    elif args.queue_action == "list":
        items = list_queue(args.status)
        if not items:
            print("[queue] Empty")
            return 0
        for item in items:
            cat = item.get('category', '-') or '-'
            print(f"  {item['priority']} | {item['status']:12} | {item['keyword']:30} | {cat}")

    elif args.queue_action == "next":
        item = get_next_keyword()
        if item:
            print(f"[queue] Next: {item['keyword']} (id={item['id']}, priority={item['priority']})")
        else:
            print("[queue] No pending keywords")

    elif args.queue_action == "remove":
        if remove_keyword(args.keyword):
            print(f"[queue] ✅ Removed: {args.keyword}")
        else:
            print(f"[queue] ⚠️ Not found or not pending: {args.keyword}")

    return 0


# ─────────────────────────────────────────────────────────────────
# Auto command handler (Phase 23)
# ─────────────────────────────────────────────────────────────────

def _cmd_auto(args, logger: logging.Logger) -> int:
    """mc auto — 큐에서 다음 키워드를 꺼내 run_chain() 실행."""
    from mc.queue import get_next_keyword, mark_done, mark_failed
    from chain_publisher import run_chain
    import traceback

    dry_run = getattr(args, 'dry_run', False)

    item = get_next_keyword()
    if not item:
        print("[auto] No pending keywords in queue. Exiting.")
        return 0

    keyword = item["keyword"]
    queue_id = item["id"]
    print(f"[auto] Processing: {keyword} (id={queue_id}, priority={item['priority']})")

    if dry_run:
        print(f"[auto] Dry run — would process: {keyword}")
        return 0

    try:
        chain_id = run_chain(keyword, publish_mode="auto", use_context=True)
        if chain_id:
            mark_done(queue_id, chain_id)
            print(f"[auto] ✅ Chain #{chain_id} completed for '{keyword}'")
            # Success alert
            try:
                from mc.notify import send_success
                send_success(f"Chain #{chain_id} published", f"Keyword: {keyword}")
            except Exception:
                pass
        else:
            mark_failed(queue_id, "run_chain returned None")
            print(f"[auto] ❌ Failed: run_chain returned None")
            return 1
    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}"
        traceback.print_exc()
        mark_failed(queue_id, error_msg)
        print(f"[auto] ❌ Failed: {error_msg}")
        # Alert on failure
        try:
            from mc.notify import send_alert
            send_alert(f"mc auto failed: {keyword}", error_msg, level="error")
        except Exception:
            pass
        return 1

    return 0


# ─────────────────────────────────────────────────────────────────
# Schedule command handlers (Phase 23)
# ─────────────────────────────────────────────────────────────────

def _cmd_schedule(args, logger: logging.Logger) -> int:
    """Handle mc schedule subcommands using unified scheduler module."""
    from mc.scheduler import install_schedule, remove_schedule, get_status

    if args.schedule_action == "setup":
        hour = args.hour
        minute = args.minute

        install_schedule(hour=hour, minute=minute)
        print(f"[schedule] ✅ Daily at {hour:02d}:{minute:02d} registered")

    elif args.schedule_action == "status":
        status = get_status()
        os_type = status.get("os", "unknown")

        if os_type == "macos":
            if status.get("plist_exists"):
                print(f"  launchd: {status.get('plist_path')}")
                print(f"  loaded: {status.get('loaded')}")
            else:
                print("  No launchd tasks")
        elif os_type == "linux":
            entries = status.get("entries", [])
            if entries:
                for t in entries:
                    print(f"  cron: {t['schedule']} → {t['command'][:60]}...")
            else:
                print("  No cron tasks")
        else:
            print(f"  Unknown OS: {os_type}")

    elif args.schedule_action == "remove":
        if remove_schedule():
            print("  [schedule] ✅ Schedule removed")
        else:
            print("  [schedule] ⚠️ No schedule to remove")

    return 0


# ─────────────────────────────────────────────────────────────────
# Status command handler (Phase 23)
# ─────────────────────────────────────────────────────────────────

def _cmd_status(args, logger: logging.Logger) -> int:
    """mc status — 최근 N일 체인 현황 요약 출력."""
    import chain_db as db
    from datetime import datetime, timedelta
    import json

    days = args.days
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    chains = db.get_chains_since(since)
    if not chains:
        print(f"[status] No chains in last {days} days")
        return 0

    total = len(chains)
    completed = sum(1 for c in chains if c["status"] == "completed")
    failed = sum(1 for c in chains if c["status"] == "failed")
    in_progress = total - completed - failed

    # 사이트별 발행 수
    site_stats = {}
    for c in chains:
        if c["status"] == "completed":
            posts = db.get_chain_posts(c["id"])
            for p in posts:
                if p.get("published_url"):
                    url = p["published_url"]
                    if "rotcha.kr" in url:
                        site_stats["rotcha.kr"] = site_stats.get("rotcha.kr", 0) + 1
                    elif "techpawz" in url:
                        site_stats["techpawz.com"] = site_stats.get("techpawz.com", 0) + 1
                    elif "informationhot" in url:
                        site_stats["informationhot.kr"] = site_stats.get("informationhot.kr", 0) + 1

    # Smoke test 통과율
    smoke_total = 0
    smoke_passed = 0
    for c in chains:
        if c["status"] == "completed":
            posts = db.get_chain_posts(c["id"])
            for p in posts:
                if p.get("smoke_test_result"):
                    smoke_total += 1
                    if p["smoke_test_result"] == "pass":
                        smoke_passed += 1

    # 키워드 큐 현황
    queue_items = db.list_keyword_queue()
    queue_stats = {}
    for item in queue_items:
        queue_stats[item["status"]] = queue_stats.get(item["status"], 0) + 1

    if args.json:
        print(json.dumps({
            "period_days": days,
            "total_chains": total,
            "completed": completed,
            "failed": failed,
            "in_progress": in_progress,
            "site_breakdown": site_stats,
            "smoke_test_pass_rate": f"{smoke_passed}/{smoke_total}" if smoke_total else "N/A",
            "queue_status": queue_stats,
        }, ensure_ascii=False, indent=2))
        return 0

    # 터미널 텍스트 출력
    print(f"\n{'='*50}")
    print(f"  mc Status — Last {days} days ({since} ~)")
    print(f"{'='*50}")
    print(f"  Total chains:   {total}")
    print(f"  ✅ Completed:    {completed}")
    print(f"  ❌ Failed:       {failed}")
    print(f"  🔄 In progress:  {in_progress}")
    print(f"\n  Site breakdown:")
    for site, count in sorted(site_stats.items(), key=lambda x: -x[1]):
        print(f"    {site}: {count}")
    if smoke_total:
        rate = smoke_passed / smoke_total * 100
        print(f"\n  Smoke test: {smoke_passed}/{smoke_total} passed ({rate:.1f}%)")
    print(f"\n  Queue status:")
    for status in ["pending", "processing", "done", "failed"]:
        count = queue_stats.get(status, 0)
        if count:
            print(f"    {status}: {count}")
    print(f"{'='*50}\n")
    return 0


# ─────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="mc",
        description="mc — Manual Chain CLI: one command to derive, draft, image, and publish a blog chain",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ── Main command: mc <keyword> ─────────────────────────────────
    main_parser = subparsers.add_parser("run", help="Run full pipeline (default)")
    main_parser.add_argument("keyword", help="Seed keyword for the chain")
    main_parser.add_argument("--chain-id", type=int, help="Existing chain ID (for --resume / --draft / --image)")
    main_parser.add_argument("--pid-file", type=str, default=None,
                            help="PID file to delete on exit (internal use by --background)")

    # Pipeline stage flags
    stage_group = main_parser.add_mutually_exclusive_group()
    stage_group.add_argument("--dry-run", action="store_true",
                             help="Derive only — create chain, no draft")
    stage_group.add_argument("--draft", action="store_true",
                             help="Derive + draft — no image generation")
    stage_group.add_argument("--image", action="store_true",
                             help="Derive + draft + image — skip publish")
    stage_group.add_argument("--skip-publish", action="store_true",
                             help="Alias for --image")
    stage_group.add_argument("--publish", action="store_true",
                             help="Full pipeline (default if no stage flag)")

    # Resume & override
    main_parser.add_argument("--resume", action="store_true",
                            help="Resume interrupted chain (requires --chain-id)")
    main_parser.add_argument("--site", type=str,
                            choices=list(_SITE_BLOG_KEY.keys()),
                            help="Single site override (rotcha / issue.techpawz / techpawz / aikorea24)")

    # Search context flags (Phase 20: --search global default)
    main_parser.add_argument("--search", action="store_true", default=True,
                            help="Enable Naver search context (default)")
    main_parser.add_argument("--no-search", action="store_true",
                            help="Disable Naver search context")

    # Execution mode
    main_parser.add_argument("--background", action="store_true",
                            help="Run in background (detached process)")

    # ── Queue command ─────────────────────────────────────────────
    queue_parser = subparsers.add_parser("queue", help="키워드 큐 관리")
    queue_parser.add_argument("--pid-file", type=str, default=None,
                             help="PID file to delete on exit (internal use)")
    queue_sub = queue_parser.add_subparsers(dest="queue_action")

    # queue add
    add_p = queue_sub.add_parser("add", help="키워드 큐에 추가")
    add_p.add_argument("keyword", help="시드 키워드")
    add_p.add_argument("--category", help="카테고리 (travel, stock, automotive, real_estate, etc)")
    add_p.add_argument("--priority", type=int, default=3, choices=range(1, 6), help="우선순위 1~5 (1=최고)")

    # queue list
    list_p = queue_sub.add_parser("list", help="큐 목록 조회")
    list_p.add_argument("--status", choices=["pending", "processing", "done", "failed"], help="상태 필터")

    # queue next
    next_p = queue_sub.add_parser("next", help="다음 처리할 키워드 1개 조회 (processing으로 변경)")

    # queue remove
    remove_p = queue_sub.add_parser("remove", help="큐에서 키워드 제거")
    remove_p.add_argument("keyword", help="제거할 키워드")

    # ── Auto command ──────────────────────────────────────────────
    auto_parser = subparsers.add_parser("auto", help="큐에서 다음 키워드 꺼내서 자동 발행")
    auto_parser.add_argument("--pid-file", type=str, default=None,
                            help="PID file to delete on exit (internal use)")
    auto_parser.add_argument("--dry-run", action="store_true", help="키워드만 꺼내서 보여주고 실행은 안 함")

    # ── Schedule command ──────────────────────────────────────────
    schedule_parser = subparsers.add_parser("schedule", help="자동 발행 스케줄 관리")
    schedule_parser.add_argument("--pid-file", type=str, default=None,
                                help="PID file to delete on exit (internal use)")
    schedule_sub = schedule_parser.add_subparsers(dest="schedule_action")

    # schedule setup
    setup_p = schedule_sub.add_parser("setup", help="일일 자동 발행 스케줄 등록")
    setup_p.add_argument("--daily", action="store_true", help="매일 실행 (기본값)")
    setup_p.add_argument("--hour", type=int, default=9, help="실행 시각 (시, 0-23)")
    setup_p.add_argument("--minute", type=int, default=0, help="실행 시각 (분, 0-59)")
    setup_p.add_argument("--no-launchd", action="store_true", help="macOS launchd 대신 cron 사용")

    # schedule status
    status_p = schedule_sub.add_parser("status", help="현재 스케줄 등록 상태 확인")

    # schedule remove
    remove_p = schedule_sub.add_parser("remove", help="스케줄 제거")
    remove_p.add_argument("--all", action="store_true", help="모든 mc 스케줄 제거")

    # ── Status command ────────────────────────────────────────────
    status_parser = subparsers.add_parser("status", help="최근 7일 발행 현황 요약")
    status_parser.add_argument("--pid-file", type=str, default=None,
                              help="PID file to delete on exit (internal use)")
    status_parser.add_argument("--days", type=int, default=7, help="조회 기간 (일)")
    status_parser.add_argument("--json", action="store_true", help="JSON 출력")

    args = parser.parse_args()

    # ── PID file cleanup on exit (for background subprocess) ───────
    if args.pid_file:
        import atexit as _atexit
        _pid_file = Path(args.pid_file)
        if _pid_file.exists():
            _atexit.register(lambda: _pid_file.unlink(missing_ok=True))

    # Logging
    logger = _setup_logging()

    # ── Route to handler ──────────────────────────────────────────
    if args.command == "run":
        if args.resume and args.chain_id:
            try:
                return _resume_chain(args.chain_id, args.site, logger)
            except NotImplementedError as e:
                logger.error(str(e))
                sys.exit(1)
        elif args.chain_id and args.draft:
            return _draft_existing(args.chain_id, logger)
        elif args.chain_id and args.image:
            return _image_existing(args.chain_id, logger)
        elif args.keyword:
            if args.background:
                try:
                    return _run_background(args.keyword, args, logger)
                except NotImplementedError as e:
                    logger.error(str(e))
                    sys.exit(1)
            else:
                return _run_full(args.keyword, args, logger)
        else:
            parser.print_help()
            sys.exit(1)

    elif args.command == "queue":
        return _cmd_queue(args, logger)

    elif args.command == "auto":
        return _cmd_auto(args, logger)

    elif args.command == "schedule":
        return _cmd_schedule(args, logger)

    elif args.command == "status":
        return _cmd_status(args, logger)

    else:
        # Backward compatibility: if no subcommand, treat as keyword
        if args.keyword and not args.command:
            # This is the old behavior: mc <keyword>
            # We need to parse with the old parser structure
            pass

        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())
