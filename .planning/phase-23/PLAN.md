# PLAN.md — Phase 23: 인프라 안정화 + 자동 스케줄링

**Phase:** 23  
**Created:** 2026-07-26  
**Status:** Draft  
**Mode:** execute

---

## Overview

3개 Task로 구성된 인프라 안정화 + 자동 스케줄링 파이프라인 구축:

| Task | 내용 | 예상 파일 변경 |
|------|------|----------------|
| **Task 1** | 키워드 큐 시스템 | `config/keyword_queue.yaml` (선택), `chain_db.py` (DB 마이그레이션), `mc/queue.py` (신규), `cli/mc.py` (서브커맨드 추가) |
| **Task 2** | 스케줄러 설정 + 로그 로테이션 | `cli/mc.py` (schedule 서브커맨드), `scheduler/launchd_manager.py` (확장), `scheduler/cron_manager.py` (확장) |
| **Task 3** | 에러 알림 + 상태 확인 | `config/notify.yaml`, `mc/notify.py` (신규), `cli/mc.py` (status 서브커맨드) |

---

## Task 1: 키워드 큐 시스템

### 1.1 DB 마이그레이션: `keyword_queue` 테이블 추가 (`chain_db.py`)

```python
# MIGRATIONS_SQL에 추가
"CREATE TABLE IF NOT EXISTS keyword_queue ("
"  id INTEGER PRIMARY KEY AUTOINCREMENT,"
"  keyword TEXT NOT NULL UNIQUE,"
"  category TEXT,"
"  priority INTEGER DEFAULT 3,"
"  status TEXT NOT NULL DEFAULT 'pending',"  # pending/processing/done/failed
"  created_at TEXT NOT NULL,"
"  processed_at TEXT,"
"  error_msg TEXT"
")",
"CREATE INDEX IF NOT EXISTS idx_keyword_queue_status ON keyword_queue(status)",
"CREATE INDEX IF NOT EXISTS idx_keyword_queue_priority ON keyword_queue(priority DESC, created_at)",
```

### 1.2 `mc/queue.py` 신규 모듈 생성

```python
"""
mc/queue.py — 키워드 큐 관리
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict

from mc_paths import DB_CANDIDATES  # 또는 기존 chain_db.get_conn()

DB_PATH = next((p for p in DB_CANDIDATES if p.exists()), DB_CANDIDATES[0])

def get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def add_keyword(keyword: str, category: str = None, priority: int = 3) -> Dict:
    """키워드 큐에 추가. 중복 시 warning 반환."""
    conn = get_conn()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        conn.execute(
            "INSERT INTO keyword_queue (keyword, category, priority, status, created_at) VALUES (?, ?, ?, 'pending', ?)",
            (keyword, category, priority, now)
        )
        conn.commit()
        return {"success": True, "keyword": keyword, "status": "added"}
    except sqlite3.IntegrityError:
        # 중복 확인: 기존 상태 조회
        row = conn.execute("SELECT status, category FROM keyword_queue WHERE keyword = ?", (keyword,)).fetchone()
        return {"success": False, "keyword": keyword, "status": "duplicate", "existing_status": row["status"] if row else None}
    finally:
        conn.close()

def get_next_keyword() -> Optional[Dict]:
    """우선순위 높은 pending 키워드 1개 반환 후 processing으로 변경."""
    conn = get_conn()
    row = conn.execute(
        "SELECT id, keyword, category, priority FROM keyword_queue WHERE status = 'pending' ORDER BY priority DESC, created_at LIMIT 1"
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE keyword_queue SET status = 'processing', processed_at = ? WHERE id = ?",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), row["id"])
        )
        conn.commit()
        conn.close()
        return dict(row)
    conn.close()
    return None

def mark_done(keyword: str):
    """처리 완료: done으로 변경."""
    conn = get_conn()
    conn.execute(
        "UPDATE keyword_queue SET status = 'done', processed_at = ? WHERE keyword = ?",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), keyword)
    )
    conn.commit()
    conn.close()

def mark_failed(keyword: str, error_msg: str):
    """처리 실패: failed로 변경 + 에러 메시지 기록."""
    conn = get_conn()
    conn.execute(
        "UPDATE keyword_queue SET status = 'failed', processed_at = ?, error_msg = ? WHERE keyword = ?",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), error_msg, keyword)
    )
    conn.commit()
    conn.close()

def list_queue(status: str = None) -> List[Dict]:
    """큐 목록 조회."""
    conn = get_conn()
    if status:
        rows = conn.execute("SELECT * FROM keyword_queue WHERE status = ? ORDER BY priority DESC, created_at", (status,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM keyword_queue ORDER BY priority DESC, created_at").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def remove_keyword(keyword: str) -> bool:
    """큐에서 키워드 제거."""
    conn = get_conn()
    cur = conn.execute("DELETE FROM keyword_queue WHERE keyword = ?", (keyword,))
    conn.commit()
    conn.close()
    return cur.rowcount > 0
```

