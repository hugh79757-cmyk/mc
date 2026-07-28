"""
mc/scheduler.py — 스케줄러 통합 모듈 (Phase 23)

macOS launchd + Linux cron을 통합 관리합니다.
"""

import os
import platform
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional


def get_os() -> str:
    """현재 OS 반환: 'macos' | 'linux'"""
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    elif system == "linux":
        return "linux"
    else:
        return "unknown"


# ── macOS Launchd ──

def generate_plist(
    hour: int = 9,
    minute: int = 0,
    project_dir: str = None,
    label: str = "com.mc.auto",
    python_path: str = "/usr/bin/env python3",
) -> str:
    """launchd plist XML 생성."""
    import plistlib

    project_dir = project_dir or str(Path(__file__).resolve().parent.parent)
    log_dir = Path(project_dir) / "logs"

    program_args = [
        python_path,
        "-m", "cli.mc",
        "auto",
    ]

    plist_dict = {
        "Label": label,
        "ProgramArguments": program_args,
        "WorkingDirectory": project_dir,
        "StartCalendarInterval": {"Hour": hour, "Minute": minute},
        "StandardOutPath": str(log_dir / "mc-auto-%Y-%m-%d.log"),
        "StandardErrorPath": str(log_dir / "mc-auto-error.log"),
        "KeepAlive": False,
        "RunAtLoad": False,
        "EnvironmentVariables": {
            "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin",
        },
    }

    return plistlib.dumps(plist_dict).decode("utf-8")


def install_schedule_macos(
    hour: int = 9,
    minute: int = 0,
    label: str = "com.mc.auto",
    project_dir: str = None,
) -> str:
    """macOS launchd 스케줄 등록."""
    import plistlib

    project_dir = project_dir or str(Path(__file__).resolve().parent.parent)
    log_dir = Path(project_dir) / "logs"
    launch_agents_dir = Path.home() / "Library" / "LaunchAgents"

    log_dir.mkdir(parents=True, exist_ok=True)
    launch_agents_dir.mkdir(parents=True, exist_ok=True)

    plist_path = launch_agents_dir / f"{label}.plist"

    program_args = [
        "/usr/bin/env python3",
        "-m", "cli.mc",
        "auto",
    ]

    plist_dict = {
        "Label": label,
        "ProgramArguments": program_args,
        "WorkingDirectory": project_dir,
        "StartCalendarInterval": {"Hour": hour, "Minute": minute},
        "StandardOutPath": str(log_dir / "mc-auto-%Y-%m-%d.log"),
        "StandardErrorPath": str(log_dir / "mc-auto-error.log"),
        "KeepAlive": False,
        "RunAtLoad": False,
        "EnvironmentVariables": {
            "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin",
        },
    }

    with open(plist_path, "wb") as f:
        plistlib.dump(plist_dict, f)

    # load
    result = subprocess.run(
        ["launchctl", "load", str(plist_path)],
        capture_output=True, timeout=15, check=False,
    )

    if result.returncode != 0:
        # Already loaded - unload first
        subprocess.run(["launchctl", "unload", str(plist_path)], capture_output=True, check=False)
        subprocess.run(["launchctl", "load", str(plist_path)], capture_output=True, check=False)

    return str(plist_path)


def remove_schedule_macos(label: str = "com.mc.auto") -> bool:
    """macOS launchd 스케줄 제거."""
    launch_agents_dir = Path.home() / "Library" / "LaunchAgents"
    plist_path = launch_agents_dir / f"{label}.plist"

    if plist_path.exists():
        subprocess.run(
            ["launchctl", "unload", str(plist_path)],
            capture_output=True, timeout=15, check=False,
        )
        plist_path.unlink()
        return True
    return False


def get_status_macos(label: str = "com.mc.auto") -> Dict[str, Any]:
    """macOS launchd 스케줄 상태 확인."""
    launch_agents_dir = Path.home() / "Library" / "LaunchAgents"
    plist_path = launch_agents_dir / f"{label}.plist"

    exists = plist_path.exists()

    # launchctl list로 확인
    loaded = False
    if exists:
        result = subprocess.run(
            ["launchctl", "list"],
            capture_output=True, text=True, timeout=10,
        )
        loaded = label in result.stdout

    return {
        "os": "macos",
        "plist_path": str(plist_path) if exists else None,
        "plist_exists": exists,
        "loaded": loaded,
    }


# ── Linux Cron ──

def generate_crontab_line(
    hour: int = 9,
    minute: int = 0,
    project_dir: str = None,
    command: str = None,
) -> str:
    """crontab 라인 생성."""
    project_dir = project_dir or str(Path(__file__).resolve().parent.parent)
    log_dir = Path(project_dir) / "logs"

    if command is None:
        command = f"cd {project_dir} && /usr/bin/env python3 -m cli.mc auto >> {log_dir}/mc-auto-$(date +%Y-%m-%d).log 2>&1"

    return f"{minute} {hour} * * * {command} # mc-auto"


def install_schedule_linux(
    hour: int = 9,
    minute: int = 0,
    project_dir: str = None,
    command: str = None,
) -> bool:
    """Linux cron 스케줄 등록."""
    project_dir = project_dir or str(Path(__file__).resolve().parent.parent)
    log_dir = Path(project_dir) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    if command is None:
        command = f"cd {project_dir} && /usr/bin/env python3 -m cli.mc auto >> {log_dir}/mc-auto-$(date +%Y-%m-%d).log 2>&1"

    cron_line = f"{minute} {hour} * * * {command} # mc-auto"

    try:
        from crontab import CronTab
        cron = CronTab(user=True)

        # Check for existing mc-auto entry
        for job in cron:
            if "# mc-auto" in (job.comment or "") and "mc auto" in str(job):
                print("  [scheduler] Cron entry already exists")
                return False

        job = cron.new(command=command, comment="mc-auto daily")
        job.setall(minute, hour, "*", "*", "*")
        cron.write()
        return True
    except ImportError:
        # Fallback: direct crontab manipulation
        try:
            result = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=10)
            existing = result.stdout if result.returncode == 0 else ""

            if cron_line in existing:
                print("  [scheduler] Cron entry already exists")
                return False

            new_crontab = existing.rstrip() + "\n" + cron_line + "\n"
            proc = subprocess.run(["crontab", "-"], input=new_crontab, text=True, capture_output=True, timeout=10)
            return proc.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False


