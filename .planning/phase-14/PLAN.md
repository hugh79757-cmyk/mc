---
phase: 14-cli-entry-point
plan: 01
type: plan-only
wave: 1-4
depends_on: [phase-13]
files_modified: []
files_created:
  - cli/mc.py
  - setup.py (or pyproject.toml — console_scripts entry)
  - test_cli_mc.py
autonomous: false
requirements:
  - R1
  - R2
  - R3
  - R4
  - R5
  - R6
user_setup: []
must_haves:
  truths:
    - "`mc <keyword>` runs derive → draft → image → publish in one command"
    - "`chain_publisher.py` is NOT modified — all delegation happens through imports"
    - "Resume detects chain state from DB and continues from the interrupted step"
    - "Logging writes to logs/mc-cli-YYYYMMDD.log with timestamps and cost summary"
    - "Background execution spawns a detached process with PID tracking"
    - "Single-site override changes blog_key mapping without modifying config"
    - "All 130 existing pytest tests still pass; N new tests added"
  artifacts:
    - path: "cli/mc.py"
      provides: "main() — CLI entry point, argument parsing, pipeline orchestration"
      min_lines: 250
    - path: "cli/mc.py"
      provides: "_resume_chain() — chain state detection and step skipping"
      pattern: "def _resume_chain"
    - path: "cli/mc.py"
      provides: "_setup_logging() — file + stdout dual logging"
      pattern: "def _setup_logging"
    - path: "test_cli_mc.py"
      provides: "Unit tests for CLI argument parsing, resume logic, logging, background"
      min_lines: 80
  key_links:
    - from: "cli/mc.py main()"
      to: "chain_publisher.run_chain()"
      via: "import"
      pattern: "from chain_publisher import run_chain"
    - from: "cli/mc.py _resume_chain()"
      to: "chain_db.get_chain() / get_chain_posts()"
      via: "import"
      pattern: "from chain_db import get_chain"
---

# Phase 14 — CLI 단일 진입점 `mc <keyword>`

<objective>
Phase 1–13에서 `chain_publisher.py --seed "키워드" --draft --image --publish`로 3개 커맨드를 순차 실행. Phase 14는 `mc 업클로젯` 하나로 모든 스텝을 자동 실행하는 단일 진입점 CLI를 구축한다.

**설계 원칙**: `chain_publisher.py`를 수정하지 않고 import하여 재사용. 신규 파일만 생성. 기존 130/130 pytest 완전 보존.

**본 PLAN.md는 기획 문서입니다.** 구현은 추후 세션에서 실행합니다.
</objective>

## Phase Goal

**As a** blog operator running the mc pipeline, **I want to** type `mc 업클로젯` and have the entire chain derived, drafted, imaged, and published automatically, **so that** I don't need to remember 3+ separate commands and their flags.

## Multi-Source Coverage Audit

| Source Item | Source Type | Covered By | Notes |
|-------------|-------------|------------|-------|
| R1: `mc <keyword>` full pipeline | CONTEXT | Wave 1, Task 1.1 | Calls derive→draft→image→publish sequentially |
| R2: Stage flags (dry-run/draft/image) | CONTEXT | Wave 1, Task 1.1 | argparse with stage flags |
| R3: Resume (`--chain-id N --resume`) | CONTEXT | Wave 2, Task 2.1 | DB state detection → skip completed steps |
| R4: Single-site override (`--site`) | CONTEXT | Wave 1, Task 1.1 | blog_overrides dict passed to publish_chain |
| R5: Background (`--background`) | CONTEXT | Wave 3, Task 3.2 | subprocess.Popen or os.fork |
| R6: Logging (`logs/mc-cli-*.log`) | CONTEXT | Wave 3, Task 3.1 | logging module, file+stdout, cost summary |
| `chain_publisher.py` untouched | CONSTRAINT | All waves | Import only — no monkey-patching |
| 19/27 guard untouched | CONSTRAINT | All waves | Not in scope |
| W1–W6 / Phase 11–13 code untouched | CONSTRAINT | All waves | Only new files |
| 130/130 pytest preserved | CONSTRAINT | All waves | +N new tests for new code |
| Phase 14.1 carry-over | CONTEXT | — | Noted, no task in this phase |