### 1.3 `cli/mc.py`에 queue 서브커맨드 추가

```python
# cli/mc.py 내 서브파서 추가

queue_parser = subparsers.add_parser("queue", help="키워드 큐 관리")
queue_sub = queue_parser.add_subparsers(dest="queue_action")

# queue add
add_p = queue_sub.add_parser("add", help="키워드 큐에 추가")
add_p.add_argument("keyword", help="시드 키워드")
add_p.add_argument("--category", help="카테고리 (travel, stock, automotive, real_estate, etc)")
add_p.add_argument("--priority", type=int, default=3, choices=range(1, 6), help="우선순위 1~5 (높을수록 먼저)")

# queue list
list_p = queue_sub.add_parser("list", help="큐 목록 조회")
list_p.add_argument("--status", choices=["pending", "processing", "done", "failed"], help="상태 필터")

# queue next
next_p = queue_sub.add_parser("next", help="다음 처리할 키워드 1개 조회 (processing으로 변경)")

# queue remove
remove_p = queue_sub.add_parser("remove", help="큐에서 키워드 제거")
remove_p.add_argument("keyword", help="제거할 키워드")
```

```python
# 핸들러 함수들 (cli/mc.py 내)

def _cmd_queue(args):
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
            return
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
            print(f"[queue] ⚠️ Not found: {args.keyword}")
```

### 1.4 `mc auto` 구현 — 큐에서 꺼내서 `run_chain()` 실행

```python
# cli/mc.py 내

def _cmd_auto(args):
    """mc auto — 큐에서 다음 키워드를 꺼내 run_chain() 실행."""
    from mc.queue import get_next_keyword, mark_done, mark_failed
    from chain_publisher import run_chain
    import traceback
    
    item = get_next_keyword()
    if not item:
        print("[auto] No pending keywords in queue. Exiting.")
        return 0
    
    keyword = item["keyword"]
    print(f"[auto] Processing: {keyword} (id={item['id']}, priority={item['priority']})")
    
    try:
        chain_id = run_chain(keyword, publish_mode="auto", use_context=True)
        if chain_id:
            mark_done(keyword)
            print(f"[auto] ✅ Chain #{chain_id} completed for '{keyword}'")
        else:
            mark_failed(keyword, "run_chain returned None")
            print(f"[auto] ❌ Failed: run_chain returned None")
            return 1
    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}"
        traceback.print_exc()
        mark_failed(keyword, error_msg)
        print(f"[auto] ❌ Failed: {error_msg}")
        # 알림 전송 (실패해도 발행 중단 안 함)
        try:
            from mc.notify import send_alert
            send_alert(f"mc auto failed: {keyword}", error_msg, level="error")
        except Exception:
            pass
        return 1
    
    return 0
```

### 1.5 `mc` 메인 파서에 `auto` 서브커맨드 추가

