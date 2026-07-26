"""
mc/queue.py — 키워드 큐 관리 (Phase 23)

DB 연장)

DB 테이블 keyword_queue를 사용해 키워드를 큐에 저장하고 관리합니다.
"""

from datetime import datetime
from typing import Optional, List, Dict
import chain_db as db


def add_keyword(keyword: str, category: str = None, priority: int = 3) -> Dict:
    """키워드 큐에 추가. 중복 시 warning 반환."""
    return db.add_keyword_queue(keyword, category, priority)


def get_next_keyword() -> Optional[Dict]:
    """우선순위 높은 pending 키워드 1개 반환 후 processing으로 변경."""
    return db.get_next_keyword()


def mark_done(queue_id: int, chain_id: int):
    """처리 완료: done으로 변경. queue_id 기반."""
    conn = db.get_conn()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "UPDATE keyword_queue SET status = 'done', processed_at = ?, chain_id = ? WHERE id = ?",
        (now, chain_id, queue_id)
    )
    conn.commit()
    conn.close()


def mark_failed(queue_id: int, error_msg: str):
    """처리 실패: failed로 변경 + 에러 메시지 기록. queue_id 기반."""
    conn = db.get_conn()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "UPDATE keyword_queue SET status = 'failed', processed_at = ?, error_msg = ? WHERE id = ?",
        (now, error_msg, queue_id)
    )
    conn.commit()
    conn.close()


def list_queue(status: str = None) -> List[Dict]:
    """큐 목록 조회."""
    return db.list_keyword_queue(status)


def remove_keyword(queue_id: int) -> bool:
    """큐에서 키워드 제거 (pending만 삭제 가능)."""
    conn = db.get_conn()
    cur = conn.execute("DELETE FROM keyword_queue WHERE id = ? AND status = 'pending'", (queue_id,))
    conn.commit()
    conn.close()
    return cur.rowcount > 0


# 키워드 기반 편의 함수들 (기존 호환용)
def mark_done_by_keyword(keyword: str, chain_id: int):
    """키워드 기반으로 done 처리 (기존 호환)."""
    db.mark_keyword_done(keyword, chain_id)


def mark_failed_by_keyword(keyword: str, error_msg: str):
    """키워드 기반으로 failed 처리 (기존 호환)."""
    db.mark_keyword_failed(keyword, error_msg)