**Status:** ✅ All items covered. No gaps.

---

## Wave Structure

| Wave | Plans | Requirement | Files |
|------|-------|-------------|-------|
| **1** | 14-01-PLAN.md | **R1, R2, R4** (CLI wrapper + basic flags) | cli/mc.py, test_cli_mc.py |
| **2** | 14-01-PLAN.md | **R3** (Resume) | cli/mc.py, test_cli_mc.py |
| **3** | 14-01-PLAN.md | **R5, R6** (Logging + Background) | cli/mc.py, test_cli_mc.py |
| **4** | 14-01-PLAN.md | **Meta** (Install + Deploy) | setup.py / pyproject.toml |

**Rationale:** Wave 1(기본 CLI) → Wave 2(Resume) → Wave 3(로깅/백그라운드) → Wave 4(설치/배포). 기본 기능이 먼저 동작해야 resume/로깅/설치가 의미 있음.

---

## Wave 1 — CLI Wrapper + Basic Flags (R1, R2, R4)

### Context

`chain_publisher.py`의 `run_chain()` 함수는 이미 `--seed`, `--dry-run`, `--draft`, `--image`, `--publish`를 처리함. Wave 1은 이 함수를 import하여 `mc <keyword>` 인터페이스로 래핑한다.

핵심 결정: **import delegation** vs **subprocess delegation**

| 방식 | 장점 | 단점 |
|------|------|------|
| **Import** (권장) | 타입 체크, 로깅 컨텍스트 공유, 오류 전파 쉬움 | Python import chain 의존 |
| Subprocess | 완전 격리, chain_publisher.py 변경에 안전 | 출력 파싱 필요, 로깅 분리 |

**결정**: Import delegation 채택. `from chain_publisher import run_chain, generate_chain_images, publish_chain, inject_cards_chain, _NON_INTENDED_CHAINS` — 이미 안정적인 API.

### Tasks

<task type="plan-only">
<name>Task 1.1: Create cli/mc.py with argparse + pipeline wrapper</name>
<files>
  - cli/mc.py (created)
</files>
<action>
Create `cli/mc.py` with the following structure:

```python
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

# ── Delegation: import from chain_publisher (NO modifications to that file) ──
# These imports happen inside functions to avoid side effects at module load.
# Run from project root so relative imports work.

def _setup_logging() -> logging.Logger:
    """Set up dual logging: stdout + file."""
    ...

def main():
    parser = argparse.ArgumentParser(
        prog="mc",
        description="Manual Chain — publish a 3-deep blog chain from one keyword",
    )
    parser.add_argument("keyword", nargs="?", help="Seed keyword for chain")
    parser.add_argument("--chain-id", type=int, help="Existing chain ID (for --resume)")
    
    # Pipeline stage flags
    parser.add_argument("--dry-run", action="store_true", help="Derive only")
    parser.add_argument("--draft", action="store_true", help="Derive + draft")
    parser.add_argument("--image", action="store_true", help="Derive + draft + image")
    parser.add_argument("--skip-publish", action="store_true", help="Same as --image")
    parser.add_argument("--publish", action="store_true", help="Full pipeline (default)")
    
    # Resume & override
    parser.add_argument("--resume", action="store_true", help="Resume from interrupted step")
    parser.add_argument("--site", type=str, choices=["rotcha", "infohot", "techpawz", "aikorea24"],
                        help="Single site override")
    
    # Execution mode
    parser.add_argument("--background", action="store_true", help="Run in background")
    
    args = parser.parse_args()
    
    if not args.keyword and not args.chain_id:
        parser.print_help()
        sys.exit(1)
    
    # Logging setup
    logger = _setup_logging()
    
    # Route to handler
    if args.resume and args.chain_id:
        _resume_chain(args.chain_id, args.site, logger)
    elif args.chain_id and args.draft:
        _draft_existing(args.chain_id, logger)
    elif args.chain_id and args.image:
        _image_existing(args.chain_id, logger)
    elif args.keyword:
        _run_full(args.keyword, args, logger)
    else:
        parser.print_help()
        sys.exit(1)


def _run_full(keyword: str, args, logger: logging.Logger) -> int:
    """R1: mc <keyword> → full pipeline."""
    from chain_publisher import run_chain
    ...
```