```python
# cli/mc.py 메인 파서에 추가
auto_p = subparsers.add_parser("auto", help="큐에서 다음 키워드 꺼내서 자동 발행")
```

---

## Task 2: 스케줄러 설정 + 로그 로테이션

### 2.1 `scheduler/launchd_manager.py` 확장 — `mc auto` 실행용

```python
# scheduler/launchd_manager.py 수정

import os
import subprocess
import plistlib
from pathlib import Path

MC_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = MC_ROOT / "logs"
LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"

def add_auto_task(
    hour: int = 9,
    minute: int = 0,
    label: str = "com.mc.auto",
    python_path: str = None,
    project_root: str = None,
):
    """launchd plist 생성 및 load (mc auto 실행)."""
    project_root = project_root or str(MC_ROOT)
    python_path = python_path or "/usr/bin/env python3"
    
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    plist_path = LAUNCH_AGENTS_DIR / f"{label}.plist"
    
    program_args = [
        python_path,
        "-m", "cli.mc",
        "auto",
    ]
    
    plist = {
        "Label": label,
        "ProgramArguments": program_args,
        "WorkingDirectory": project_root,
        "StartCalendarInterval": {"Hour": hour, "Minute": minute},
        "StandardOutPath": str(LOG_DIR / "mc-auto-%Y-%m-%d.log"),  # launchd는 %Y-%m-%d 치환 안 됨 → 별도 처리 필요
        "StandardErrorPath": str(LOG_DIR / "mc-auto-error.log"),
        "KeepAlive": False,
        "RunAtLoad": False,
        "EnvironmentVariables": {
            "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin",
        },
    }
    
    LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(plist_path, "wb") as f:
        plistlib.dump(plist, f)
    print(f"  [scheduler] ✅ plist created: {plist_path}")
    
    # launchctl load
    result = subprocess.run(
        ["launchctl", "load", str(plist_path)],
        capture_output=True, timeout=15, check=False,
    )
    if result.returncode == 0:
        print(f"  [scheduler] ✅ launchctl loaded: {label}")
    else:
        # 이미 로드된 경우 unload 후 재시도
        subprocess.run(["launchctl", "unload", str(plist_path)], capture_output=True, check=False)
        subprocess.run(["launchctl", "load", str(plist_path)], capture_output=True, check=False)
        print(f"  [scheduler] ✅ launchctl reloaded: {label}")
    
    return plist_path
```

**중요:** launchd의 `StandardOutPath`는 strftime 치환을 지원하지 않으므로, 로그 로테이션은 Task 2.3에서 별도 처리.

### 2.2 `scheduler/cron_manager.py` 확장 — `mc auto` 실행용

```python
# scheduler/cron_manager.py 의 add_task 확장

def add_auto_task(self, hour: int = 9, minute: int = 0, description: str = "mc auto daily"):
    """crontab에 mc auto 작업 추가."""
    mc_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    command = f"cd {mc_root} && /usr/bin/env python3 -m cli.mc auto >> logs/mc-auto-$(date +%Y-%m-%d).log 2>&1"
    cron_expr = f"{minute} {hour} * * *"
    self.add_task(command, cron_expr, description)
```

### 2.3 `cli/mc.py`에 schedule 서브커맨드 추가

```python
# cli/mc.py 내 서브파서 추가

schedule_parser = subparsers.add_parser("schedule", help="자동 발행 스케줄 관리")
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
```

