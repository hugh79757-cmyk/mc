"""
draft_loop_spoke.py — 스포크 loop_role 마커 (Phase 6)

chain_id의 모든 chain_posts에 loop_role = 'spoke' 설정.
실질적 듀얼 CTA 주입은 Wave 3에서 처리.
"""

import chain_db as db


def mark_loop_spokes(chain_id: int) -> tuple:
    """
    Mark all posts in a chain as spokes.
    Returns: (ok: bool, count_or_error: str)
    """
    posts = db.get_chain_posts(chain_id)
    if not posts:
        return (False, f"Chain #{chain_id} has no posts")

    count = 0
    for p in posts:
        db.set_loop_role(p["id"], "spoke")
        count += 1

    print(f"  [spoke] ✅ {count} posts marked as spoke for chain #{chain_id}")
    return (True, str(count))


if __name__ == "__main__":
    import sys
    cid = int(sys.argv[1]) if len(sys.argv) > 1 else 9
    ok, msg = mark_loop_spokes(cid)
    print(f"OK: {msg}" if ok else f"FAIL: {msg}")