def remove_schedule_linux() -> bool:
    """Linux cron 스케줄 제거."""
    try:
        from crontab import CronTab
        cron = CronTab(user=True)
        removed = False
        for job in cron:
            if "# mc-auto" in (job.comment or "") and "mc auto" in str(job):
                cron.remove(job)
                removed = True
        if removed:
            cron.write()
        return removed
    except ImportError:
        try:
            result = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                return False
            lines = [l for l in result.stdout.split("\n") if "# mc-auto" not in l or "mc auto" not in l]
            new_crontab = "\n".join(lines) + "\n"
            proc = subprocess.run(["crontab", "-"], input=new_crontab, text=True, capture_output=True, timeout=10)
            return proc.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False


def get_status_linux() -> Dict[str, Any]:
    """Linux cron 스케줄 상태 확인."""
    try:
        from crontab import CronTab
        cron = CronTab(user=True)
        entries = []
        for job in cron:
            if "# mc-auto" in (job.comment or "") and "mc auto" in str(job):
                entries.append({
                    "command": str(job),
                    "schedule": str(job.slices),
                    "enabled": job.is_enabled(),
                })
        return {
            "os": "linux",
            "entries": entries,
            "has_schedule": len(entries) > 0,
        }
    except ImportError:
        try:
            result = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                return {"os": "linux", "entries": [], "has_schedule": False}
            entries = []
            for line in result.stdout.split("\n"):
                if "# mc-auto" in line and "mc auto" in line:
                    entries.append({"command": line.strip()})
            return {
                "os": "linux",
                "entries": entries,
                "has_schedule": len(entries) > 0,
            }
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return {"os": "linux", "entries": [], "has_schedule": False}


# ── Unified Interface ──

def generate_schedule(
    hour: int = 9,
    minute: int = 0,
    project_dir: str = None,
) -> str:
    """OS에 맞는 스케줄 생성."""
    os_type = get_os()
    if os_type == "macos":
        return generate_plist(hour, minute, project_dir)
    elif os_type == "linux":
        return generate_crontab_line(hour, minute, project_dir)
    else:
        raise NotImplementedError(f"Unsupported OS: {os_type}")


def install_schedule(
    hour: int = 9,
    minute: int = 0,
    project_dir: str = None,
) -> bool:
    """OS에 맞는 스케줄 등록."""
    os_type = get_os()
    if os_type == "macos":
        install_schedule_macos(hour, minute, project_dir=project_dir)
        return True
    elif os_type == "linux":
        return install_schedule_linux(hour, minute, project_dir)
    else:
        raise NotImplementedError(f"Unsupported OS: {os_type}")


def remove_schedule() -> bool:
    """OS에 맞는 스케줄 제거."""
    os_type = get_os()
    if os_type == "macos":
        return remove_schedule_macos()
    elif os_type == "linux":
        return remove_schedule_linux()
    else:
        return False


def get_status() -> Dict[str, Any]:
    """OS에 맞는 스케줄 상태 확인."""
    os_type = get_os()
    if os_type == "macos":
        return get_status_macos()
    elif os_type == "linux":
        return get_status_linux()
    else:
        return {"os": os_type, "entries": [], "has_schedule": False}


# ── Log Rotation ──

def setup_daily_log_rotation(log_dir: str = None, max_days: int = 30) -> None:
    """일자별 로그 파일 핸들러 설정 + 오래된 로그 삭제."""
    import logging
    from datetime import datetime, timedelta

    log_dir = log_dir or str(Path(__file__).resolve().parent.parent / "logs")
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # 오늘 날짜 로그 파일
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = log_path / f"mc-auto-{today}.log"

    # 루트 로거에 FileHandler 추가 (중복 방지)
    root_logger = logging.getLogger()

    # 기존 mc-auto 파일 핸들러 제거
    for handler in root_logger.handlers[:]:
        if isinstance(handler, logging.FileHandler):
            if "mc-auto" in handler.baseFilename:
                root_logger.removeHandler(handler)
                handler.close()

    # 새 핸들러 추가
    file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root_logger.addHandler(file_handler)

    # 오래된 로그 삭제 (max_days 이상)
    cutoff = datetime.now() - timedelta(days=max_days)
    for log_file in log_path.glob("mc-auto-*.log"):
        try:
            # 파일명에서 날짜 추출
            name = log_file.stem  # mc-auto-YYYY-MM-DD
            if name.startswith("mc-auto-"):
                date_str = name[8:]  # YYYY-MM-DD
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
                if file_date < cutoff:
                    log_file.unlink()
        except (ValueError, OSError):
            pass


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "status":
            print(get_status())
        elif sys.argv[1] == "install":
            hour = int(sys.argv[2]) if len(sys.argv) > 2 else 9
            minute = int(sys.argv[3]) if len(sys.argv) > 3 else 0
            install_schedule(hour, minute)
            print(f"Schedule installed: {hour}:{minute:02d}")
        elif sys.argv[1] == "remove":
            remove_schedule()
            print("Schedule removed")