"""
cron_manager.py — Linux/macOS cron 작업 관리

의존성: python-crontab (pip install python-crontab)
없으면 fallback: subprocess crontab 직접 제어
"""

import os
import subprocess
import shlex

MC_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMMENT_TAG = "# mc-scheduler"


class CronManager:
    def add_task(self, command: str, cron_expr: str, description: str = ""):
        """crontab에 mc 작업 추가 (중복 방지)."""
        try:
            from crontab import CronTab
            cron = CronTab(user=True)
            existing = [
                j for j in cron if COMMENT_TAG in (j.comment or "")
                and command in str(j)
            ]
            if existing:
                print(f"  [scheduler] ⚠️ Task already exists: {command[:60]}")
                return
            job = cron.new(command=command, comment=f"{COMMENT_TAG} {description}")
            job.setall(cron_expr)
            cron.write()
            print(f"  [scheduler] ✅ Cron added: {cron_expr} {command[:40]}...")
        except ImportError:
            self._add_task_fallback(command, cron_expr)

    def remove_task(self, command: str):
        """crontab에서 mc 작업 제거."""
        try:
            from crontab import CronTab
            cron = CronTab(user=True)
            cron.remove_all(
                lambda j: COMMENT_TAG in (j.comment or "") and command in str(j)
            )
            cron.write()
            print(f"  [scheduler] ✅ Cron removed: {command[:40]}...")
        except ImportError:
            self._remove_task_fallback(command)

    def list_tasks(self) -> list[dict]:
        """등록된 mc cron 작업 목록."""
        try:
            from crontab import CronTab
            cron = CronTab(user=True)
            tasks = []
            for j in cron:
                if COMMENT_TAG in (j.comment or ""):
                    tasks.append({
                        "command": str(j),
                        "schedule": str(j.slices),
                        "description": (j.comment or "").replace(COMMENT_TAG, "").strip(),
                    })
            return tasks
        except ImportError:
            return self._list_tasks_fallback()

    def _add_task_fallback(self, command: str, cron_expr: str):
        """python-crontab 없을 때 raw crontab 조작."""
        existing = self._get_crontab()
        entry = f"{cron_expr} {command} {COMMENT_TAG}"
        if entry in existing:
            print(f"  [scheduler] ⚠️ Task already exists")
            return
        existing.append(entry)
        self._set_crontab(existing)
        print(f"  [scheduler] ✅ Cron added (fallback)")

    def _remove_task_fallback(self, command: str):
        existing = self._get_crontab()
        filtered = [l for l in existing if COMMENT_TAG not in l or command not in l]
        self._set_crontab(filtered)

    def _list_tasks_fallback(self) -> list:
        return [
            {"command": l, "schedule": "", "description": ""}
            for l in self._get_crontab() if COMMENT_TAG in l
        ]

    def _get_crontab(self) -> list:
        try:
            result = subprocess.run(
                ["crontab", "-l"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                return [l.strip() for l in result.stdout.split("\n") if l.strip()]
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return []

    def _set_crontab(self, lines: list):
        content = "\n".join(lines) + "\n"
        proc = subprocess.Popen(
            ["crontab"], stdin=subprocess.PIPE, text=True
        )
        proc.communicate(input=content)