**Key implementation details:**

1. **Pipeline stage mapping**:
   - `--dry-run` → `run_chain(keyword, dry_run=True)`
   - `--draft` → `run_chain(keyword, draft_only=True)`
   - `--image` / `--skip-publish` → `run_chain(keyword, image_only=True)`
   - `--publish` (default) → `run_chain(keyword, publish_mode="auto")`

2. **Single-site override** (`--site`):
   ```python
   blog_overrides = {1: args.site, 2: args.site, 3: args.site} if args.site else None
   ```

3. **Return value**: 체인 ID를 stdout에 출력하고 로그에 기록. 0 반환 시 실패로 간주.

4. **Project root detection**: `cli/mc.py`가 `project_root/cli/mc.py`에 위치 → `sys.path`에 project_root 추가 필요.

5. **No `chain_publisher.py` modification**: import만. 단, `chain_publisher.py`가 `if __name__ == "__main__"`으로만 실행되는 문제 없음 — import 시 실행 안 됨.

6. **SITE_MAP for --site**:
   ```python
   _SITE_BLOG_KEY = {
       "rotcha": "rotcha",
       "infohot": "infohot",
       "techpawz": "techpawz",
       "aikorea24": "aikorea24",
   }
   ```
</action>
<verify>
<automated>cd /Users/twinssn/projects2/mc && python -c "import ast; ast.parse(open('cli/mc.py').read()); print('Syntax OK')"</automated>
</verify>
<done>cli/mc.py exists with argparse, main(), _run_full(); syntax valid; imports chain_publisher functions.</done>
</task>

<task type="plan-only">
<name>Task 1.2: Basic CLI unit tests</name>
<files>
  - test_cli_mc.py (created)
</files>
<action>
Create `test_cli_mc.py` with:

1. **`test_argparse_keyword`** — `["업클로젯"]` → args.keyword == "업클로젯"
2. **`test_argparse_dry_run`** — `["업클로젯", "--dry-run"]` → args.dry_run == True
3. **`test_argparse_draft`** — `["업클로젯", "--draft"]` → args.draft == True
4. **`test_argparse_image`** — `["업클로젯", "--image"]` → args.image == True
5. **`test_argparse_skip_publish`** — `["업클로젯", "--skip-publish"]` → args.skip_publish == True
6. **`test_argparse_site`** — `["업클로젯", "--site", "rotcha"]` → args.site == "rotcha"
7. **`test_argparse_resume`** — `["--chain-id", "66", "--resume"]` → args.chain_id == 66, args.resume == True
8. **`test_argparse_background`** — `["업클로젯", "--background"]` → args.background == True
9. **`test_argparse_no_args`** — `[]` → sys.exit(1) (help)
10. **`test_argparse_chain_id_only`** — `["--chain-id", "66"]` → help (no resume/draft/image flag)
11. **`test_run_full_calls_run_chain`** — mock `chain_publisher.run_chain`, verify called with correct args
12. **`test_site_override_mapping`** — `--site rotcha` → blog_overrides = {1: "rotcha", 2: "rotcha", 3: "rotcha"}

**Mock strategy**: `unittest.mock.patch('cli.mc.run_chain')` 또는 `chain_publisher.run_chain`.
</action>
<verify>
<automated>cd /Users/twinssn/projects2/mc && python -m pytest test_cli_mc.py -x -q 2>&1 | tail -3</automated>
</verify>
<done>test_cli_mc.py has 12+ tests for argparse parsing, pipeline routing, site override.</done>
</task>