```python
# 핸들러 함수들

def _cmd_schedule(args):
    import sys
    import platform
    
    is_macos = platform.system() == "Darwin"
    
    if args.schedule_action == "setup":
        if is_macos and not args.no_launchd:
            from scheduler.launchd_manager import add_auto_task
            add_auto_task(hour=args.hour, minute=args.minute)
        else:
            from scheduler.cron_manager import CronManager
            cm = CronManager()
            cm.add_auto_task(hour=args.hour, minute=args.minute)
        print(f"[schedule] ✅ Daily at {args.hour:02d}:{args.minute:02d} registered")
    
    elif args.schedule_action == "status":
        if is_macos:
            from scheduler.launchd_manager import LaunchdManager
            lm = LaunchdManager()
            tasks = lm.list_tasks()
            if tasks:
                for t in tasks:
                    print(f"  launchd: {t['label']} ({t['path']})")
            else:
                print("  No launchd tasks")
        else:
            from scheduler.cron_manager import CronManager
            cm = CronManager()
            tasks = cm.list_tasks()
            if tasks:
                for t in tasks:
                    print(f"  cron: {t['schedule']} → {t['command'][:60]}...")
            else:
                print("  No cron tasks")
    
    elif args.schedule_action == "remove":
        if is_macos:
            from scheduler.launchd_manager import LaunchdManager
            lm = LaunchdManager()
            for t in lm.list_tasks():
                lm.remove_task(t["label"])
                print(f"  [schedule] ✅ Removed: {t['label']}")
        else:
            from scheduler.cron_manager import CronManager
            cm = CronManager()
            for t in cm.list_tasks():
                cm.remove_task(t["command"])
                print(f"  [schedule] ✅ Removed cron task")
```

### 2.4 로그 로테이션 — `logs/mc-auto-YYYY-MM-DD.log` 일자별 분리

launchd의 `StandardOutPath`는 날짜 치환 미지원이므로, `mc auto` 실행 시 로그 파일을 날짜별로 열도록 래퍼 스크립트 또는 Python 내 로깅 설정에서 처리.

```python
# cli/mc.py — _setup_logging() 수정 (mc auto 실행 시)

def _setup_logging(auto_mode: bool = False) -> logging.Logger:
    """R6: Dual logging — verbose file + concise stdout."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    if auto_mode:
        # mc auto는 일자별 로그 파일
        log_file = LOG_DIR / f"mc-auto-{datetime.now().strftime('%Y-%m-%d')}.log"
    else:
        # 일반 mc 명령은 기존 방식
        log_file = LOG_DIR / f"mc-cli-{datetime.now().strftime('%Y%m%d')}.log"
    
    logger = logging.getLogger("mc")
    logger.setLevel(logging.DEBUG)
    
    # File handler
    fh = logging.FileHandler(str(log_file), encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    
    # Stdout handler
    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(logging.INFO)
    sh.setFormatter(logging.Formatter("[mc] %(message)s"))
    
    logger.addHandler(fh)
    logger.addHandler(sh)
    
    return logger
```

```python
# _cmd_auto에서 호출 시

def _cmd_auto(args):
    logger = _setup_logging(auto_mode=True)
    # ... 기존 로직
```

---

## Task 3: 에러 알림 + 상태 확인

### 3.1 `config/notify.yaml` 생성

```yaml
# config/notify.yaml — 알림 채널 설정

notify:
  enabled: false  # true로 설정 시 알림 활성화
  
  # Webhook 기반 (Slack, Discord, Telegram, Generic)
  webhook:
    url: ""  # 예: https://hooks.slack.com/services/... 또는 Discord webhook URL
    template: |
      *{title}*
      {detail}
      Level: {level}
      Time: {timestamp}
    timeout: 10
  
  # 이메일 (Phase 24 구현 예정)
  email:
    enabled: false
    smtp_host: ""
    smtp_port: 587
    username: ""
    password: ""
    from_addr: ""
    to_addrs: []
  
  # 알림 레벨별 필터
  levels:
    error: true
    warning: false
    info: false
```

### 3.2 `mc/notify.py` 신규 모듈 생성

