"""
mc/notify.py — 통합 알림 전송 모듈 (Phase 23)

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


def send_success(title: str, detail: str) -> bool:
    """성공 알림 전송 (level=info)."""
    return send_alert(title, detail, level="info")


def send_test_alert() -> bool:
    """테스트용 알림 전송."""
    return send_alert("Test Alert", "This is a test notification from mc", level="info")