<verification>
### Wave 1 Verification
1. [ ] `python -c "import ast; ast.parse(open('cli/mc.py').read())"` — syntax OK
2. [ ] `python -m pytest test_cli_mc.py -x -q` — all CLI tests pass
3. [ ] `python -c "import sys; sys.path.insert(0, '.'); from cli.mc import main; print('OK')"` — imports succeed
4. [ ] `grep -n 'from chain_publisher import\|import chain_publisher' cli/mc.py` — delegation via import
5. [ ] `grep -n 'chain_publisher\.py' cli/mc.py | grep -v import` — NO modification of chain_publisher.py
</verification>

---

## Wave 2 — Resume (R3)

### Context

`--resume`는 체인 상태를 DB에서 읽어 중단 지점부터 재개한다. 완료된 스텝은 건너뛰고 미완료 스텝만 실행.

### State Detection Logic

```
chain = db.get_chain(chain_id)
posts = db.get_chain_posts(chain_id)

if chain['status'] == 'completed':
    → "Chain already complete, nothing to resume"
    → exit(0)

if any draft_md is missing in posts:
    → draft_chain(chain_id, chain['seed'])
else:
    → skip draft (all posts have draft_md)

if any content_image_path is missing:
    → generate_chain_images(chain_id)
else:
    → skip image (all posts have images)

if any published_url is missing:
    → publish_chain(chain_id, mode="auto")
    → inject_cards_chain(chain_id)
else:
    → skip publish (all posts published)
```

### Tasks

<task type="plan-only">
<name>Task 2.1: Implement _resume_chain()</name>
<files>
  - cli/mc.py (modified — add _resume_chain function)
</files>
<action>
Add `_resume_chain()` to `cli/mc.py`:

```python
def _resume_chain(chain_id: int, site_override: str | None, logger: logging.Logger) -> bool:
    """
    R3: Resume chain from interrupted step.
    Returns True if resume completed successfully.
    """
    import chain_db as db
    from chain_publisher import _preflight_check, generate_chain_images, publish_chain, inject_cards_chain
    from chain_drafter import draft_chain
    
    chain = db.get_chain(chain_id)
    if not chain:
        logger.error(f"Chain #{chain_id} not found")
        return False
    
    if chain["status"] == "completed":
        logger.info(f"Chain #{chain_id} already completed. Nothing to resume.")
        return True
    
    posts = db.get_chain_posts(chain_id)
    seed = chain["seed"]
    
    # Step 1: Draft — missing draft_md
    missing_draft = [p for p in posts if not p.get("draft_md")]
    if missing_draft:
        logger.info(f"Drafting chain #{chain_id} ({len(missing_draft)}/{len(posts)} posts missing)")
        draft_chain(chain_id, seed)
        posts = db.get_chain_posts(chain_id)  # refresh
    else:
        logger.info(f"All {len(posts)} posts have drafts — skipping")
    
    # Step 2: Image — missing content_image_path
    missing_image = [p for p in posts if not p.get("image_url")]
    if missing_image:
        logger.info(f"Generating images for chain #{chain_id} ({len(missing_image)}/{len(posts)} missing)")
        if not _preflight_check():
            logger.warning("Preflight check failed — image generation may fail")
        generate_chain_images(chain_id)
        posts = db.get_chain_posts(chain_id)  # refresh
    else:
        logger.info(f"All {len(posts)} posts have images — skipping")
    
    # Step 3: Publish — missing published_url
    blog_overrides = _build_blog_overrides(site_override)
    missing_publish = [p for p in posts if not p.get("published_url")]
    if missing_publish:
        logger.info(f"Publishing chain #{chain_id} ({len(missing_publish)}/{len(posts)} missing)")
        publish_chain(chain_id, mode="auto", blog_overrides=blog_overrides)
        inject_cards_chain(chain_id)
    else:
        logger.info(f"All {len(posts)} posts published — nothing to resume")
    
    logger.info(f"Resume complete for chain #{chain_id}")
    return True
```
</action>
<verify>
<automated>cd /Users/twinssn/projects2/mc && python -c "import ast; ast.parse(open('cli/mc.py').read()); print('Syntax OK')"</automated>
</verify>
<done>_resume_chain() reads chain state from DB, determines incomplete steps, delegates to chain_publisher functions.</done>
</task>