```python
"""
mc/notify.py — 통합 알림 전송 모듈

알림 채널: Webhook (Slack/Discord/Telegram/Generic)
실패해도 예외를 전파하지 않고 로그만 남김.
"""

import json
import logging
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

# 설정 로드
def _load_notify_config() -> dict:
    path = Path(__file__).resolve().parent.parent / "config" / "notify.yaml"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {"notify": {"enabled": False}}


def send_alert(title: str, detail: str, level: str = "error") -> bool:
    """
    알림 전송. 실패해도 False만 반환 (예외 전파 안 함).
    
    Args:
        title: 알림 제목
        detail: 상세 내용
        level: "error" | "warning" | "info"
    
    Returns:
        성공 시 True, 실패/비활성화 시 False
    """
    config = _load_notify_config()
    notify_cfg = config.get("notify", {})
    
    if not notify_cfg.get("enabled", False):
        return False
    
    if not notify_cfg.get("levels", {}).get(level, False):
        return False
    
    webhook_cfg = notify_cfg.get("webhook", {})
    webhook_url = webhook_cfg.get("url", "")
    if not webhook_url:
        logger.debug("Webhook URL not configured")
        return False
    
    template = webhook_cfg.get("template", "*{title}*\n{detail}\nLevel: {level}\nTime: {timestamp}")
    timeout = webhook_cfg.get("timeout", 10)
    
    payload_text = template.format(
        title=title,
        detail=detail,
        level=level.upper(),
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    
    # Slack/Discord/Generic webhook 모두 text 필드 지원 가정
    payload = {"text": payload_text}
    
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                logger.info(f"[notify] Alert sent: {title}")
                return True
            else:
                logger.warning(f"[notify] Webhook returned {resp.status}: {title}")
                return False
    except Exception as e:
        logger.warning(f"[notify] Failed to send alert '{title}': {e}")
        return False


def send_test_alert() -> bool:
    """테스트용 알림 전송."""
    return send_alert("Test Alert", "This is a test notification from mc", level="info")
```

### 3.3 `mc auto`에서 알림 호출 (Task 1.4에서 이미 반영)

```python
# mc/queue.py mark_failed 호출 후 또는 mc auto 예외 처리 시

try:
    from mc.notify import send_alert
    send_alert(f"mc auto failed: {keyword}", f"{type(e).__name__}: {e}", level="error")
except Exception:
    pass  # 알림 실패는 무시
```

### 3.4 `cli/mc.py`에 `status` 서브커맨드 추가

```python
# cli/mc.py 서브파서 추가

status_p = subparsers.add_parser("status", help="최근 7일 발행 현황 요약")
status_p.add_argument("--days", type=int, default=7, help="조회 기간 (일)")
status_p.add_argument("--json", action="store_true", help="JSON 출력")
```

```python
def _cmd_status(args):
    """mc status — 최근 N일 체인 현황 요약 출력."""
    import chain_db as db
    from datetime import datetime, timedelta
    
    days = args.days
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    chains = db.get_chains_since(since)  # 신규 함수 필요: created_at >= since
    if not chains:
        print(f"[status] No chains in last {days} days")
        return
    
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
                    # URL에서 도메인 추출
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
    
    if args.json:
        import json
        print(json.dumps({
            "period_days": days,
            "total_chains": total,
            "completed": completed,
            "failed": failed,
            "in_progress": in_progress,
            "site_breakdown": site_stats,
            "smoke_test_pass_rate": f"{smoke_passed}/{smoke_total}" if smoke_total else "N/A",
        }, ensure_ascii=False, indent=2))
        return
    
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
    print(f"{'='*50}\n")
```

### 3.5 `chain_db.py`에 `get_chains_since` 추가

```python
# chain_db.py

def get_chains_since(date_str: str) -> list[dict]:
    """지정된 날짜 이후 생성된 체인 목록 조회."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM chains WHERE created_at >= ? ORDER BY created_at DESC",
        (date_str,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
```

---

## File Changes Summary

