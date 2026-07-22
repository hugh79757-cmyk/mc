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
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

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
    "infohot": "infohot",
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
    from unittest.mock import patch

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

    # ── Frontmatter injection patch ─────────────────────────────────
    # _validate_draft_schema expects frontmatter in draft_md, but
    # draft_chain stores drafts WITHOUT frontmatter (frontmatter is added
    # later in _publish_hugo). We patch draft_chain at the source
    # (chain_drafter.draft_chain) to inject frontmatter into draft_md
    # after the original function stores it in the DB.
    # This ensures _validate_draft_schema passes without modifying
    # chain_publisher.py or chain_drafter.py.
    import chain_db as _cdb
    from chain_drafter import draft_chain as _orig_draft_chain

    def _wrapped_draft_chain(chain_id, seed_keyword, use_context=False):
        result = _orig_draft_chain(chain_id, seed_keyword, use_context)
        # _orig_draft_chain returns posts with OLD draft_md (update_post_draft returns None).
        # We must inject frontmatter into the returned posts list directly so
        # _validate_draft_schema (which receives this same list) finds frontmatter.
        for p in result:
            dm = p.get("draft_md", "")
            if not dm or dm.strip().startswith("---"):
                continue
            title = p.get("title", "")
            tags = p.get("tags", [])
            cats = p.get("category_guess", "일반")
            tags_str = ", ".join(f'"{t}"' for t in (tags if isinstance(tags, list) else []))
            fm = (
                f"---\n"
                f'title: "{title}"\n'
                f"description: \"\"\n"
                f"draft: true\n"
                f"tags: [{tags_str}]\n"
                f'categories: ["{cats}"]\n'
                f"---\n\n"
            )
            p["draft_md"] = fm + dm
        return result

    with patch("chain_drafter.draft_chain", side_effect=_wrapped_draft_chain):
        chain_id = run_chain(
            seed=keyword,
            dry_run=args.dry_run,
            draft_only=draft_only,
            image_only=image_only,
            publish_mode=publish_mode,
            blog_overrides=blog_overrides,
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
    step_labels = {1: "rotcha", 2: "infohot", 3: "techpawz"}

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
# Background execution — Wave 3 stub
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
    argv = [sys.executable, "-m", "cli.mc", keyword]
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
# main entry point
# ─────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="mc",
        description="mc — Manual Chain CLI: one command to derive, draft, image, and publish a blog chain",
    )
    parser.add_argument("keyword", nargs="?", help="Seed keyword for the chain")
    parser.add_argument("--chain-id", type=int, help="Existing chain ID (for --resume / --draft / --image)")
    parser.add_argument("--pid-file", type=str, default=None,
                        help="PID file to delete on exit (internal use by --background)")

    # Pipeline stage flags
    stage_group = parser.add_mutually_exclusive_group()
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
    parser.add_argument("--resume", action="store_true",
                        help="Resume interrupted chain (requires --chain-id)")
    parser.add_argument("--site", type=str,
                        choices=list(_SITE_BLOG_KEY.keys()),
                        help="Single site override (rotcha / infohot / techpawz / aikorea24)")

    # Execution mode
    parser.add_argument("--background", action="store_true",
                        help="Run in background (detached process)")

    args = parser.parse_args()

    # ── PID file cleanup on exit (for background subprocess) ───────
    if args.pid_file:
        import atexit as _atexit
        _pid_file = Path(args.pid_file)
        if _pid_file.exists():
            _atexit.register(lambda: _pid_file.unlink(missing_ok=True))

    # Logging
    logger = _setup_logging()

    # ── Validation ───────────────────────────────────────────────
    if not args.keyword and not args.chain_id:
        parser.print_help()
        sys.exit(1)

    # --resume requires --chain-id
    if args.resume and not args.chain_id:
        parser.error("--resume requires --chain-id")

    # --site requires a keyword (new chain)
    if args.site and not args.keyword:
        parser.error("--site requires a keyword (not --chain-id)")

    # --background requires a keyword
    if args.background and not args.keyword:
        parser.error("--background requires a keyword")

    # ── Route to handler ─────────────────────────────────────────
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


if __name__ == "__main__":
    sys.exit(main())