<task type="plan-only">
<name>Task 2.2: Resume unit tests</name>
<files>
  - test_cli_mc.py (modified — add resume tests)
</files>
<action>
Add tests to `test_cli_mc.py`:

1. **`test_resume_all_complete`** — Mock chain + posts as all complete → no calls to draft/image/publish
2. **`test_resume_missing_draft`** — Seed only, no draft → calls `draft_chain()`
3. **`test_resume_missing_image`** — Has draft, no image → calls `generate_chain_images()`
4. **`test_resume_missing_publish`** — Has draft+image, no URL → calls `publish_chain()`
5. **`test_resume_already_completed`** — Status=completed → exit early
6. **`test_resume_partial_steps`** — 2/3 posts complete, 1 missing → partial execution
7. **`test_resume_invalid_chain`** — Chain not found → error
8. **`test_preflight_check_called_before_image`** — Preflight check is called when image is missing
</action>
<verify>
<automated>cd /Users/twinssn/projects2/mc && python -m pytest test_cli_mc.py -x -q -k resume 2>&1 | tail -3</automated>
</verify>
<done>Resume tests cover: all-complete skip, missing-draft, missing-image, missing-publish, already-completed, partial steps, invalid chain.</done>
</task>

<verification>
### Wave 2 Verification
1. [ ] `python -m pytest test_cli_mc.py -x -q -k resume` — all resume tests pass
2. [ ] `python -c "import ast; src=open('cli/mc.py').read(); assert 'def _resume_chain' in src; print('OK')"` — function exists
3. [ ] `python -c "from chain_db import get_conn; c=get_conn(); r=c.execute('SELECT status FROM chains WHERE id=66').fetchone(); print(r[0] if r else 'not found')"` — real chain state readable
</verification>

---

## Wave 3 — Logging + Background (R5, R6)

### Context

Logging은 Python `logging` 모듈 사용. 파일 핸들러(자세한 로그) + stdout 핸들러(요약) 동시 출력.

### Tasks

<task type="plan-only">
<name>Task 3.1: Implement _setup_logging() + cost summary</name>
<files>
  - cli/mc.py (modified — add logging setup + cost summary)
</files>
<action>
Implement `_setup_logging()`:

```python
import logging
from datetime import datetime
from pathlib import Path

_LOG_DIR = Path(__file__).parent.parent / "logs"
_LOG_FILE = _LOG_DIR / f"mc-cli-{datetime.now().strftime('%Y%m%d')}.log"

def _setup_logging() -> logging.Logger:
    """R6: Dual logging — verbose file + concise stdout."""
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    logger = logging.getLogger("mc")
    logger.setLevel(logging.DEBUG)
    
    # File handler (DEBUG level, all details)
    fh = logging.FileHandler(str(_LOG_FILE), encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    
    # Stdout handler (INFO level, user-facing)
    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(logging.INFO)
    sh.setFormatter(logging.Formatter("[mc] %(message)s"))
    
    logger.addHandler(fh)
    logger.addHandler(sh)
    
    return logger


def _log_cost_summary(logger, chain_id: int, start_time: datetime):
    """Log cost summary at the end of a pipeline run."""
    import chain_db as db
    posts = db.get_chain_posts(chain_id)
    elapsed = (datetime.now() - start_time).total_seconds()
    
    # Count image types
    image_count = sum(1 for p in posts if p.get("image_url"))
    
    # Published URLs
    urls = [p.get("published_url", "N/A") for p in posts]
    
    logger.info(f"{'='*50}")
    logger.info(f"Cost Summary — Chain #{chain_id}")
    logger.info(f"  Elapsed: {elapsed:.1f}s")
    logger.info(f"  Posts: {len(posts)}")
    logger.info(f"  Images: {image_count}")
    logger.info(f"  URLs:")
    for url in urls:
        logger.info(f"    - {url}")
    logger.info(f"  Log file: {_LOG_FILE}")
    logger.info(f"{'='*50}")
```