| 파일 | 변경 유형 | Task |
|------|-----------|------|
| `chain_db.py` | 수정 (마이그레이션 + `get_chains_since` + `update_keyword_queue_*` 함수) | 1, 3 |
| `mc/queue.py` | **신규 생성** | 1 |
| `mc/notify.py` | **신규 생성** | 3 |
| `cli/mc.py` | 수정 (queue, auto, schedule, status 서브커맨드 추가, 로깅 분리) | 1, 2, 3 |
| `config/keyword_queue.yaml` | 선택적 생성 (기본값용) | 1 |
| `config/notify.yaml` | **신규 생성** | 3 |
| `scheduler/launchd_manager.py` | 수정 (`add_auto_task` 추가) | 2 |
| `scheduler/cron_manager.py` | 수정 (`add_auto_task` 추가) | 2 |
| `scheduler/__init__.py` | 수정 (export 추가) | 2 |
| `chain_db.py` | `get_chains_since` 추가 | 3 |

---

## Dependencies Between Tasks

- Task 1 독립 수행 가능
- Task 2: Task 1의 `mc auto` 완료 후 검증 권장
- Task 3: Task 1, 2와 독립적이나 `mc auto`에서 알림 호출하므로 Task 1 이후 검증 권장

---

## Rollout Strategy

1. Task 1 완료 → 단위 테스트 작성 → pytest 통과 확인
2. Task 2 완료 → `mc schedule setup --daily --hour 9` 실행 → launchd plist 생성 확인 → `mc schedule status` 확인
3. Task 3 완료 → `config/notify.yaml`에 webhook URL 설정 → `mc auto` 실패 시 알림 전송 확인 → `mc status` 출력 확인
4. 전체 pytest `251+N` 통과 확인

---

## Acceptance Criteria (Definition of Done)

### Task 1 완료 조건
- [ ] `keyword_queue` 테이블 생성 마이그레이션 동작
- [ ] `mc queue add "키워드" --category travel --priority 3` → 큐에 추가됨
- [ ] `mc queue list` — 대기 중인 키워드 목록 출력
- [ ] `mc queue next` — 우선순위 높은 pending 1개 반환 후 processing 변경
- [ ] `mc queue remove "키워드"` — 큐에서 제거
- [ ] `mc auto` 실행 시 큐에서 키워드 꺼내 `run_chain()` 실행 → 완료 시 done, 실패 시 failed 기록
- [ ] 빈 큐에서 `mc auto` 실행 → "No pending keywords" 출력 후 exit 0
- [ ] 중복 키워드 add 시 warning 출력
- [ ] 단위 테스트 10개 이상 통과

### Task 2 완료 조건
- [ ] `mc schedule setup --daily --hour 9` → macOS launchd plist 생성 + load 확인
- [ ] `mc schedule setup --daily --hour 9 --no-launchd` → cron 등록 확인 (Linux)
- [ ] `mc schedule status` → 등록된 스케줄 출력
- [ ] `mc schedule remove` → 스케줄 제거 확인
- [ ] 로그 파일이 `logs/mc-auto-YYYY-MM-DD.log` 일자별로 분리 저장됨
- [ ] 단위 테스트: plist/cron 파일 내용 검증 (mock)

### Task 3 완료 조건
- [ ] `config/notify.yaml` 생성 (webhook URL 설정 가능)
- [ ] `mc/notify.py` `send_alert()` 구현 — Slack/Discord webhook 전송 동작
- [ ] 알림 실패 시 예외 전파 안 하고 로그만 기록
- [ ] `mc auto` 실패 시 자동 알림 전송 확인
- [ ] `mc status` — 최근 7일 요약 출력 (체인 수, 완료/실패, 사이트별, smoke test 통과율)
- [ ] `mc status --json` — JSON 출력
- [ ] 단위 테스트: send_alert mock, status 집계 로직

### 전체
- [ ] pytest 전체 통과 (**251 + 신규 테스트**)
- [ ] `git diff chain_publisher.py chain_publisher_core.py` — 0 changes (기존 파이프라인 코드 미수정)
- [ ] `mc auto --dry-run` — E2E 흐름 검증 (큐 추가 → auto 실행 → 상태 확인)