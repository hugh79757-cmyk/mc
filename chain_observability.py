"""Lightweight structured observability for MC chain execution."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


def emit_event(chain_id: int, event: str, **fields) -> str:
    """Append one flush-safe JSON event to logs/chain_<id>.jsonl."""
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "correlation_id": f"chain-{chain_id}",
        "pid": os.getpid(),
        "chain_id": chain_id,
        "event": event,
        **fields,
    }
    log_dir = Path(__file__).resolve().parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"chain_{chain_id}.jsonl"
    try:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return str(path)
    except Exception:
        return ""