**Log file location**: `logs/mc-cli-20260722.log` (프로젝트 루트 기준)

**Log entry examples**:
```
2026-07-22 10:30:00 [INFO] Starting chain: 업클로젯
2026-07-22 10:30:01 [INFO] Derive complete: chain #66
2026-07-22 10:30:05 [INFO] Draft complete: 3 posts
2026-07-22 10:30:06 [INFO] Schema validation passed: 3/3
2026-07-22 10:30:10 [INFO] Image generation: photo→unsplash, photo→pexels, chart→pillow
2026-07-22 10:30:15 [INFO] Publish: step 3 → techpawz → https://techpawz.com/.../ ✅
2026-07-22 10:30:20 [INFO] Publish: step 2 → infohot → https://informationhot.kr/.../ ✅
2026-07-22 10:30:25 [INFO] Publish: step 1 → rotcha → https://rotcha.kr/.../ ✅
2026-07-22 10:30:26 [INFO] Card injection: 2/2 inserted
2026-07-22 10:30:26 [INFO] ==================================================
2026-07-22 10:30:26 [INFO] Cost Summary — Chain #66
2026-07-22 10:30:26 [INFO]   Elapsed: 26.0s
2026-07-22 10:30:26 [INFO]   Posts: 3
2026-07-22 10:30:26 [INFO]   Images: 3
2026-07-22 10:30:26 [INFO]   URLs:
2026-07-22 10:30:26 [INFO]     - https://techpawz.com/posts/.../
2026-07-22 10:30:26 [INFO]     - https://informationhot.kr/posts/.../
2026-07-22 10:30:26 [INFO]     - https://rotcha.kr/posts/.../
2026-07-22 10:30:26 [INFO] ==================================================
```
</action>
<verify>
<automated>cd /Users/twinssn/projects2/mc && python -c "import ast; src=open('cli/mc.py').read(); assert 'def _setup_logging' in src; assert '_log_cost_summary' in src; print('OK')"</automated>
</verify>
<done>_setup_logging() and _log_cost_summary() exist; log file path is logs/mc-cli-YYYYMMDD.log.</done>
</task>

<task type="plan-only">
<name>Task 3.2: Background execution support</name>
<files>
  - cli/mc.py (modified — add --background flag handling)
</files>
<action>
Implement `--background` handling in `main()`:

```python
if args.background and args.keyword:
    _run_background(args.keyword, args, logger)
    return

def _run_background(keyword: str, args, logger: logging.Logger) -> int:
    """R5: Fork/spawn detached process for background execution."""
    import subprocess
    import sys
    
    pid_file = Path("logs") / f"mc-bg-{datetime.now().strftime('%Y%m%d_%H%M%S')}.pid"
    
    # Build command line (reconstruct argv without --background)
    cmd = [sys.executable, "-m", "cli.mc", keyword]
    if args.dry_run:
        cmd.append("--dry-run")
    if args.draft:
        cmd.append("--draft")
    if args.image or args.skip_publish:
        cmd.append("--image")
    if args.site:
        cmd.extend(["--site", args.site])
    
    # Detach with nohup
    log_file = str(_LOG_FILE)
    with open(log_file, "a") as log_f:
        proc = subprocess.Popen(
            cmd,
            stdout=log_f,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,  # detach from parent session
        )
    
    pid_file.write_text(str(proc.pid))
    logger.info(f"Background process started — PID: {proc.pid}")
    logger.info(f"Log: {_LOG_FILE}")
    logger.info(f"PID file: {pid_file}")
    logger.info(f"Tail: tail -f {_LOG_FILE}")
    return proc.pid
```
</action>
<verify>
<automated>cd /Users/twinssn/projects2/mc && python -c "import ast; src=open('cli/mc.py').read(); assert 'def _run_background' in src; print('OK')"</automated>
</verify>
<done>_run_background() uses subprocess.Popen with detached session; PID + log file path printed.</done>
</task>

<task type="plan-only">
<name>Task 3.3: Logging + background tests</name>
<files>
  - test_cli_mc.py (modified — add logging + background tests)
