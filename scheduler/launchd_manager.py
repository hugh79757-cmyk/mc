"""
launchd_manager.py — macOS launchd plist 관리

macOS 전용. ~/Library/LaunchAgents/ 에 plist 생성 후 launchctl load.
"""

import os
import subprocess
import plistlib
from pathlib import Path

MC_ROOT = Path(__file__).resolve().parent.parent
LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
LOG_DIR = MC_ROOT / "logs"


class LaunchdManager:
    def add_task(
        self,
        chain_id: int,
        command: str = None,
        hour: int = 9,
        minute: int = 0,
        label: str = None,
    ):
        """launchd plist 생성 및 load."""
        label = label or f"com.mc.publisher.{chain_id}"
        plist_path = LAUNCH_AGENTS_DIR / f"{label}.plist"
        LOG_DIR.mkdir(parents=True, exist_ok=True)

        program_args = command or [
            "python3",
            str(MC_ROOT / "scheduler" / "task_runner.py"),
            str(chain_id),
        ]

        plist = {
            "Label": label,
            "ProgramArguments": program_args,
            "StartCalendarInterval": {"Hour": hour, "Minute": minute},
            "StandardOutPath": str(LOG_DIR / "scheduler.log"),
            "StandardErrorPath": str(LOG_DIR / "scheduler_error.log"),
            "KeepAlive": False,
            "RunAtLoad": False,
        }

        LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)
        with open(plist_path, "wb") as f:
            plistlib.dump(plist, f)
        print(f"  [scheduler] ✅ plist created: {plist_path}")

        subprocess.run(
            ["launchctl", "load", str(plist_path)],
            capture_output=True, timeout=15, check=False,
        )
        print(f"  [scheduler] ✅ launchctl loaded: {label}")

    def remove_task(self, label: str):
        """plist unload 및 삭제."""
        plist_path = LAUNCH_AGENTS_DIR / f"{label}.plist"
        if plist_path.exists():
            subprocess.run(
                ["launchctl", "unload", str(plist_path)],
                capture_output=True, timeout=15, check=False,
            )
            plist_path.unlink()
            print(f"  [scheduler] ✅ Removed: {label}")
        else:
            print(f"  [scheduler] ⚠️ Not found: {label}")

    def list_tasks(self) -> list[dict]:
        """LaunchAgents에서 mc plist 목록."""
        tasks = []
        pattern = "com.mc.publisher."
        if LAUNCH_AGENTS_DIR.exists():
            for f in LAUNCH_AGENTS_DIR.glob(f"{pattern}*.plist"):
                tasks.append({
                    "label": f.stem,
                    "path": str(f),
                })
        return tasks