</files>
<action>
Add tests to `test_cli_mc.py`:

1. **`test_setup_logging_creates_file`** — `_setup_logging()` 호출 후 `logs/` 디렉토리 생성 확인
2. **`test_setup_logging_dual_handler`** — 로거에 2개 핸들러(파일+stdout) 존재 확인
3. **`test_log_cost_summary_output`** — `_log_cost_summary()` 호출 시 예상 문자열 포함
4. **`test_background_subprocess`** — `--background` → `subprocess.Popen` 호출 확인 (mock)
5. **`test_background_pid_file`** — PID 파일 생성 확인
6. **`test_background_detached`** — `start_new_session=True`로 호출되는지 확인
</action>
<verify>
<automated>cd /Users/twinssn/projects2/mc && python -m pytest test_cli_mc.py -x -q -k "logging or background" 2>&1 | tail -3</automated>
</verify>
<done>Logging + background tests cover file creation, dual handlers, cost summary output, subprocess mock, PID file, detached session.</done>
</task>

<verification>
### Wave 3 Verification
1. [ ] `python -m pytest test_cli_mc.py -x -q -k "logging or background"` — all logging/background tests pass
2. [ ] `python -c "from cli.mc import _setup_logging; l=_setup_logging(); print(len(l.handlers))"` — 2 handlers confirmed
3. [ ] `ls logs/ | grep mc-cli-` — log directory created (after test)
4. [ ] `grep 'start_new_session' cli/mc.py` — background uses detached session
</verification>

---

## Wave 4 — Install + Deploy (Meta)

### Context

`mc` 명령어를 `which mc`로 감지 가능하게 설치 필요. `pip install -e .` 방식 채택.

### Tasks

<task type="plan-only">
<name>Task 4.1: Add console_scripts entry point</name>
<files>
  - setup.py (created if not exists) OR pyproject.toml (modified if exists)
</files>
<action>
Add console_scripts entry point to `setup.py` (or pyproject.toml):

```python
# setup.py
from setuptools import setup, find_packages

setup(
    name="mc-cli",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    python_requires=">=3.10",
    entry_points={
        "console_scripts": [
            "mc = cli.mc:main",
        ],
    },
    install_requires=[
        # runtime dependencies are already in requirements.txt / installed
    ],
)
```

Installation:
```bash
pip install -e /Users/twinssn/projects2/mc
```

Post-install verification:
```bash
which mc  # → /Users/twinssn/.../bin/mc
mc --help  # → usage text
```

**pyproject.toml alternative** (if `pyproject.toml` already exists):
```toml
[project.scripts]
mc = "cli.mc:main"
```
</action>
<verify>
<automated>cd /Users/twinssn/projects2/mc && pip install -e . 2>&1 | tail -5 && which mc && mc --help</automated>
</verify>
<done>pip install -e . completes; `which mc` returns path; `mc --help` shows usage.</done>
</task>

<task type="plan-only">
<name>Task 4.2: Shell wrapper alternative (fallback)</name>
<files>
  - (no new file — shell wrapper created manually)
</files>
<action>
If `pip install -e .` is not desired, create a shell wrapper:

```bash
# ~/bin/mc (or /usr/local/bin/mc)
#!/bin/bash
exec python3 /Users/twinssn/projects2/mc/cli/mc.py "$@"
```

```bash
chmod +x ~/bin/mc
export PATH="$HOME/bin:$PATH"
```
</action>
<verify>
<automated>mc --help 2>&1 | head -5</automated>
</verify>
<done>Shell wrapper or pip entry point makes `mc` available via PATH; `which mc` works.</done>
</task>

<verification>
### Wave 4 Verification
1. [ ] `which mc` — mc command found in PATH
2. [ ] `mc --help` — help text printed
3. [ ] `mc 업클로젯 --dry-run` — dry-run executes (mock or real)
4. [ ] `pip list | grep mc-cli` — pip package installed (if using pip method)
</verification>

---

## Wave Sequencing

```
Wave 1 (CLI wrapper): Task 1.1 → Task 1.2
       ↓
Wave 2 (Resume):     Task 2.1 → Task 2.2
       ↓
Wave 3 (Logging/BG): Task 3.1 → Task 3.2 → Task 3.3
       ↓
Wave 4 (Install):    Task 4.1 → Task 4.2
```

각 Wave는 이전 Wave의 완료에 의존하지 않음 (독립적 개발 가능). 단, Wave 4(설치)는 Wave 1 파일이 존재해야 함.

---

## Full Test Suite

<task type="plan-only">
<name>Task 5: Full test suite — target 130+N / 130+N</name>
<files>
  - (no new code — run tests only)
</files>
<action>
Run the complete test suite:

```bash
cd /Users/twinssn/projects2/mc && python -m pytest -x -q
```

Expected: 130/N existing + N new = 130+N total.

New test count breakdown:
| Source | Tests | Files |
|--------|-------|-------|
| Task 1.2: CLI argparse + routing | 12 | test_cli_mc.py |
| Task 2.2: Resume logic | 8 | test_cli_mc.py |
| Task 3.3: Logging + background | 6 | test_cli_mc.py |
| **Total new** | **26** | |
| **Existing** | **130** | |
| **Grand total** | **156** | |

If any existing test fails, regression — fix immediately.
If test count differs, count and report cause.
</action>
<verify>
<automated>cd /Users/twinssn/projects2/mc && python -m pytest -x -q 2>&1 | tail -3</automated>
</verify>
<done>Full test suite passes at 130+N / 130+N.</done>
</task>

---

## Phase 14.1 — 이월 항목 (v1.1, not in scope for Phase 14)

The following items are NOT implemented in Phase 14. Planned for Phase 14.1:

1. **cron/launchd 스케줄링** — `mc --schedule --cron "0 9 * * *"` 통합. 현재는 `chain_publisher.py --schedule`으로 분리.
2. **Dashboard CLI** — `mc status`, `mc list`, `mc stats` — 체인 목록 + 상태 + 통계.
3. **`audit_chain.py` 통합** — `mc audit --chain-id N` — 체인 QA 검사.
4. **Slack/email 알림** — 발행 완료 시 알림 전송.

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **chain_publisher.py import side effects** | Medium | High — module-level code runs on import | Verify `chain_publisher.py` has `if __name__ == "__main__"` guard (line 661 has it ✅) |
| **Subprocess --background orphan process** | Low | Low — PID file tracks; kill by PID | `start_new_session=True` prevents terminal dependency |
| **Resume misdetects step completion** | Medium | Medium — duplicate publish | Check multiple DB fields (draft_md + image_meta.content_image_path + published_url) |
| **Log file rotation absent** | Low | Low — daily file; manual cleanup | Single log per day; can add RotatingFileHandler later |
| **pip install -e . path dependency** | Low | Low — editable install ties to project path | Shell wrapper alternative always available |
| **130-test regression from new imports** | Low | High — pipeline breakage | All new code in `cli/mc.py` and `test_cli_mc.py`; `chain_publisher.py` untouched |
| **which mc not found after install** | Low | Medium — user confusion | Verify in Wave 4; document shell wrapper fallback |

---

## Success Criteria

- [ ] **Wave 1**: `cli/mc.py` with `main()`, `_run_full()`, argparse for all flags; `test_cli_mc.py` with 12+ tests
- [ ] **Wave 2**: `_resume_chain()` with DB state detection; 8 resume tests
- [ ] **Wave 3**: `_setup_logging()` with dual handlers; `_run_background()` with subprocess; 6 logging/background tests
- [ ] **Wave 4**: `pip install -e .` or shell wrapper → `which mc` works → `mc --help` prints usage
- [ ] **pytest 130+N / 130+N** (`python -m pytest -x -q`) — all existing + new tests pass
- [ ] **`chain_publisher.py` not modified** — `git diff chain_publisher.py` shows 0 changes
- [ ] **19/27 guard, FM preservation, W1-W6, Phase 11-13 code not modified**
- [ ] **Phase 14.1 items noted but NOT implemented**
